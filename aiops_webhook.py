import os
import time
import threading
import json
import logging
import requests
from flask import Flask, request, jsonify
from msal import ConfidentialClientApplication

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("aiops")

# -------------------------------------------------
# Configuration (READ FROM ENV VARS ONLY)
# -------------------------------------------------
CORALOGIX_API_KEY = os.getenv("CORALOGIX_API_KEY")
CORALOGIX_API_BASE = os.getenv("CORALOGIX_API_BASE")

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

# Track active alerts
pending_alerts = {}

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

    r = requests.post(url, headers=headers, json=payload)
    LOG.info("Email sent: %s", r.status_code)


# -------------------------------------------------
# Teams helper
# -------------------------------------------------
def send_to_teams(title, message):
    payload = {
        "title": title,
        "message": message
    }

    r = requests.post(
        TEAMS_WEBHOOK_URL,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=10
    )

    LOG.info("Teams webhook status: %s | response: %s", r.status_code, r.text)

# -------------------------------------------------
# Alert monitoring logic
# -------------------------------------------------
def monitor_alert(alert_id, alert_name, wait_minutes=10):
    LOG.info("Monitoring alert %s", alert_id)
    time.sleep(wait_minutes * 60)

    # If still pending → unresolved
    if alert_id in pending_alerts:
        LOG.info("Alert %s unresolved, escalating", alert_id)
        send_email(
            subject=f"Unresolved alert: {alert_name}",
            body=f"Alert {alert_name} ({alert_id}) did not resolve within {wait_minutes} minutes."
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
    alert_name = payload.get("alert_name")
    action = payload.get("alert_action")

    if not alert_id or not action:
        return jsonify({"error": "invalid payload"}), 400

    # ALERT RESOLVED → Teams
    if action.upper() == "RESOLVED":
        pending_alerts.pop(alert_id, None)
        send_to_teams(
            title="Alert Resolved",
            message=f"Alert **{alert_name}** ({alert_id}) has been resolved."
        )
        return jsonify({"status": "resolved"}), 200

    # ALERT TRIGGERED → start monitoring
    if action.upper() == "TRIGGERED":
        pending_alerts[alert_id] = payload
        t = threading.Thread(
            target=monitor_alert,
            args=(alert_id, alert_name),
            daemon=True
        )
        t.start()
        return jsonify({"status": "monitoring"}), 202

    return jsonify({"status": "ignored"}), 200


# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# -------------------------------------------------
# App entrypoint
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
