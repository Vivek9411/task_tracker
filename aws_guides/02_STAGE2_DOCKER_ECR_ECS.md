# 🐳 02. Stage 2: Containerized Deployment (Docker + Amazon ECR + AWS ECS Fargate)

In Stage 2, we containerize our Django application so that it runs identically on your laptop, on AWS ECS, and on Kubernetes, with no manual server configuration.

---

## 🏗️ Architecture Diagram

```
Developer Laptop
      │ (docker build & push)
      ▼
[Amazon ECR (Private Docker Registry)]
      │ (pull image)
      ▼
[AWS ECS Cluster (Fargate Serverless)]
      ├── Task (Container 1: Django + Gunicorn)
      └── Task (Container 2: Django + Gunicorn)
            │ (Port 5432)
            ▼
[AWS RDS PostgreSQL (Private Subnet)]
```

---

## Step 1: Create Production Dockerfile & .dockerignore

Create `.dockerignore` to prevent uploading unnecessary files:
```text
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
.git
.gitignore
db.sqlite3
*.log
.env
.vscode/
.idea/
```

Create multi-stage production `Dockerfile`:
```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
RUN pip install --no-cache-dir --user gunicorn psycopg2-binary

# Stage 2: Runtime image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
COPY . /app

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "config.wsgi:application"]
```

---

## Step 2: Test Locally with Docker

Build the Docker image locally:
```bash
docker build -t task-tracker:latest .
```

Run the container locally:
```bash
docker run -d -p 8000:8000 --env-file .env task-tracker:latest
```

Verify in browser at `http://localhost:8000`. Stop the container when verified:
```bash
docker ps
docker stop <container_id>
```

---

## Step 3: Create Amazon ECR (Elastic Container Registry)

Amazon ECR is your private Docker image registry on AWS.

Run this AWS CLI command to create an ECR repository:
```bash
aws ecr create-repository \
    --repository-name task-tracker \
    --image-scanning-configuration scanOnPush=true \
    --region ap-south-1
```

Get your AWS Account ID:
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-south-1"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/task-tracker"
echo "ECR URI: $ECR_URI"
```

---

## Step 4: Authenticate Docker and Push to ECR

1. Log in to your private ECR registry:
```bash
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
```

2. Tag your local image with the ECR repository URI:
```bash
docker tag task-tracker:latest ${ECR_URI}:latest
```

3. Push the image to AWS:
```bash
docker push ${ECR_URI}:latest
```

---

## Step 5: Deploy with AWS App Runner (Fastest & Simplest)

AWS App Runner is a fully managed service that takes your container image and provides:
* Automatic HTTPS URL
* Auto-scaling
* Built-in load balancing

1. Search **App Runner** in AWS Console $\rightarrow$ Click **Create service**.
2. **Source:**
   * Repository type: **Container registry**
   * Provider: **Amazon ECR**
   * Container image URI: Click **Browse** and select `task-tracker:latest`.
   * Deployment trigger: **Automatic** *(deploys new version whenever a new image is pushed!)*
3. **ECR access role:**
   * Select **Create new service role** (or select existing AppRunner role).
4. **Configure service:**
   * Service name: `task-tracker-service`
   * Virtual CPU & Memory: `1 vCPU`, `2 GB`
   * Environment variables: Add your `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=*`, and RDS credentials (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`).
   * Port: `8000`.
5. Click **Next** $\rightarrow$ **Create & deploy**.

App Runner will deploy your container and provide a live URL like `https://xxxxxx.ap-south-1.awsapprunner.com`.

---

## Step 6: Deploy with AWS ECS Fargate (Enterprise Standard)

If you prefer full control over VPC networking:
1. Search **ECS (Elastic Container Service)**.
2. **Create Cluster:** Choose **AWS Fargate (serverless)** $\rightarrow$ Name: `django-cluster`.
3. **Create Task Definition:**
   * Infrastructure: `AWS Fargate`
   * Container Name: `web`
   * Image URI: `${ECR_URI}:latest`
   * Port mapping: `8000` (HTTP)
   * Environment variables: Enter RDS and Django config.
4. **Create Service:**
   * Launch type: `FARGATE`
   * Desired tasks: `2` (for high availability)
   * Networking: Select `django-vpc`
   * Load Balancer: Create an **Application Load Balancer (ALB)** listening on Port 80, forwarding to Target Group on Port 8000.
