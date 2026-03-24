# AWS ECS Deployment Guide for DevOps Engineer

**Project:** Zinnia Axion - Enterprise Productivity Intelligence Platform  
**Component:** Flask + Gunicorn Backend API  
**Target:** AWS ECS Fargate with ALB + Route 53  

---

## Quick Overview

Deploy a Flask + Gunicorn backend to AWS ECS that:
- Handles 1000-2000+ simultaneous users
- Receives telemetry data from desktop tracker agents
- Serves admin and user dashboards
- Uses PostgreSQL for data storage
- Provides HTTPS via Application Load Balancer
- Accessible via custom domain (replaces ngrok)

---

## Architecture

```
Employee Laptops (Windows/macOS/Linux)
    ↓ HTTPS (every 60s)
Application Load Balancer (ALB)
    ├─ HTTPS Listener (443)
    ├─ SSL Certificate (ACM)
    └─ Health Check: /health
    ↓
ECS Service (Fargate)
    ├─ Task Definition: zinnia-axion-backend
    ├─ Desired Count: 2 (for high availability)
    ├─ Container: Flask + Gunicorn (8 workers)
    └─ Port: 5000
    ↓
RDS PostgreSQL
    ├─ Version: 15
    ├─ Instance: db.t4g.medium (or larger)
    └─ Storage: 100 GB (with auto-scaling)

Route 53
    └─ A Record: axion.yourcompany.com → ALB
```

---

## Prerequisites

### AWS Resources Needed:

- [x] AWS Account with appropriate IAM permissions
- [x] VPC with public and private subnets
- [x] ECR repository for Docker images
- [x] RDS PostgreSQL instance
- [x] Route 53 hosted zone for your domain

### IAM Permissions Required:

- ECS (Full access)
- ECR (Push/Pull images)
- RDS (Create/Manage)
- Route 53 (Manage DNS)
- ACM (Certificate Manager)
- Secrets Manager (Create/Read secrets)
- CloudWatch Logs (Create/Write)
- EC2 (Security groups, Load balancers)

---

## Deployment Steps

### Step 1: Build and Push Docker Image

```bash
# 1. Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# 2. Build Docker image
docker build -t zinnia-axion-backend .

# 3. Tag image
docker tag zinnia-axion-backend:latest \
  YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/zinnia-axion:latest

# 4. Push to ECR
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/zinnia-axion:latest
```

**Expected build time:** 2-3 minutes  
**Image size:** ~200-300 MB

---

### Step 2: Create RDS PostgreSQL Database

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier zinnia-axion-db \
  --db-instance-class db.t4g.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username telemetry_admin \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 100 \
  --storage-type gp3 \
  --backup-retention-period 7 \
  --vpc-security-group-ids sg-YOUR_RDS_SG \
  --db-subnet-group-name your-db-subnet-group \
  --no-publicly-accessible \
  --storage-encrypted

# Wait for DB to be available (5-10 minutes)
aws rds wait db-instance-available \
  --db-instance-identifier zinnia-axion-db

# Get endpoint
aws rds describe-db-instances \
  --db-instance-identifier zinnia-axion-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text
```

**Output:** `zinnia-axion-db.abc123.us-east-1.rds.amazonaws.com`

**Create database and user:**
```bash
# Connect to RDS
psql -h zinnia-axion-db.abc123.us-east-1.rds.amazonaws.com \
     -U telemetry_admin -d postgres

# Run in psql:
CREATE DATABASE telemetry_db;
CREATE USER telemetry_user WITH PASSWORD 'telemetry_pass';
GRANT ALL PRIVILEGES ON DATABASE telemetry_db TO telemetry_user;
\q
```

**Database URI:**
```
postgresql://telemetry_user:telemetry_pass@zinnia-axion-db.abc123.us-east-1.rds.amazonaws.com:5432/telemetry_db
```

---

### Step 3: Store Secrets in AWS Secrets Manager

```bash
# Create secret for database credentials
aws secretsmanager create-secret \
  --name zinnia-axion/database \
  --secret-string '{
    "username": "telemetry_user",
    "password": "telemetry_pass",
    "host": "zinnia-axion-db.abc123.us-east-1.rds.amazonaws.com",
    "port": "5432",
    "database": "telemetry_db"
  }'

# Create secret for application
aws secretsmanager create-secret \
  --name zinnia-axion/app \
  --secret-string '{
    "SECRET_KEY": "GENERATE_RANDOM_64_CHAR_STRING_HERE",
    "OIDC_CLIENT_ID": "your-oidc-client-id",
    "OIDC_CLIENT_SECRET": "your-oidc-client-secret"
  }'
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

### Step 4: Create ECS Task Definition

**Create a task definition JSON file:**

Create a file named `task-definition.json` with the following content:

```json
{
  "family": "zinnia-axion-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/zinnia-axion:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "FLASK_HOST", "value": "0.0.0.0"},
        {"name": "FLASK_PORT", "value": "5000"},
        {"name": "GUNICORN_WORKERS", "value": "8"},
        {"name": "LOG_LEVEL", "value": "INFO"},
        {"name": "DEMO_MODE", "value": "false"},
        {"name": "POLL_INTERVAL_SEC", "value": "10"},
        {"name": "BATCH_INTERVAL_SEC", "value": "60"},
        {"name": "BUCKET_SIZE_SEC", "value": "60"},
        {"name": "CONFIDENCE_THRESHOLD", "value": "0.60"},
        {"name": "PRODUCTIVE_DOMINANT_RATIO", "value": "0.70"},
        {"name": "NON_PROD_DOMINANT_RATIO", "value": "0.6667"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URI",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:zinnia-axion/database:DATABASE_URI::"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:zinnia-axion/app:SECRET_KEY::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/zinnia-axion-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "backend"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 40
      }
    }
  ]
}
```

**Register task definition:**
```bash
aws ecs register-task-definition \
  --cli-input-json file://task-definition.json
```

---

### Step 5: Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name zinnia-axion-alb \
  --subnets subnet-PUBLIC_SUBNET_1 subnet-PUBLIC_SUBNET_2 \
  --security-groups sg-ALB_SECURITY_GROUP \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4

# Create target group
aws elbv2 create-target-group \
  --name zinnia-axion-tg \
  --protocol HTTP \
  --port 5000 \
  --vpc-id vpc-YOUR_VPC_ID \
  --target-type ip \
  --health-check-enabled \
  --health-check-protocol HTTP \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3

# Create HTTPS listener (requires SSL certificate)
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:ACCOUNT:loadbalancer/app/zinnia-axion-alb/ABC123 \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:ACCOUNT:targetgroup/zinnia-axion-tg/XYZ789

# Create HTTP listener (redirect to HTTPS)
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:ACCOUNT:loadbalancer/app/zinnia-axion-alb/ABC123 \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=redirect,RedirectConfig='{Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'
```

---

### Step 6: Request SSL Certificate (ACM)

```bash
# Request certificate
aws acm request-certificate \
  --domain-name axion.yourcompany.com \
  --validation-method DNS \
  --region us-east-1

# Get validation DNS records
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT_ID

# Add CNAME record to Route 53 for validation
# Wait for certificate to be issued (5-30 minutes)
```

---

### Step 7: Create ECS Service

```bash
# Create ECS cluster (if not exists)
aws ecs create-cluster --cluster-name zinnia-axion-cluster

# Create ECS service
aws ecs create-service \
  --cluster zinnia-axion-cluster \
  --service-name zinnia-axion-backend \
  --task-definition zinnia-axion-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-PRIVATE_SUBNET_1,subnet-PRIVATE_SUBNET_2],
    securityGroups=[sg-ECS_SECURITY_GROUP],
    assignPublicIp=DISABLED
  }" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:ACCOUNT:targetgroup/zinnia-axion-tg/XYZ789,containerName=backend,containerPort=5000" \
  --health-check-grace-period-seconds 60
```

---

### Step 8: Configure Route 53 DNS

```bash
# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names zinnia-axion-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

# Create Route 53 A record (alias to ALB)
aws route53 change-resource-record-sets \
  --hosted-zone-id YOUR_HOSTED_ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "axion.yourcompany.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "ALB_HOSTED_ZONE_ID",
          "DNSName": "'"$ALB_DNS"'",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

**Result:** `https://axion.yourcompany.com` → Points to your backend

---

### Step 9: Run Database Migrations

```bash
# Connect to ECS task and run migrations
aws ecs run-task \
  --cluster zinnia-axion-cluster \
  --task-definition zinnia-axion-backend:1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-PRIVATE_SUBNET_1],
    securityGroups=[sg-ECS_SECURITY_GROUP],
    assignPublicIp=ENABLED
  }" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["alembic", "upgrade", "head"]
    }]
  }'
```

Or use ECS Exec to run in existing task:
```bash
# Enable execute command on service first, then:
aws ecs execute-command \
  --cluster zinnia-axion-cluster \
  --task TASK_ID \
  --container backend \
  --interactive \
  --command "alembic upgrade head"
```

---

### Step 10: Verify Deployment

```bash
# Test health endpoint
curl https://axion.yourcompany.com/health
# Expected: {"status": "ok"}

# Test summary endpoint
curl https://axion.yourcompany.com/summary/today
# Expected: {"productive_sec": 0, "non_productive_sec": 0, ...}

# Check ECS service status
aws ecs describe-services \
  --cluster zinnia-axion-cluster \
  --services zinnia-axion-backend

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:ACCOUNT:targetgroup/zinnia-axion-tg/XYZ789
```

---

## Security Groups Configuration

### ALB Security Group

**Inbound:**
- Port 443 (HTTPS) from 0.0.0.0/0 (public internet)
- Port 80 (HTTP) from 0.0.0.0/0 (redirect to HTTPS)

**Outbound:**
- Port 5000 to ECS Security Group (backend)

### ECS Security Group

**Inbound:**
- Port 5000 from ALB Security Group only

**Outbound:**
- Port 5432 to RDS Security Group (database)
- Port 443 to 0.0.0.0/0 (for OIDC, external APIs)

### RDS Security Group

**Inbound:**
- Port 5432 from ECS Security Group only

**Outbound:**
- None needed

---

## Environment Variables

### Required (Set in ECS Task Definition):

```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
DATABASE_URI=postgresql://telemetry_user:PASSWORD@zinnia-axion-db.abc123.us-east-1.rds.amazonaws.com:5432/telemetry_db
SECRET_KEY=<from Secrets Manager>
GUNICORN_WORKERS=8
LOG_LEVEL=INFO
DEMO_MODE=false
```

### Optional (For OIDC SSO):

```env
OIDC_ISSUER_URL=https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
OIDC_CLIENT_ID=<from Azure AD>
OIDC_CLIENT_SECRET=<from Secrets Manager>
OIDC_REDIRECT_URI=https://axion.yourcompany.com/admin/callback
```

### Productivity Configuration:

```env
POLL_INTERVAL_SEC=10
BATCH_INTERVAL_SEC=60
BUCKET_SIZE_SEC=60
CONFIDENCE_THRESHOLD=0.60
PRODUCTIVE_DOMINANT_RATIO=0.70
NON_PROD_DOMINANT_RATIO=0.6667
```

---

## Resource Sizing

### For 1000 Simultaneous Users:

**ECS Task:**
- CPU: 2048 (2 vCPU)
- Memory: 4096 MB (4 GB)
- Workers: 8
- Desired Count: 2 (for HA)

**RDS:**
- Instance: db.t4g.medium (2 vCPU, 4 GB RAM)
- Storage: 100 GB (gp3)
- IOPS: 3000

**ALB:**
- Standard ALB (auto-scales)

### For 2000 Simultaneous Users:

**ECS Task:**
- CPU: 4096 (4 vCPU)
- Memory: 8192 MB (8 GB)
- Workers: 12
- Desired Count: 2-3

**RDS:**
- Instance: db.t4g.large (2 vCPU, 8 GB RAM)
- Storage: 200 GB (gp3)
- IOPS: 6000

---

## Cost Estimate (Monthly)

### For 1000 Users:

| Resource | Specs | Monthly Cost |
|----------|-------|--------------|
| ECS Fargate (2 tasks) | 2 vCPU, 4 GB each | ~$60 |
| RDS PostgreSQL | db.t4g.medium | ~$65 |
| ALB | Standard | ~$22 |
| Data Transfer | ~50 GB/month | ~$4 |
| CloudWatch Logs | 10 GB/month | ~$5 |
| **Total** | | **~$156/month** |

### For 2000 Users:

**~$280-320/month**

---

## Monitoring & Alerts

### CloudWatch Alarms to Create:

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name zinnia-backend-high-cpu \
  --alarm-description "Backend CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High memory alarm
aws cloudwatch put-metric-alarm \
  --alarm-name zinnia-backend-high-memory \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Target 5xx errors
aws cloudwatch put-metric-alarm \
  --alarm-name zinnia-backend-5xx-errors \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 60 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

---

## Testing Deployment

### 1. Health Check

```bash
curl https://axion.yourcompany.com/health
```

Expected:
```json
{"status": "ok"}
```

### 2. Test Tracker Connection

Update local `.env`:
```env
BACKEND_URL=https://axion.yourcompany.com
```

Run tracker:
```bash
python3 tracker/agent.py
```

Check backend logs:
```bash
aws logs tail /ecs/zinnia-axion-backend --follow
```

### 3. Load Test

```bash
# Install Apache Bench
brew install httpd

# Test with 100 concurrent requests
ab -n 1000 -c 100 https://axion.yourcompany.com/health

# Expected:
# - 100% success rate
# - < 100ms average response time
# - 0 failed requests
```

---

## Troubleshooting

### ECS Tasks Not Starting

```bash
# Check task logs
aws ecs describe-tasks \
  --cluster zinnia-axion-cluster \
  --tasks TASK_ARN

# Check stopped tasks
aws ecs list-tasks \
  --cluster zinnia-axion-cluster \
  --desired-status STOPPED
```

### Targets Unhealthy in ALB

```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn TARGET_GROUP_ARN

# Common issues:
# - Security group blocking port 5000
# - /health endpoint not responding
# - Task not fully started (check start period)
```

### Database Connection Errors

```bash
# Test DB connection from ECS task
aws ecs execute-command \
  --cluster zinnia-axion-cluster \
  --task TASK_ID \
  --container backend \
  --interactive \
  --command "/bin/bash"

# Inside container:
psql $DATABASE_URI -c "SELECT 1"
```

### DNS Not Resolving

```bash
# Check Route 53 record
nslookup axion.yourcompany.com

# Should return ALB DNS name
```

---

## Rollback Plan

If deployment fails:

```bash
# Update service to previous task definition
aws ecs update-service \
  --cluster zinnia-axion-cluster \
  --service zinnia-axion-backend \
  --task-definition zinnia-axion-backend:PREVIOUS_REVISION

# Or scale down to 0
aws ecs update-service \
  --cluster zinnia-axion-cluster \
  --service zinnia-axion-backend \
  --desired-count 0
```

---

## Post-Deployment

### 1. Update MSI Build Workflow

After backend is deployed and DNS is configured:

**Backend URL:** `https://axion.yourcompany.com`

Use this URL when building MSI on GitHub Actions.

### 2. Monitor for 24-48 Hours

- CloudWatch metrics (CPU, memory, requests)
- CloudWatch logs (errors, warnings)
- Target health in ALB
- Database connections

### 3. Scale as Needed

```bash
# Increase task count
aws ecs update-service \
  --cluster zinnia-axion-cluster \
  --service zinnia-axion-backend \
  --desired-count 3

# Update task CPU/memory
# (requires new task definition revision)
```

---

## Files Included for DevOps Engineer

### Docker Files:
- `Dockerfile` - Production-ready backend container
- `.dockerignore` - Files to exclude from Docker build

### Configuration Files (in repo):
- `wsgi.py` - WSGI entry point for Gunicorn
- `gunicorn_config.py` - Gunicorn production configuration
- `.env.example` - Environment variables reference

### Deployment Guide:
- `DEPLOYMENT_AWS.md` - This comprehensive guide

### Application Code:
- `backend/` - Flask application
- `migrations/` - Database migrations (Alembic)
- `requirements.txt` - Python dependencies

---

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (200 OK) |
| `/track` | POST | Tracker telemetry ingest |
| `/summary/today` | GET | Productivity summary |
| `/apps` | GET | App breakdown |
| `/daily` | GET | 7-day trend |
| `/admin/dashboard` | GET | Admin dashboard (SSO protected) |

---

## Expected Load (1000 Users)

- **Requests/sec:** 16.7 (very light)
- **Database writes:** 100 inserts/sec
- **Network bandwidth:** 0.47 Mbps
- **Storage growth:** ~2 GB/day (before archiving)

**Infrastructure is intentionally over-provisioned for headroom.**

---

## Questions for DevOps Engineer?

1. VPC and subnet IDs?
2. Existing RDS instance or create new?
3. Domain name for Route 53? (e.g., axion.yourcompany.com)
4. Existing hosted zone or create new?
5. OIDC/SSO integration needed immediately or later?
6. Preferred AWS region? (default: us-east-1)
7. CloudWatch log retention? (default: 30 days)
8. Backup retention for RDS? (default: 7 days)

---

## Support

For questions during deployment:
- Check: `SYSTEM_DESIGN_DOCUMENT.md` (comprehensive architecture)
- Check: `GUNICORN_INTEGRATION.md` (Gunicorn setup)
- Logs: CloudWatch Logs → `/ecs/zinnia-axion-backend`

---

**Ready for DevOps engineer to deploy!** 🚀
