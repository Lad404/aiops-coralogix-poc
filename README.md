## AIOps – Coralogix Alert Intelligence Engine (POC)

## 📌 Overview

This project implements an **AIOps decision layer** between **Coralogix** and **notification systems (Microsoft Teams & Outlook)**.

The goal is to:

* Eliminate noise from short-lived alerts
* Automatically determine whether an alert **resolved on its own**
* Route alerts intelligently:

  * **Resolved → Microsoft Teams**
  * **Unresolved → Email escalation**

The solution is deployed on an **AWS EC2 instance**, exposed securely over **HTTPS using Cloudflare Tunnel**, and integrated with **Coralogix Metric Alerts** sourced from **AWS CloudWatch via Coralogix integration (CloudFormation)**.

---

## 🧱 Architecture (Final)

```
AWS EC2 (CPU Metrics)
   │
   ▼
AWS CloudWatch
   │
   ▼
Coralogix AWS Integration
(CloudFormation – no manual metric streams)
   │
   ▼
Coralogix Metric Alert
   │
   ▼
Outbound Webhook (HTTPS)
   │
   ▼
Cloudflare Tunnel (trycloudflare.com)
   │
   ▼
AIOps Flask Engine (EC2 :5000)
   │
   ├─ Alert resolved  → Microsoft Teams (Power Automate Webhook)
   └─ Alert unresolved → Outlook Email (Microsoft Graph)
```

---

## 📁 Directory Structure

```bash
/home/ubuntu/aiops-venv/
├── aiops_webhook.py        # Main AIOps engine
├── bin/                    # Python virtualenv binaries
├── include/
├── lib/
├── lib64/
├── pyvenv.cfg
```

---

## 🧰 Prerequisites

* AWS EC2 (Amazon Linux / Ubuntu)
* Python 3.10+
* Coralogix account
* Microsoft Teams (with Power Automate)
* Microsoft Entra ID App (Graph Mail.Send)
* Internet access (for Cloudflare Tunnel)

---

## 🔹 Step 1: Create Python Virtual Environment

```bash
sudo apt update
sudo apt install python3-venv -y

python3 -m venv aiops-venv
source aiops-venv/bin/activate
```

Install dependencies:

```bash
pip install flask requests msal
```
Below is a **standalone, production-ready README section** you can **directly paste** into your `README.md`.
It documents **Azure App Registration for Outlook (Microsoft Graph)** exactly as used in your AIOps POC, with **no assumptions** and **no skipped steps**.

---

## 🔹 Azure App Registration (Outlook / Microsoft Graph – Email Escalation)

This section explains how to create an **Azure App Registration** that allows the AIOps service to send **email alerts via Microsoft Graph** when alerts remain unresolved.

This app is used **only for email escalation**, not for Teams.

---

### 1️⃣ Create App Registration

1. Log in to **Azure Portal**
2. Navigate to:

```
Azure Active Directory → App registrations → New registration
```

3. Fill the details:

| Field                       | Value               |
| --------------------------- | ------------------- |
| **Name**                    | `AIOps-Mail-Sender` |
| **Supported account types** | Single tenant       |
| **Redirect URI**            | Leave empty         |

4. Click **Register**

---

### 2️⃣ Capture Application Details

After creation, note the following values (used later as environment variables):

| Azure Field                 | Used As           |
| --------------------------- | ----------------- |
| **Application (client) ID** | `GRAPH_CLIENT_ID` |
| **Directory (tenant) ID**   | `GRAPH_TENANT_ID` |

---

### 3️⃣ Create Client Secret

1. Go to:

```
Certificates & secrets → Client secrets → New client secret
```

2. Fill:

   * Description: `aiops-mail-secret`
   * Expiry: 90 days (or per policy)

3. Click **Add**

4. **Immediately copy the Value**
   ⚠️ You cannot retrieve it again

Used as:

```
GRAPH_CLIENT_SECRET
```

---

### 4️⃣ Configure Microsoft Graph API Permissions

1. Go to:

```
API permissions → Add a permission → Microsoft Graph
```

2. Select:

```
Application permissions
```

3. Add:

```
Mail.Send
```

4. Click **Add permissions**

---

### 5️⃣ Grant Admin Consent (Mandatory)

1. In **API permissions**
2. Click:

```
Grant admin consent for <Tenant Name>
```

3. Ensure status shows:

```
Granted for <Tenant>
```

⚠️ Without admin consent, emails **will always fail (403)**.

---

### 6️⃣ Assign Mailbox to Send From

Decide which mailbox will send escalation emails.

Example:

```
alerts@company.com
```

This value is used as:

```
EMAIL_FROM
```

Recipient email:

```
EMAIL_TO
```

---

### 7️⃣ Required Environment Variables

Add the following to your **systemd service** or shell environment:

```bash
GRAPH_TENANT_ID=<tenant-id>
GRAPH_CLIENT_ID=<client-id>
GRAPH_CLIENT_SECRET=<client-secret>

EMAIL_FROM=alerts@company.com
EMAIL_TO=your.email@company.com
```

---

### 8️⃣ Verify Token Generation (Optional Manual Test)

Run from EC2 to verify authentication:

```bash
curl -X POST \
  https://login.microsoftonline.com/<TENANT_ID>/oauth2/v2.0/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=<CLIENT_ID>" \
  -d "scope=https://graph.microsoft.com/.default" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "grant_type=client_credentials"
```

Expected result:

```json
{
  "access_token": "eyJ0eXAiOiJKV1Qi..."
}
```

---

### 9️⃣ How AIOps Uses This App

| Event                      | Action                         |
| -------------------------- | ------------------------------ |
| Alert triggered            | Timer started                  |
| Alert unresolved (10 mins) | Email sent via Microsoft Graph |
| Alert resolved             | No email                       |

---

### ⚠️ Known Limitations

* Email failures return **403** if:

  * Admin consent missing
  * Mailbox not licensed
  * App secret expired
* App-only Graph permissions **cannot read inbox**
* This app is **not used for Teams notifications**

---

## 🔹 Step 2: Environment Variables

Create environment file:

```bash
sudo nano /etc/aiops.env
```

```ini
CORALOGIX_API_KEY=xxxxxxxx
CORALOGIX_API_BASE=https://api.ap1.coralogix.com

TEAMS_WEBHOOK_URL=https://<power-automate-webhook-url>

GRAPH_TENANT_ID=xxxxxxxx
GRAPH_CLIENT_ID=xxxxxxxx
GRAPH_CLIENT_SECRET=xxxxxxxx

EMAIL_FROM=alerts@company.com
EMAIL_TO=alerts@company.com
```

---

## 🔹 Step 3: AIOps Flask Engine

The Flask service listens on:

```
POST /coralogix/webhook
```

Handles:

* `TRIGGERED` → start monitoring
* `RESOLVED` → send to Teams immediately
* Timeout → email escalation

Service runs on **port 5000**.

---

## 🔹 Step 4: systemd Service

Create service:

```bash
sudo nano /etc/systemd/system/aiops.service
```

```ini
[Unit]
Description=AIOps Coralogix Monitor
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/aiops-venv
EnvironmentFile=/etc/aiops.env
ExecStart=/home/ubuntu/aiops-venv/bin/python /home/ubuntu/aiops-venv/aiops_webhook.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable & start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable aiops.service
sudo systemctl start aiops.service
```

Verify:

```bash
sudo systemctl status aiops.service
```

---

## 🔹 Step 5: Manual Testing (Local)

### Health Check

```bash
curl http://localhost:5000/health
```

Expected:

```json
{"status":"ok"}
```

### Trigger Alert

```bash
curl -X POST http://localhost:5000/coralogix/webhook \
-H "Content-Type: application/json" \
-d '{
  "alert_id": "test-xx",
  "alert_name": "CPU Spike Test",
  "alert_action": "TRIGGERED"
}'
```
<img width="1919" height="493" alt="Screenshot 2026-01-19 153626" src="https://github.com/user-attachments/assets/755f28a3-dbd8-4a37-ae70-8a797705e944" />



### Resolve Alert

```bash
curl -X POST http://localhost:5000/coralogix/webhook \
-H "Content-Type: application/json" \
-d '{
  "alert_id": "test-xx",
  "alert_name": "CPU Spike Test",
  "alert_action": "RESOLVED"
}'
```
<img width="1919" height="456" alt="Screenshot 2026-01-19 153715" src="https://github.com/user-attachments/assets/2c84b807-b7be-476c-b5bd-30acecd37c3b" />

<img width="1343" height="479" alt="Screenshot 2026-01-19 153701" src="https://github.com/user-attachments/assets/9a08b546-f7b9-488f-9705-11df2bdbf754" />


---

## 🔹 Step 6: Cloudflare Tunnel (HTTPS)

Coralogix requires **public HTTPS endpoints**.

### Install Cloudflared

```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
```

### Start Tunnel

```bash
cloudflared tunnel --url http://localhost:5000
```

You will receive a URL like:

```
https://random-name.trycloudflare.com
```

Webhook endpoint becomes:

```
https://random-name.trycloudflare.com/coralogix/webhook
```

---

## 🔹 Step 7: Coralogix → AWS Integration

1. Coralogix → **Integrations**
2. Choose **AWS CloudWatch Metrics**
3. Provide AWS Account ID & Region
<img width="1771" height="1043" alt="Screenshot 2026-01-19 131945" src="https://github.com/user-attachments/assets/acbdf3fa-2647-4a51-9217-34c8700426a8" />
<img width="1659" height="679" alt="Screenshot 2026-01-19 132012" src="https://github.com/user-attachments/assets/dc81f94c-210f-45ae-ada8-35c942cecc8c" />

4. Coralogix deploys **CloudFormation stack automatically**
<img width="1746" height="985" alt="Screenshot 2026-01-19 132026" src="https://github.com/user-attachments/assets/c1bf1651-56cf-4180-9667-5ac608af5020" />

5. Metrics visible in **Hosted Grafana**
<img width="1916" height="1040" alt="Screenshot 2026-01-17 173933" src="https://github.com/user-attachments/assets/517889d4-c347-4778-9819-e3d34bc53a07" />

✅ No manual metric streams created.

---

## 🔹 Step 8: Coralogix Metric Alert

Example condition:

* Metric: `AWS/EC2 CPUUtilization`
* Threshold: `> 20`
* Duration: `1 minute`
* Delay evaluation: `300 seconds`
* Required data: `100%`
* Notification: **Webhook only**

---

## 🔹 Step 9: Coralogix Webhook Body (FINAL)

Below is a **drop-in README section** you can **copy-paste exactly** into your existing `README.md`.
It is **only** for **creating the outbound webhook in Coralogix**, written in the same style as the rest of the doc and aligned with what you actually configured and tested.

---

## 🔹 Creating the Outbound Webhook in Coralogix

This section explains how to configure Coralogix to send alert events to the AIOps engine running on EC2 via **HTTPS (Cloudflare Tunnel)**.

---

### 1️⃣ Navigate to Outbound Webhooks

1. Log in to **Coralogix UI**
2. Go to:

```
Settings → Notifications → Outbound Webhooks
```

3. Click **Create Webhook**

---

### 2️⃣ Webhook Basic Details

Fill the fields as follows:

| Field            | Value                                     |
| ---------------- | ----------------------------------------- |
| **Name**         | `(Any name of choice)`                     |
| **Description**  | `Webhook for AIOps alert decision engine` |
| **Method**       | `POST`                                    |
| **Content Type** | `application/json`                        |
| **Timeout**      | `10 seconds`                              |
| **Retries**      | `3`                                       |

---

### 3️⃣ Endpoint URL (HTTPS – Mandatory)

Since Coralogix **does not support HTTP endpoints**, the webhook **must be HTTPS**.

Use the **Cloudflare Tunnel URL** created earlier:

```
https://<random-name>.trycloudflare.com/coralogix/webhook
```

Example:

```
https://experiencing-work-camel-proprietary.trycloudflare.com/coralogix/webhook
```
<img width="1355" height="524" alt="Screenshot 2026-01-19 140842" src="https://github.com/user-attachments/assets/17ca4dd2-69f2-49ff-9bfe-36e4f3a2e6c5" />
<img width="1313" height="376" alt="Screenshot 2026-01-19 140847" src="https://github.com/user-attachments/assets/c2403fd5-0b0f-4941-a842-e25c0ccc90bf" />


⚠️ **Important**

* `localhost`
* private IPs
* HTTP endpoints

❌ will NOT work in Coralogix.

---

### 4️⃣ Webhook Body (CRITICAL)

Paste **exactly** the following JSON in the **Body** section:

```json
{
  "alert_id": "$ALERT_ID",
  "alert_name": "$ALERT_NAME",
  "alert_action": "$ALERT_ACTION"
}
```
---

### 5️⃣ Save & Test Webhook

1. Click **Save**
2. Click **Test & Save**

Expected behavior:

* Coralogix sends a test POST request
* AIOps service logs:

    <img width="1794" height="333" alt="Screenshot 2026-01-17 172659" src="https://github.com/user-attachments/assets/84ef223a-e0ac-49f6-b181-8153b7fc2759" />

  ```
* Status shows **Webhook saved successfully**

If it fails:

* Verify Cloudflare tunnel is running
* Verify `/coralogix/webhook` route exists
* Verify HTTPS URL is reachable from the internet

---

### 6️⃣ Attach Webhook to Alert

1. Open your **Metric Alert**, set it as below:

   <img width="867" height="1023" alt="Screenshot 2026-01-19 162757" src="https://github.com/user-attachments/assets/a2e62ed1-cf54-4799-8f55-8b1583fe2fdc" />

   <img width="868" height="1027" alt="Screenshot 2026-01-19 162808" src="https://github.com/user-attachments/assets/faa81995-d192-4d98-96f6-d1190b4b5da3" />

(For testing purposes we have kept the threshold at 20%, in real scenarios keep it 80-85% or accordingly)

<img width="747" height="388" alt="Screenshot 2026-01-19 163117" src="https://github.com/user-attachments/assets/0d5a07d5-c837-4009-8584-0fe65e8dde33" />

Keep the delay alert evaluation as 300 secs, as there is a delay between AWS and Coralogix alert sending and receiving)


2. Go to **Notification Groups**

3. Select the created webhook:

   <img width="867" height="333" alt="image" src="https://github.com/user-attachments/assets/e66dcf5b-e4b0-4495-82f2-4a7a773f3e62" />

   ```

4. Set:

   Notify On: Triggered & Resolved

5. Save the alert


## 🔹 Step 10: Microsoft Teams Body 

Paste into **Power Automate → Message**:

```
🚨 Alert Update

Alert Name: @{triggerBody()?['alert_name']}
Alert ID: @{triggerBody()?['alert_id']}
Instance ID: @{triggerBody()?['instance_id']}
Status: @{triggerBody()?['alert_action']}
```
<img width="835" height="792" alt="image" src="https://github.com/user-attachments/assets/43e2e164-9a8b-4cf3-a184-b0f4021af547" />

---

## 🔹 Step 11: Generate Real Alert (CPU Spike)

```bash
stress-ng --cpu 2 --cpu-method matrixprod --timeout 600 --metrics-brief
```

Expected behavior:

* Alert triggered in Coralogix
  <img width="1917" height="1026" alt="Screenshot 2026-01-19 150040" src="https://github.com/user-attachments/assets/6b30647a-d2eb-4136-9cb1-0c79ea9a2b0e" />

* Webhook received by AIOps
  <img width="1919" height="290" alt="Screenshot 2026-01-19 143655" src="https://github.com/user-attachments/assets/efd87b20-21ee-481e-a71f-f4b8cc72b449" />

* If resolved → Teams message
  <img width="1280" height="514" alt="Screenshot 2026-01-19 153340" src="https://github.com/user-attachments/assets/d6247a4e-e77e-403b-912a-55e53997f903" />

* If not → Email escalation (Cannot happen due to insufficient permissions on Azure AD in our case, but reflected in logs as 403 Error)
  <img width="1919" height="481" alt="Screenshot 2026-01-17 163924" src="https://github.com/user-attachments/assets/7e108fbb-88d8-4abe-80a0-c15df7992649" />

  
---

## ✅ Final Outcome

| Scenario            | Result           |
| ------------------- | ---------------- |
| Short spike         | Teams only       |
| Sustained issue     | Email escalation |
| Noise reduction     | ✔                |
| Instance visibility | ✔                |

---

## ⚠️ Limitations

* Coralogix webhooks **cannot inject instance ID directly**
* Instance ID must exist as **metric label**
* Cloudflare quick tunnels are **non-persistent** (POC only)

---

## 📌 Next Enhancements

* Persistent Cloudflare tunnel
* Multi-instance alert grouping
* Severity-based routing
* Auto-enrichment (Instance Name, ASG, Owner)
