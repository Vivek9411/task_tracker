# 🔐 00. AWS Prerequisites & IAM Security Setup

Before launching any resources on AWS, you must establish secure access and understand how identity management works.

---

## 1. What is AWS IAM (Identity and Access Management)?

IAM is the service that controls **who** can authenticate (sign in) and **what** they are authorized to do in your AWS account.

### The 4 Pillars of IAM:
1. **Root User:** The account creator's email and password. Total, unrestricted access.
   > ⚠️ **Golden Rule:** Never create Access Keys for Root. Never use Root for daily coding or deployments.
2. **IAM User:** A named identity with specific credentials (password for console, access keys for CLI/SDK).
3. **IAM Policy:** A JSON document granting or denying specific API actions (e.g. `ec2:DescribeInstances`).
4. **IAM Role:** A temporary identity that can be assumed by AWS services (like an EC2 instance reading S3) or external tools (like GitHub Actions via OIDC).

---

## 2. Step-by-Step: Create an IAM User for Development

1. Log into the AWS Console: [console.aws.amazon.com](https://console.aws.amazon.com/)
2. In the search bar at the top, type **IAM** and select it.
3. In the left navigation menu, click **Users** $\rightarrow$ **Create user**.
4. **User details:**
   * User name: `developer-cli`
   * Leave "Provide user access to the AWS Management Console" unchecked if you only want CLI access, or check it if you want to log in with this user on the web.
   * Click **Next**.
5. **Set permissions:**
   * Select **Attach policies directly**.
   * In the search box, search for: `AdministratorAccess`.
   * Check the box next to `AdministratorAccess` *(for training/learning; in production you would scope this down)*.
   * Click **Next** $\rightarrow$ **Create user**.
6. **Generate CLI Access Keys:**
   * Click on the user name (`developer-cli`) you just created.
   * Go to the **Security credentials** tab.
   * Scroll down to **Access keys** $\rightarrow$ Click **Create access key**.
   * Select **Command Line Interface (CLI)**.
   * Check the confirmation box at the bottom and click **Next**.
   * (Optional) Description tag: `developer-laptop-cli`.
   * Click **Create access key**.
   * ⚠️ **IMPORTANT:** Download the `.csv` file or copy both:
     * **Access Key ID** (e.g. `AKIAIOSFODNN7EXAMPLE`)
     * **Secret Access Key** (e.g. `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)

---

## 3. Configure the AWS CLI on Your Machine

Open your terminal in `/home/vivek/Desktop/django-project` and run:

```bash
aws configure
```

You will see 4 interactive prompts:

```text
AWS Access Key ID [None]: <PASTE YOUR ACCESS KEY ID>
AWS Secret Access Key [None]: <PASTE YOUR SECRET ACCESS KEY>
Default region name [None]: ap-south-1
Default output format [None]: json
```

> **Region recommendation:**
> - `ap-south-1` (Mumbai, India) - Lowest latency if you are in India.
> - `us-east-1` (N. Virginia, USA) - Largest region with earliest access to new AWS services.

---

## 4. Verify Your Configuration

Run the following command to verify that AWS CLI is authenticated:

```bash
aws sts get-caller-identity
```

### Expected Output:
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/developer-cli"
}
```

---

## 5. Cost Protection: Setup a $5 CloudWatch Billing Alert

To make sure you never get an unexpected bill:
1. In the AWS Console, search for **Billing and Cost Management**.
2. Go to **Billing Preferences** (or **Budgets**).
3. Enable **Receive Free Tier Usage Alerts** and **Receive Billing Alerts**.
4. In **AWS Budgets** $\rightarrow$ Click **Create budget**:
   * Budget Type: **Cost budget (Recommended)**.
   * Period: Monthly.
   * Budgeted amount: `$5.00`.
   * Alert threshold: 80% ($4.00) and 100% ($5.00).
   * Enter your email address to receive immediate alerts.
