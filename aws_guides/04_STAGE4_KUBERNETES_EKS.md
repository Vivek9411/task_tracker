# ☸️ 04. Stage 4: Cloud Kubernetes Orchestration (Amazon EKS)

In Stage 4, we step into enterprise orchestration with **Amazon EKS (Elastic Kubernetes Service)**.

---

## 🏗️ Architecture Diagram

```
Internet (Users)
      │
      ▼
[AWS Application Load Balancer (ALB)]
      │
      ▼ (Ingress Controller)
[Amazon EKS Cluster]
   ├── Namespace: production
   │     ├── Service (ClusterIP: Port 8000)
   │     │     ├── Pod 1: Django Container [Active]
   │     │     ├── Pod 2: Django Container [Active]
   │     │     └── Pod 3: Django Container [Active]
   │     ├── ConfigMap (Non-sensitive env vars)
   │     └── Secret (Database passwords, Secret keys)
   │
   └── Connects to RDS PostgreSQL outside the cluster (VPC)
```

---

## Step 1: Install Kubernetes Tools on Your Machine

```bash
# 1. Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
mv kubectl ~/.local/bin/

# 2. Install eksctl (Official CLI for Amazon EKS)
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
mv /tmp/eksctl ~/.local/bin/
```

Verify:
```bash
kubectl version --client
eksctl version
```

---

## Step 2: Create Amazon EKS Cluster

Create a 2-node managed Kubernetes cluster using `eksctl`:

```bash
eksctl create cluster \
  --name django-eks-cluster \
  --region ap-south-1 \
  --nodegroup-name standard-workers \
  --node-type t3.small \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3 \
  --managed
```
*(This sets up the VPC, subnets, control plane, and worker EC2 nodes automatically in ~15 minutes).*

Update your local `kubeconfig`:
```bash
aws eks update-kubeconfig --region ap-south-1 --name django-eks-cluster
kubectl get nodes
```

---

## Step 3: Create Kubernetes Manifests

In your repo, create a `k8s/` folder:

### 1. `k8s/configmap.yaml`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: django-config
data:
  DEBUG: "False"
  ALLOWED_HOSTS: "*"
  DB_PORT: "5432"
```

### 2. `k8s/secret.yaml`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: django-secret
type: Opaque
stringData:
  SECRET_KEY: "your-production-secret-key"
  DB_NAME: "task_tracker"
  DB_USER: "postgres"
  DB_PASSWORD: "your-rds-password"
  DB_HOST: "task-tracker-db.xxxxxx.ap-south-1.rds.amazonaws.com"
```

### 3. `k8s/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-app
  labels:
    app: django-app
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: django-app
  template:
    metadata:
      labels:
        app: django-app
    spec:
      containers:
      - name: django-container
        image: <YOUR-ACCOUNT-ID>.dkr.ecr.ap-south-1.amazonaws.com/task-tracker:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: django-config
        - secretRef:
            name: django-secret
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 10
```

### 4. `k8s/service.yaml`
```yaml
apiVersion: v1
kind: Service
metadata:
  name: django-service
spec:
  type: LoadBalancer # Automatically provisions an AWS Elastic Load Balancer
  selector:
    app: django-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
```

---

## Step 4: Deploy to EKS Cluster

Apply all manifests:
```bash
kubectl apply -f k8s/
```

Check rollout status:
```bash
kubectl get deployments
kubectl get pods
kubectl get service django-service
```

Under `EXTERNAL-IP`, you will see your AWS Load Balancer URL (e.g. `a74829xxxxxx.ap-south-1.elb.amazonaws.com`). Open that in your browser!

---

## Step 5: Kubernetes CI/CD Automation

Add this step to your GitHub Actions workflow (`.github/workflows/deploy.yml`):

```yaml
      - name: Update Kubeconfig
        run: |
          aws eks update-kubeconfig --region ${{ env.AWS_REGION }} --name django-eks-cluster

      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/django-app django-container=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          kubectl rollout status deployment/django-app
```
Now every `git push` performs a Kubernetes rolling rollout!
