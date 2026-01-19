import os
import time
import threading
import logging
import requests
from flask import Flask, request, jsonify
from msal import ConfidentialClientApplication

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s aiops: %(message)s"
)
LOG = logging.getLogger("aiops")

# -------------------------------------------------
# Environment variables
# -------------------------------------------------
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")

GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")

# -------------------------------------------------
# Flask app
# -------------------------------------------------
app = Flask(__name__)

# Track alerts waiting for resolution
pending_alerts = {}

# -------------------------------------------------
# Microsoft Graph helpers (Outlook escalation)
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
            "body": {
                "contentType": "Text",
                "content": body
            },
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
    LOG.info("Email sent | status=%s", r.status_code)

# -------------------------------------------------
# Microsoft Teams helper
# -------------------------------------------------
def send_to_teams(alert_name, alert_id, instance_id, status):
    payload = {
        "title": "Coralogix Alert Update",
        "text": (
            f"**Alert Name:** {alert_name}\n\n"
            f"**Alert ID:** {alert_id}\n\n"
            f"**Instance ID:** {instance_id}\n\n"
            f"**Status:** {status}"
        )
    }

    r = requests.post(
        TEAMS_WEBHOOK_URL,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=10
    )

    LOG.info(
        "Teams webhook status=%s | response=%s",
        r.status_code,
        r.text
    )

# -------------------------------------------------
# Alert monitoring logic (escalation timer)
# -------------------------------------------------
def monitor_alert(alert_id, alert_name, instance_id, wait_minutes=10):
    LOG.info("Monitoring alert %s", alert_id)
    time.sleep(wait_minutes * 60)

    if alert_id in pending_alerts:
        LOG.info("Alert %s unresolved, escalating", alert_id)

        send_email(
            subject=f"Unresolved alert: {alert_name}",
            body=(
                f"Alert Name: {alert_name}\n"
                f"Alert ID: {alert_id}\n"
                f"Instance ID: {instance_id}\n\n"
                f"The alert did not resolve within {wait_minutes} minutes."
            )
        )

        pending_alerts.pop(alert_id, None)

# -------------------------------------------------
# Coralogix webhook endpoint
# -------------------------------------------------
@app.route("/coralogix/webhook", methods=["POST"])
def coralogix_webhook():
    payload = request.get_json(force=True)
    LOG.info("Webhook received: %s", payload)

    alert_id = payload.get("alert_id")
    alert_name = payload.get("alert_name", "Unknown Alert")
    raw_action = payload.get("alert_action", "")
    instance_id = payload.get("instance_id", "unknown")

    action = raw_action.strip().upper()

    LOG.info(
        "Parsed action=%s alert_id=%s instance_id=%s",
        action, alert_id, instance_id
    )

    if not alert_id or not action:
        return jsonify({"error": "invalid payload"}), 400

    # -------------------------
    # ALERT TRIGGERED
    # -------------------------
    if action in ["TRIGGER", "TRIGGERED"]:
        pending_alerts[alert_id] = {
            "alert_name": alert_name,
            "instance_id": instance_id
        }

        LOG.info("Alert triggered, starting monitor")

        t = threading.Thread(
            target=monitor_alert,
            args=(alert_id, alert_name, instance_id),
            daemon=True
        )
        t.start()

        return jsonify({"status": "monitoring"}), 202

    # -------------------------
    # ALERT RESOLVED
    # -------------------------
    if action in ["RESOLVE", "RESOLVED"]:
        pending_alerts.pop(alert_id, None)

        LOG.info("Sending RESOLVED to Teams")

        send_to_teams(
            alert_name=alert_name,
            alert_id=alert_id,
            instance_id=instance_id,
            status="RESOLVED"
        )

        return jsonify({"status": "resolved"}), 200

    return jsonify({"status": "ignored"}), 200

# -------------------------------------------------
# Entrypoint
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
