import os
import time
import threading
import logging
import requests
from flask import Flask, request, jsonify

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
LOG = logging.getLogger("aiops")

# -------------------------------------------------
# Configuration (ENV VARS)
# -------------------------------------------------
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")

# -------------------------------------------------
# Flask app
# -------------------------------------------------
app = Flask(__name__)

# Track active alerts
pending_alerts = {}

# -------------------------------------------------
# Helpers
# -------------------------------------------------


def extract_instance_id(payload: dict) -> str:
    """
    Extract EC2 Instance ID from Coralogix metric alert payload
    """
    # Common Coralogix locations
    for key in ("labels", "dimensions"):
        section = payload.get(key, {})
        if isinstance(section, dict):
            for name in ("InstanceId", "instance_id", "instanceId"):
                if name in section:
                    return section[name]
    return "unknown"

# -------------------------------------------------
# Microsoft Graph helpers
# -------------------------------------------------
def get_graph_token():
    app_msal = ConfidentialClientApplication(
        GRAPH_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}",
        client_credential=GRAPH_CLIENT_SECRET
    )
    token = app_msal.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    return token.get("access_token")


def send_email(subject, body):
    token = get_graph_token()
    if not token:
        LOG.error("Failed to obtain Graph token")
        return

    url = f"https://graph.microsoft.com/v1.0/users/{EMAIL_FROM}/sendMail"
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [
                {"emailAddress": {"address": EMAIL_TO}}
            ]
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, json=payload, timeout=10)
    LOG.info("Email sent status: %s", r.status_code)


# -------------------------------------------------
# Teams helper
# -------------------------------------------------

def send_to_teams(payload: dict):
    headers = {"Content-Type": "application/json"}

    r = requests.post(
        TEAMS_WEBHOOK_URL,
        headers=headers,
        json=payload,
        timeout=10
    )

    LOG.info(
        "Teams webhook status=%s response=%s",
        r.status_code,
        r.text
    )

# -------------------------------------------------
# Alert monitoring
# -------------------------------------------------
def monitor_alert(alert_id, alert_name, instance_id, wait_minutes=10):
    LOG.info("Monitoring alert %s", alert_id)
    time.sleep(wait_minutes * 60)

    if alert_id in pending_alerts:
        LOG.warning(
            "Alert %s still unresolved after %s minutes",
            alert_id,
            wait_minutes
        )
        pending_alerts.pop(alert_id, None)

# -------------------------------------------------
# Webhook endpoint
# -------------------------------------------------
@app.route("/coralogix/webhook", methods=["POST"])
def coralogix_webhook():
    payload = request.get_json(force=True)
    LOG.info("Webhook received: %s", payload)

    alert_id = payload.get("alert_id")
    alert_name = payload.get("alert_name", "unknown")
    raw_action = payload.get("alert_action", "").upper()

    instance_id = extract_instance_id(payload)

    if not alert_id or not raw_action:
        return jsonify({"error": "invalid payload"}), 400

    LOG.info(
        "Parsed action=%s alert_id=%s instance_id=%s",
        raw_action,
        alert_id,
        instance_id
    )

    # ---------------- TRIGGERED ----------------
    if raw_action in ("TRIGGER", "TRIGGERED"):
        pending_alerts[alert_id] = True

        threading.Thread(
            target=monitor_alert,
            args=(alert_id, alert_name, instance_id),
            daemon=True
        ).start()

        return jsonify({"status": "monitoring"}), 202

    # ---------------- RESOLVED ----------------
    if raw_action in ("RESOLVE", "RESOLVED"):
        pending_alerts.pop(alert_id, None)

        teams_payload = {
            "alert_id": alert_id,
            "alert_name": alert_name,
            "alert_action": "RESOLVED",
            "instance_id": instance_id
        }

        LOG.info("Sending RESOLVED alert to Teams")
        send_to_teams(teams_payload)

        return jsonify({"status": "resolved"}), 200

    return jsonify({"status": "ignored"}), 200

# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

# -------------------------------------------------
# Entrypoint
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
