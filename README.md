
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

📸 `screenshots/ec2/ec2-launch.png`

---

### Step 2: SSH into EC2

```bash
ssh ubuntu@<EC2_PUBLIC_IP>
```

📸 `screenshots/ec2/ssh.png`

---

## 4. Python Environment Setup

```bash
python3 -m venv aiops-venv
source aiops-venv/bin/activate
pip install flask requests msal
```

📸 `screenshots/ec2/python-setup.png`

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

📸 `screenshots/code/aiops_webhook.png`

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

📸 `screenshots/ec2/env-file.png`

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

📸 `screenshots/ec2/systemd.png`

---

## 8. Teams Integration (Power Automate)

* Create HTTP-triggered workflow
* Connect to Teams channel
* Enable workflow

📸 `screenshots/teams/power-automate.png`

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
  "alert_id": "test-001",
  "alert_name": "CPU Spike Test",
  "alert_action": "TRIGGERED"
}'
```

### Resolve alert

```bash
curl -X POST http://localhost:5000/coralogix/webhook \
-H "Content-Type: application/json" \
-d '{
  "alert_id": "test-001",
  "alert_name": "CPU Spike Test",
  "alert_action": "RESOLVED"
}'
```

📸 `screenshots/logs/journalctl.png`

---

## 10. Errors Encountered

### Coralogix

* Outbound webhook UI failed
* Alerts not delivered consistently

📸 `screenshots/coralogix/webhook-error.png`

### Microsoft Graph

* Email escalation failed with HTTP 403
* Tenant policy blocks app-only mail sending

📸 `screenshots/logs/graph-403.png`

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

# 🚀 How to Push This to GitHub (Commands)

```bash
git init
git add .
git commit -m "Initial AIOps Coralogix POC"
git branch -M main
git remote add origin https://github.com/<your-org>/aiops-coralogix-poc.git
git push -u origin main
```

---

## ✅ Final Recommendation

✔ GitHub + README.md is **better than Word**
✔ Easier to maintain
✔ Screenshot-friendly
✔ Industry standard

If you want, next I can:

* Generate the **architecture diagram**
* Convert your existing Word content into README automatically
* Prepare a **public-safe version** (no sensitive terms)
* Create a **v2 branch** plan

Just tell me the next step.
