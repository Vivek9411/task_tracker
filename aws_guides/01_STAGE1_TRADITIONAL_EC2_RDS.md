# 🖥️ 01. Stage 1: Traditional Cloud Deployment (EC2 + VPC + RDS + Nginx)

This guide walks you through deploying your Django app on an **AWS EC2 Ubuntu Virtual Server** connected to an **AWS RDS PostgreSQL** database inside a custom **Virtual Private Cloud (VPC)**.

---

## 🏗️ Architecture Diagram

```
Internet (Users)
      │
      ▼ (Port 80 / 443)
[Internet Gateway]
      │
      ▼
[AWS VPC: 10.0.0.0/16]
   │
   ├── Public Subnet (10.0.1.0/24)
   │     └── [EC2 Instance: Ubuntu 24.04]
   │           ├── Nginx (Reverse Proxy & Static Files)
   │           └── Gunicorn (Systemd Service) ──▶ Django WSGI App
   │
   └── Private Subnet (10.0.2.0/24 & 10.0.3.0/24)
         └── [AWS RDS PostgreSQL (db.t4g.micro)]
```

---

## Step 1: Networking Setup (VPC & Subnets)

1. Open AWS Console $\rightarrow$ Search **VPC**.
2. Click **Create VPC** $\rightarrow$ Select **VPC and more**:
   * Name tag: `django-vpc`
   * IPv4 CIDR block: `10.0.0.0/16`
   * Number of Availability Zones (AZs): `2`
   * Number of Public subnets: `2` (e.g., `10.0.1.0/24`, `10.0.2.0/24`)
   * Number of Private subnets: `2` (e.g., `10.0.10.0/24`, `10.0.11.0/24`)
   * NAT Gateways: **None** *(to avoid NAT Gateway hourly charges while learning)*
   * VPC Endpoints: None
   * Click **Create VPC**.

---

## Step 2: Security Groups (Virtual Firewalls)

Security groups act as stateful firewalls for EC2 and RDS.

### 1. Web Security Group (`web-sg`):
* Attach to: EC2 Instance
* **Inbound Rules:**
  * Type: `SSH` | Port: `22` | Source: `My IP` *(Never use 0.0.0.0/0 for SSH)*
  * Type: `HTTP` | Port: `80` | Source: `0.0.0.0/0` (Anywhere IPv4)
  * Type: `HTTPS` | Port: `443` | Source: `0.0.0.0/0` (Anywhere IPv4)
* **Outbound Rules:**
  * All traffic allowed (`0.0.0.0/0`).

### 2. Database Security Group (`db-sg`):
* Attach to: RDS PostgreSQL
* **Inbound Rules:**
  * Type: `PostgreSQL` | Port: `5432` | Source: `Custom` $\rightarrow$ select `web-sg` (Security Group ID).
  > 💡 **Why?** This ensures *only* your EC2 server can talk to PostgreSQL. The database is invisible to the public internet!

---

## Step 3: Provision AWS RDS (PostgreSQL)

1. Search **RDS** in AWS Console $\rightarrow$ **Databases** $\rightarrow$ Click **Create database**.
2. **Settings:**
   * Choose database creation method: **Standard create**
   * Engine type: **PostgreSQL**
   * Engine Version: `PostgreSQL 16`
   * Templates: **Free tier** *(Crucial to avoid charges)*
   * DB instance identifier: `task-tracker-db`
   * Master username: `postgres`
   * Master password: `<Choose a strong password>`
   * Instance configuration: `db.t4g.micro` or `db.t3.micro`
   * Storage: `20 GiB gp3` (Disable storage autoscaling)
   * Connectivity:
     * Virtual Private Cloud (VPC): `django-vpc`
     * Public access: **No**
     * VPC security group: Select existing $\rightarrow$ Choose `db-sg` (remove `default`)
   * Initial database name: `task_tracker`
3. Click **Create database** (Takes ~5 minutes to provision).

---

## Step 4: Launch EC2 Instance

1. Search **EC2** $\rightarrow$ **Instances** $\rightarrow$ **Launch instances**.
2. **Settings:**
   * Name: `django-app-server`
   * OS Image: **Ubuntu Server 24.04 LTS** (Free tier eligible)
   * Architecture: `64-bit (x86)`
   * Instance type: `t2.micro` or `t3.micro`
   * Key pair (login):
     * Click **Create new key pair**.
     * Name: `django-ec2-key`
     * Type: `RSA` | Format: `.pem`
     * Save the downloaded `.pem` file safely on your laptop!
   * Network settings:
     * VPC: `django-vpc`
     * Subnet: Select a **Public subnet** (e.g. `django-vpc-subnet-public1`)
     * Auto-assign public IP: **Enable**
     * Security groups: Select existing $\rightarrow$ Choose `web-sg`
   * Storage: `8 GiB gp3`
3. Click **Launch instance**.

---

## Step 5: Connect and Configure Ubuntu Server

On your local machine, set proper permissions on your `.pem` key:

```bash
chmod 400 ~/Downloads/django-ec2-key.pem
```

SSH into your server:
```bash
ssh -i ~/Downloads/django-ec2-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

Once inside Ubuntu, run the installation script:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev libpq-dev postgresql-client nginx git
```

---

## Step 6: Clone Code & Configure Virtualenv

```bash
cd /home/ubuntu
git clone <YOUR-GITHUB-REPO-URL> app
cd /home/ubuntu/app

# Create virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

Create production `.env`:
```bash
nano .env
```
Add:
```env
SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=<YOUR-EC2-PUBLIC-IP>,yourdomain.com
DB_NAME=task_tracker
DB_USER=postgres
DB_PASSWORD=<YOUR-RDS-PASSWORD>
DB_HOST=<YOUR-RDS-ENDPOINT.rds.amazonaws.com>
DB_PORT=5432
```

Run migrations and collect static files:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

---

## Step 7: Configure Gunicorn as a Systemd Service

Create systemd socket and service so Gunicorn runs in the background and restarts on server reboot:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Paste:
```ini
[Unit]
Description=gunicorn daemon for Django Task Tracker
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/app
ExecStart=/home/ubuntu/app/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          config.wsgi:application

[Install]
WantedBy=multi-user.target
```

Enable and start Gunicorn:
```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl status gunicorn
```

---

## Step 8: Configure Nginx as Reverse Proxy

Create Nginx site configuration:
```bash
sudo nano /etc/nginx/sites-available/task_tracker
```

Paste:
```nginx
server {
    listen 80;
    server_name <YOUR-EC2-PUBLIC-IP>;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /home/ubuntu/app;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

Enable site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/task_tracker /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Now open `http://<YOUR-EC2-PUBLIC-IP>` in your browser — your Django application is live on AWS!
