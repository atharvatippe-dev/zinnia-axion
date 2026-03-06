# Zinnia Axion — AWS EC2 Deployment Guide (Level 3)

This guide deploys Zinnia Axion to an AWS EC2 instance with a fixed public IP, HTTPS, and PostgreSQL database. No ngrok tunnel required.

---

## Prerequisites

- AWS account (free tier eligible)
- A domain name (optional but recommended for HTTPS)
- SSH client (Terminal on macOS/Linux, PuTTY on Windows)

---

## Step 1: Launch EC2 Instance

### 1.1 Go to AWS Console
1. Log in to [AWS Console](https://console.aws.amazon.com)
2. Navigate to **EC2** → **Instances** → **Launch Instance**

### 1.2 Configure Instance
| Setting | Value |
|---------|-------|
| Name | `zinnia-axion-backend` |
| AMI | Ubuntu Server 22.04 LTS (Free tier eligible) |
| Instance type | `t3.micro` (free tier) or `t3.small` for production |
| Key pair | Create new or select existing (download the `.pem` file!) |

### 1.3 Network Settings
Click **Edit** and configure:
- **Auto-assign public IP**: Enable
- **Security group**: Create new with these rules:

| Type | Port | Source | Description |
|------|------|--------|-------------|
| SSH | 22 | My IP | SSH access |
| HTTP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | 443 | 0.0.0.0/0 | Secure web traffic |
| Custom TCP | 5000 | 0.0.0.0/0 | Flask API (temporary, remove after Nginx setup) |

### 1.4 Storage
- 20 GB gp3 (default is fine, increase if needed)

### 1.5 Launch
Click **Launch Instance** and wait for it to start.

---

## Step 2: Allocate Elastic IP (Fixed Public IP)

1. Go to **EC2** → **Elastic IPs** → **Allocate Elastic IP address**
2. Click **Allocate**
3. Select the new IP → **Actions** → **Associate Elastic IP address**
4. Select your instance → **Associate**

**Note your Elastic IP** (e.g., `54.123.45.67`) — this is your permanent backend URL.

---

## Step 3: Connect to Instance

```bash
# Make key readable
chmod 400 ~/Downloads/your-key.pem

# Connect via SSH
ssh -i ~/Downloads/your-key.pem ubuntu@YOUR_ELASTIC_IP
```

---

## Step 4: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, PostgreSQL, Nginx, and tools
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git certbot python3-certbot-nginx

# Verify installations
python3 --version   # Should be 3.10+
psql --version      # Should be 14+
nginx -v            # Should be 1.18+
```

---

## Step 5: Configure PostgreSQL

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user (run these in psql prompt)
CREATE USER telemetry_user WITH PASSWORD 'your_secure_password_here';
CREATE DATABASE telemetry_db OWNER telemetry_user;
GRANT ALL PRIVILEGES ON DATABASE telemetry_db TO telemetry_user;
\q
```

**Important:** Replace `your_secure_password_here` with a strong password. Save it — you'll need it for `.env`.

---

## Step 6: Clone and Configure Zinnia Axion

```bash
# Create app directory
sudo mkdir -p /opt/zinnia-axion
sudo chown ubuntu:ubuntu /opt/zinnia-axion
cd /opt/zinnia-axion

# Clone repository
git clone https://github.com/atharvatippe-dev/zinnia-axion.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

---

## Step 7: Configure Environment

```bash
# Copy example and edit
cp .env.example .env
nano .env
```

**Update these values in `.env`:**

```bash
# ─── Backend ───
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
DATABASE_URI=postgresql://telemetry_user:your_secure_password_here@localhost:5432/telemetry_db

# ─── Enterprise Hardening ───
DEMO_MODE=false
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<your_admin_password>

# ─── Timezone ───
TIMEZONE=Asia/Kolkata
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Step 8: Initialize Database

```bash
cd /opt/zinnia-axion
source venv/bin/activate

# Test database connection and create tables
python3 -c "
from backend.app import create_app
from backend.models import db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database tables created successfully!')
"
```

---

## Step 9: Create Systemd Service

```bash
sudo nano /etc/systemd/system/zinnia-axion.service
```

**Paste this content:**

```ini
[Unit]
Description=Zinnia Axion Backend API
After=network.target postgresql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/zinnia-axion
Environment="PATH=/opt/zinnia-axion/venv/bin"
ExecStart=/opt/zinnia-axion/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 "backend.app:create_app()"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Enable and start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable zinnia-axion
sudo systemctl start zinnia-axion

# Check status
sudo systemctl status zinnia-axion
```

---

## Step 10: Configure Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/zinnia-axion
```

**Paste this content:**

```nginx
server {
    listen 80;
    server_name YOUR_ELASTIC_IP;  # Or your domain name

    # Increase max body size for telemetry batches
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable the site:**

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/zinnia-axion /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Step 11: Set Up HTTPS (Optional but Recommended)

### Option A: With a Domain Name

If you have a domain (e.g., `axion.yourcompany.com`):

1. Point your domain's A record to your Elastic IP
2. Run Certbot:

```bash
sudo certbot --nginx -d axion.yourcompany.com
```

3. Follow the prompts. Certbot will automatically configure HTTPS.

### Option B: Without a Domain (Self-Signed)

For internal/testing use only:

```bash
# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/zinnia-axion.key \
    -out /etc/ssl/certs/zinnia-axion.crt \
    -subj "/CN=YOUR_ELASTIC_IP"
```

Update Nginx config to use HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name YOUR_ELASTIC_IP;

    ssl_certificate /etc/ssl/certs/zinnia-axion.crt;
    ssl_certificate_key /etc/ssl/private/zinnia-axion.key;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name YOUR_ELASTIC_IP;
    return 301 https://$host$request_uri;
}
```

---

## Step 12: Test the Deployment

```bash
# Test locally on the server
curl http://localhost:5000/health

# Test from your laptop (replace with your Elastic IP)
curl http://YOUR_ELASTIC_IP/health

# Test with HTTPS (if configured)
curl https://YOUR_ELASTIC_IP/health --insecure  # --insecure only for self-signed
```

Expected response:
```json
{"status": "ok"}
```

---

## Step 13: Update Tracker Installers

Now update the installer build config to use your new permanent URL.

### For Windows Installer

Edit `installer/windows/build_config.py`:

```python
BACKEND_URL = "https://YOUR_ELASTIC_IP"  # Or https://axion.yourcompany.com
```

### For macOS Installer

Edit `installer/mac/build_config.py`:

```python
BACKEND_URL = "https://YOUR_ELASTIC_IP"  # Or https://axion.yourcompany.com
```

Rebuild the installers and distribute to users.

---

## Step 14: Run Streamlit Dashboards

You can run the dashboards on your local machine (they connect to the remote backend):

```bash
# On your laptop, update .env
API_BASE_URL=https://YOUR_ELASTIC_IP

# Run admin dashboard
streamlit run frontend/admin_dashboard.py --server.port 8502

# Run user dashboard
streamlit run frontend/dashboard.py --server.port 8501
```

Or deploy dashboards on the same server (advanced — requires additional Nginx config).

---

## Maintenance Commands

```bash
# View logs
sudo journalctl -u zinnia-axion -f

# Restart service
sudo systemctl restart zinnia-axion

# Update code
cd /opt/zinnia-axion
git pull
sudo systemctl restart zinnia-axion

# Check database
sudo -u postgres psql -d telemetry_db -c "SELECT COUNT(*) FROM telemetry_event;"
```

---

## Security Checklist

- [ ] Changed default PostgreSQL password
- [ ] Set strong `SECRET_KEY` in `.env`
- [ ] Set strong `ADMIN_PASSWORD` in `.env`
- [ ] Set `DEMO_MODE=false`
- [ ] HTTPS enabled (Let's Encrypt or self-signed)
- [ ] Security group restricts SSH to your IP only
- [ ] Removed port 5000 from security group after Nginx setup

---

## Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| EC2 t3.micro (free tier first year) | $0 - $8.50 |
| Elastic IP (when attached) | $0 |
| Storage (20GB gp3) | ~$1.60 |
| Data transfer (moderate) | ~$1-5 |
| **Total** | **~$3-15/month** |

---

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u zinnia-axion -n 50
```

### Database connection error
```bash
# Test connection
psql -h localhost -U telemetry_user -d telemetry_db
```

### Nginx 502 Bad Gateway
```bash
# Check if backend is running
sudo systemctl status zinnia-axion
curl http://127.0.0.1:5000/health
```

### Trackers not connecting
1. Verify security group allows inbound on port 80/443
2. Check tracker's `BACKEND_URL` matches your Elastic IP
3. Test with curl from tracker machine

---

*Guide created: 2026-02-24*
