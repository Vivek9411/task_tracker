# 🚀 03. Stage 3: CI/CD Pipeline Automation (GitHub Actions + AWS OIDC)

In Stage 3, we automate our entire deployment lifecycle. Every time you push code to GitHub:
1. Automated tests run.
2. The Docker image is built and tagged with the Git commit hash.
3. The image is pushed to Amazon ECR.
4. AWS ECS or App Runner updates automatically with zero downtime.

---

## 🔒 Security Best Practice: AWS IAM OIDC (No Static Keys!)

Traditional setups stored permanent `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in GitHub Secrets. If an attacker gains access to GitHub, your AWS account is compromised.

**The Modern Solution:** **OpenID Connect (OIDC)**. GitHub requests a temporary token from AWS, and AWS assumes a temporary IAM Role valid for 1 hour. No secrets stored in GitHub!

---

## Step 1: Configure AWS IAM OIDC for GitHub

Run these AWS CLI commands to configure OIDC:

```bash
# 1. Create OpenID Connect Provider for GitHub
aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd2d98bab03faadb97b34396831e3780aea1" \
    --region us-east-1

# 2. Get your Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_REPO="<YOUR-GITHUB-USERNAME>/<YOUR-REPO-NAME>"

# 3. Create IAM Role Trust Policy
cat <<EOF > github-trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
EOF

# 4. Create the IAM Role
aws iam create-role \
    --role-name github-actions-deploy-role \
    --assume-role-policy-document file://github-trust-policy.json

# 5. Attach ECR & ECS permissions
aws iam attach-role-policy \
    --role-name github-actions-deploy-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
    --role-name github-actions-deploy-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess
```

---

## Step 2: Create GitHub Actions Workflow

In your repo, create `.github/workflows/deploy.yml`:

```yaml
name: Build and Deploy to AWS

on:
  push:
    branches: [ "main" ]

permissions:
  id-token: write # Required for AWS OIDC authentication
  contents: read

env:
  AWS_REGION: ap-south-1
  ECR_REPOSITORY: task-tracker
  ECS_SERVICE: task-tracker-service
  ECS_CLUSTER: django-cluster

jobs:
  test:
    name: Run Unit Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Tests
        run: |
          python manage.py test

  build-and-deploy:
    name: Build Docker Image & Deploy
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/github-actions-deploy-role
          aws-region: ${{ env.AWS_REGION }}

      - name: Log in to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Deploy to Amazon ECS (Rolling Update)
        run: |
          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service ${{ env.ECS_SERVICE }} \
            --force-new-deployment \
            --region ${{ env.AWS_REGION }}
```

---

## Step 3: Add GitHub Repository Secret

In your GitHub repository:
1. Go to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
2. Click **New repository secret**.
3. Name: `AWS_ACCOUNT_ID`
4. Value: `<Your 12-digit AWS Account ID>`
5. Click **Add secret**.

Now, whenever you run `git push origin main`, GitHub Actions will run tests, build the Docker image, push it to ECR, and deploy it to AWS!
