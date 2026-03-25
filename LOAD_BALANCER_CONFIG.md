# Load Balancer Configuration - Quick Reference

## For DevOps Engineer

---

## ✅ **Simple Answer: Single Backend, No Special Routing**

Your ALB only needs to forward **ALL traffic** to the Flask backend on port **5000**.  
No path-based routing needed - Flask handles all routing internally.

---

## 🎯 **ALB Target Group Configuration**

```yaml
Target Type: IP (for Fargate)
Protocol: HTTP
Port: 5000
VPC: <your-vpc>

Health Check:
  Protocol: HTTP
  Path: /health
  Port: traffic-port
  Interval: 30 seconds
  Timeout: 10 seconds
  Healthy threshold: 2
  Unhealthy threshold: 3
  Success codes: 200
```

---

## 🎯 **ALB Listener Configuration**

### HTTPS Listener (Port 443) - PRIMARY
```yaml
Protocol: HTTPS
Port: 443
SSL Certificate: <from ACM>
Default Action: Forward to target-group-backend
```

### HTTP Listener (Port 80) - REDIRECT
```yaml
Protocol: HTTP
Port: 80
Default Action: Redirect to HTTPS (port 443, status 301)
```

---

## 🎯 **Route 53 DNS**

```yaml
Type: A Record (Alias)
Name: axion.yourcompany.com
Alias Target: <ALB DNS Name>
Routing Policy: Simple
Evaluate Target Health: Yes
```

---

## 🔍 **Health Check Verification**

After deployment, test:

```bash
# Health check (ALB uses this)
curl https://axion.yourcompany.com/health
# Expected: {"status":"ok"}

# Test actual endpoint
curl https://axion.yourcompany.com/summary/today
# Expected: {"productive_sec":0,"non_productive_sec":0,...}
```

---

## 📊 **Key Endpoints (All Handled by Backend)**

| Endpoint | Purpose | Used By |
|----------|---------|---------|
| `/health` | ALB health check | Load Balancer |
| `/track` | Tracker data ingest | Desktop agents (1000+ users) |
| `/summary/today` | Productivity data | User dashboard |
| `/admin/dashboard` | Admin interface | Managers |

**No special routing rules needed** - just forward everything to backend.

---

## 🔐 **Security Groups**

### ALB Security Group
```yaml
Inbound:
  - Port 443 (HTTPS) from 0.0.0.0/0
  - Port 80 (HTTP) from 0.0.0.0/0

Outbound:
  - Port 5000 to ECS Security Group
```

### ECS Security Group
```yaml
Inbound:
  - Port 5000 from ALB Security Group ONLY

Outbound:
  - Port 5432 to RDS Security Group (database)
  - Port 443 to 0.0.0.0/0 (OIDC, external APIs)
```

---

## 📝 **Backend URL for Tracker MSI**

After deployment, use this URL for building the Windows MSI:

```
BACKEND_URL=https://axion.yourcompany.com
```

This goes into the GitHub Actions workflow input when building the MSI installer.

---

## 🚨 **CloudWatch Alarms to Set Up**

```yaml
1. TargetResponseTime > 1 second
2. HealthyHostCount < 1
3. HTTPCode_Target_5XX_Count > 10 in 5 minutes
4. UnHealthyHostCount > 0
```

---

## ✅ **That's It!**

**Single Rule:** ALB forwards all HTTPS traffic → Backend port 5000  
**Health Check:** `/health` returns `200 OK`  
**No complex routing needed**

The Flask application (Gunicorn) handles all the routing internally based on the request path.

---

**Questions?** Refer to:
- `DEPLOYMENT_AWS.md` (full deployment guide)
- `API_ROUTES.md` (complete API documentation)
