
## AIOps POC – Coralogix → EC2 → Teams / Email

### Overview

This repository contains a Proof of Concept (POC) for an **AIOps alert mediation layer** that reduces alert noise by automatically handling short-lived alerts and escalating only unresolved alerts.

---

## 1. Architecture

### High-level flow

```
Coralogix Alert
   |
   | (Outbound Webhook)
   v
EC2 (Python Flask – AIOps Service)
   |
   ├── Resolved within 10 minutes → Microsoft Teams
   └── Unresolved after 10 minutes → Email Escalation
```

<img width="1536" height="1024" alt="ChatGPT Image Jan 14, 2026, 06_11_45 PM" src="https://github.com/user-attachments/assets/cf01e43d-fc8a-4ef9-9c40-332ee82aabb8" />


---

## 2. Prerequisites

* AWS EC2 (Ubuntu)
* Python 3.10+
* Coralogix account
* Microsoft Teams
* Power Automate
* Internet access from EC2

---

## 3. EC2 Setup

### Step 1: Launch EC2

* OS: Ubuntu
* Instance type: t2.micro (POC)
* Open inbound port **5000**

---

### Step 2: SSH into EC2

```bash
ssh ubuntu@<EC2_PUBLIC_IP>
```

---

## 4. Python Environment Setup

```bash
python3 -m venv aiops-venv
source aiops-venv/bin/activate
pip install flask requests msal
```

---

## 5. AIOps Flask Service

### File: `aiops_webhook.py`

**Endpoints**

* `GET /health` – health check
* `POST /coralogix/webhook` – receives alerts

**Expected payload**

```json
{
  "alert_id": "string",
  "alert_name": "string",
  "alert_action": "TRIGGERED | RESOLVED"
}
```
---

## 6. Environment Configuration

### File: `/etc/aiops.env`

path:/etc/aiops.env

```ini
CORALOGIX_API_KEY=xxxxx
CORALOGIX_API_BASE=https://api.ap1.coralogix.com
TEAMS_WEBHOOK_URL=https://<power-automate-url>
EMAIL_FROM=alerts@domain.com
EMAIL_TO=alerts@domain.com
```

---

## 7. systemd Service Setup

### File: `aiops.service`

path: /etc/systemd/system/aiops.service

```ini
[Unit]
Description=AIOps Coralogix monitor
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/aiops-venv
ExecStart=/home/ubuntu/aiops-venv/bin/python /home/ubuntu/aiops-venv/aiops_webhook.py
EnvironmentFile=/etc/aiops.env
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable aiops.service
sudo systemctl start aiops.service
```

---

## 8. Teams Integration (Power Automate)

* Create HTTP-triggered workflow
* Connect to Teams channel
* Enable workflow

<img width="1079" height="796" alt="image" src="https://github.com/user-attachments/assets/e0f843a1-6dcf-4c9f-a6bc-6bef4960f5e2" />

---

## 9. Testing

### Health check

```bash
curl http://localhost:5000/health
```

### Trigger alert

```bash
curl -X POST http://localhost:5000/coralogix/webhook \
-H "Content-Type: application/json" \
-d '{
  "alert_id": "test-xx",
  "alert_name": "CPU Spike Test",
  "alert_action": "TRIGGERED"
}'
```

### Resolve alert

```bash
curl -X POST http://localhost:5000/coralogix/webhook \
-H "Content-Type: application/json" \
-d '{
  "alert_id": "test-xx",
  "alert_name": "CPU Spike Test",
  "alert_action": "RESOLVED"
}'
```

<img width="1550" height="201" alt="image" src="https://github.com/user-attachments/assets/9283d5b4-3000-462a-a17b-551bd900e666" />

<img width="1229" height="528" alt="image" src="https://github.com/user-attachments/assets/d90b13f0-afda-4659-bc72-fa5212e0b30c" />


---

## 10. Errors Encountered

### Coralogix

* Outbound webhook UI failed
* Alerts not delivered consistently

<img width="1913" height="969" alt="Screenshot 2026-01-14 163210" src="https://github.com/user-attachments/assets/b112455c-f2f3-4009-bbdc-f048ec4b613b" />


### Microsoft Graph

* Email escalation failed with HTTP 403
* Tenant policy blocks app-only mail sending

<img width="1329" height="184" alt="Screenshot 2026-01-12 153638" src="https://github.com/user-attachments/assets/2d617933-037c-407b-9b6b-9547793c82c0" />

<img width="1835" height="666" alt="Screenshot 2026-01-12 154402" src="https://github.com/user-attachments/assets/666f682f-2916-418c-9db5-50c7a265438e" />

---

## 11. Limitations

* Coralogix webhook reliability
* Microsoft tenant email restrictions
* In-memory alert state (POC only)

---

## 12. Conclusion

This POC successfully validates:

* AIOps alert suppression logic
* Automated resolution handling
* Teams notification flow

Remaining gaps are **platform and policy limitations**, not design issues.

---
