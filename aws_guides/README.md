# ☁️ AWS Cloud Mastery & Deployment Guides

Welcome to your hands-on training repository for deploying this Django application to AWS. These guides are structured to take you from core cloud infrastructure all the way to Kubernetes orchestration.

---

## 📚 Table of Contents

| Guide | Topic | Description |
| :--- | :--- | :--- |
| **[00. Prerequisites & IAM](00_AWS_PREREQUISITES_IAM.md)** | Cloud Security & Setup | IAM User, Access Keys, AWS CLI configuration, Free Tier cost controls. |
| **[01. Stage 1: Traditional Cloud](01_STAGE1_TRADITIONAL_EC2_RDS.md)** | EC2, VPC & RDS | Custom VPC, Subnets, Security Groups, RDS PostgreSQL, Gunicorn, Nginx, SSL. |
| **[02. Stage 2: Containerized Cloud](02_STAGE2_DOCKER_ECR_ECS.md)** | Docker & ECS Fargate | Multi-stage Dockerfile, Amazon ECR, Serverless containers on ECS / App Runner. |
| **[03. Stage 3: Automated CI/CD](03_STAGE3_GITHUB_ACTIONS_CICD.md)** | GitHub Actions + OIDC | Automated testing, ECR build/push, Zero-downtime rolling deployments without static keys. |
| **[04. Stage 4: Cloud Kubernetes](04_STAGE4_KUBERNETES_EKS.md)** | Amazon EKS & Helm | Deployments, Services, Ingress, ConfigMaps, Secrets, and EKS Cluster orchestration. |

---

## 🗺️ Architectural Progression

```mermaid
flowchart TD
    subgraph S1 ["Stage 1: Foundational Cloud (IaaS)"]
        VPC["AWS VPC (10.0.0.0/16)"]
        EC2["EC2 (Ubuntu 24.04)<br/>Nginx + Gunicorn"]
        RDS["AWS RDS PostgreSQL"]
        VPC --> EC2 --> RDS
    end

    subgraph S2 ["Stage 2: Containerization (CaaS)"]
        DOCKER["Production Docker Image"]
        ECR["Amazon ECR Registry"]
        ECS["AWS ECS Fargate / App Runner"]
        DOCKER --> ECR --> ECS
    end

    subgraph S3 ["Stage 3: CI/CD Automation"]
        GIT["Git Push main"]
        GHA["GitHub Actions + AWS OIDC"]
        AUTO["Auto Build, Test & Deploy"]
        GIT --> GHA --> AUTO
    end

    subgraph S4 ["Stage 4: Kubernetes (EKS)"]
        EKS["Amazon EKS Cluster"]
        PODS["Replicated Django Pods"]
        ING["ALB Ingress Controller"]
        EKS --> ING --> PODS
    end

    S1 --> S2 --> S3 --> S4
```

---

## 🚦 Recommended Next Step
Start with **[00_AWS_PREREQUISITES_IAM.md](00_AWS_PREREQUISITES_IAM.md)** to configure your IAM credentials and AWS CLI.
