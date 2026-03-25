# Zinnia Axion - API Routes & Load Balancer Configuration

**Base URL:** `https://axion.yourcompany.com` (or your ALB DNS)  
**Backend Port:** `5000`  
**Health Check Endpoint:** `/health`

---

## Load Balancer Configuration

### 🔹 **Health Check Settings for ALB Target Group**

```yaml
Protocol: HTTP
Port: 5000
Path: /health
Interval: 30 seconds
Timeout: 10 seconds
Healthy threshold: 2
Unhealthy threshold: 3
Success codes: 200
```

**Health Check Response:**
```json
{
  "status": "ok"
}
```

---

## API Endpoint Categories

### 1️⃣ **Public Endpoints** (No Authentication)

| Method | Endpoint | Description | Used By |
|--------|----------|-------------|---------|
| `GET` | `/health` | Health check for ALB | Load Balancer |
| `GET` | `/summary/today?user_id=X` | Today's productivity summary | User Dashboard |
| `GET` | `/apps?user_id=X` | App breakdown for today | User Dashboard |
| `GET` | `/daily?days=7&user_id=X` | 7-day productivity trend | User Dashboard |
| `GET` | `/db-stats` | Database statistics | Monitoring |
| `GET` | `/dashboard/<user_id>` | Self-contained HTML dashboard | Legacy |
| `POST` | `/cleanup` | Purge old telemetry data | Maintenance |

---

### 2️⃣ **Tracker Endpoints** (Device Token Authentication)

| Method | Endpoint | Description | Used By |
|--------|----------|-------------|---------|
| `POST` | `/track` | Ingest telemetry events (batch) | Desktop Tracker Agent |
| `POST` | `/tracker/ingest` | Alternative ingest endpoint | Desktop Tracker Agent |

**Authentication:** Requires `X-Device-Token` header

**Request Example:**
```bash
curl -X POST https://axion.yourcompany.com/track \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: your-device-token" \
  -d '{
    "events": [
      {
        "user_id": "atharvat",
        "app_name": "Visual Studio Code",
        "window_title": "backend/app.py",
        "timestamp": "2026-03-24T10:30:00Z",
        "interactions": 15,
        "mouse_movement": 450
      }
    ]
  }'
```

---

### 3️⃣ **Admin Endpoints** (OIDC SSO Authentication)

| Method | Endpoint | Description | Used By |
|--------|----------|-------------|---------|
| `GET` | `/admin/login` | SSO login page | Admin Dashboard |
| `GET` | `/admin/callback` | OIDC callback | Admin Dashboard |
| `POST` | `/admin/logout` | Clear session | Admin Dashboard |
| `GET` | `/admin/dashboard` | Team-scoped dashboard | Admin Dashboard |
| `GET` | `/admin/me` | Current user info | Admin Dashboard |
| `GET` | `/admin/teams` | List all teams | Admin Dashboard |
| `GET` | `/admin/users` | List users in manager's team | Admin Dashboard |
| `GET` | `/admin/leaderboard` | Team productivity leaderboard | Admin Dashboard |
| `GET` | `/admin/user/<user_id>/non-productive-apps` | Non-prod apps for user | Admin Dashboard |
| `GET` | `/admin/user/<user_id>/app-breakdown` | Detailed app breakdown | Admin Dashboard |
| `DELETE` | `/admin/user/<user_id>` | Delete user and events | Admin Dashboard |
| `GET` | `/admin/tracker-status` | Tracker agent status | Admin Dashboard |
| `GET` | `/admin/audit-log` | Audit log entries | Compliance |
| `POST` | `/admin/device-tokens` | Create device token | Admin |
| `POST` | `/admin/device-tokens/<id>/revoke` | Revoke device token | Admin |
| `POST` | `/admin/device-tokens/<id>/rotate` | Rotate device token | Admin |
| `POST` | `/admin/users/<id>/assign_to_my_team` | Add user to team | Admin |
| `POST` | `/admin/users/<id>/remove_from_my_team` | Remove user from team | Admin |

**Authentication:** Requires session cookie from OIDC SSO login

---

## ALB Listener Rules Configuration

### **Rule 1: Health Check (Highest Priority)**
```yaml
IF path is /health
THEN forward to target-group-backend
Priority: 1
```

### **Rule 2: Admin Routes (SSO Protected)**
```yaml
IF path matches /admin/*
THEN forward to target-group-backend
Priority: 10
```

### **Rule 3: Tracker Ingest**
```yaml
IF path matches /track OR /tracker/*
THEN forward to target-group-backend
Priority: 20
```

### **Rule 4: All Other Routes (Default)**
```yaml
IF path is /*
THEN forward to target-group-backend
Priority: 100
```

---

## CORS Configuration

**Allowed Origins:**
- `https://axion.yourcompany.com` (production)
- `http://localhost:8501` (Streamlit dev - user dashboard)
- `http://localhost:8502` (Streamlit dev - admin dashboard)

**Allowed Methods:**
- `GET`, `POST`, `DELETE`, `OPTIONS`

**Allowed Headers:**
- `Content-Type`
- `X-Device-Token`
- `Authorization`

---

## Security Headers (ALB Response)

Add these headers at the ALB level:

```yaml
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Rate Limiting (Already Configured in Backend)

| Endpoint | Limit |
|----------|-------|
| `/track` | 100 requests/minute per IP |
| `/admin/*` | 60 requests/minute per IP |
| All others | 300 requests/minute per IP |

---

## Base URL Examples for Different Environments

### Production
```
Base URL: https://axion.yourcompany.com
Health: https://axion.yourcompany.com/health
Tracker: https://axion.yourcompany.com/track
Admin: https://axion.yourcompany.com/admin/dashboard
```

### Staging
```
Base URL: https://axion-staging.yourcompany.com
Health: https://axion-staging.yourcompany.com/health
Tracker: https://axion-staging.yourcompany.com/track
Admin: https://axion-staging.yourcompany.com/admin/dashboard
```

### Development (Local)
```
Base URL: http://localhost:5000
Health: http://localhost:5000/health
Tracker: http://localhost:5000/track
Admin: http://localhost:5000/admin/dashboard
```

---

## Example: Desktop Tracker Configuration

After ALB deployment, update tracker `.env`:

```env
# Production Backend URL (from ALB + Route 53)
BACKEND_URL=https://axion.yourcompany.com

# User credentials (auto-detected from Windows USERNAME)
LAN_ID=atharvat

# Tracker polling configuration
POLL_INTERVAL_SEC=10
BATCH_INTERVAL_SEC=60
```

---

## Example: Admin Dashboard Configuration

Update Streamlit `frontend/admin_dashboard.py`:

```python
# Production backend
BACKEND_URL = os.getenv("BACKEND_URL", "https://axion.yourcompany.com")
```

---

## Testing After Deployment

### 1. Test Health Endpoint
```bash
curl https://axion.yourcompany.com/health
# Expected: {"status":"ok"}
```

### 2. Test Summary Endpoint
```bash
curl https://axion.yourcompany.com/summary/today?user_id=atharvat
# Expected: {"productive_sec":0,"non_productive_sec":0,...}
```

### 3. Test Tracker Ingest (with device token)
```bash
curl -X POST https://axion.yourcompany.com/track \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_DEVICE_TOKEN" \
  -d '{"events":[{"user_id":"test","app_name":"Chrome","window_title":"test","timestamp":"2026-03-24T10:00:00Z","interactions":1,"mouse_movement":100}]}'
# Expected: {"status":"ok","events_inserted":1}
```

### 4. Test Admin Login (browser)
```
Navigate to: https://axion.yourcompany.com/admin/login
Should redirect to OIDC provider (Microsoft Azure AD)
```

---

## CloudWatch Metrics to Monitor

1. **ALB Metrics:**
   - `TargetResponseTime` (should be < 100ms)
   - `HTTPCode_Target_5XX_Count` (should be 0)
   - `HealthyHostCount` (should match desired tasks)
   - `RequestCount` (track traffic)

2. **ECS Metrics:**
   - `CPUUtilization` (should be < 80%)
   - `MemoryUtilization` (should be < 85%)

3. **Custom Metrics (from logs):**
   - `/track` request count
   - Database query time
   - Failed authentication attempts

---

## Troubleshooting

### Issue: 502 Bad Gateway
**Cause:** Backend container not responding  
**Fix:** Check ECS task logs, verify `/health` endpoint

### Issue: 504 Gateway Timeout
**Cause:** Request taking too long  
**Fix:** Check database performance, optimize queries

### Issue: 403 Forbidden (Admin routes)
**Cause:** OIDC not configured  
**Fix:** Set `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` in Secrets Manager

### Issue: Tracker can't connect
**Cause:** CORS or device token issue  
**Fix:** Verify `BACKEND_URL`, check `X-Device-Token` header

---

## Summary for DevOps Engineer

**Primary Information Needed:**

1. **Health Check Path:** `/health`
2. **Backend Port:** `5000`
3. **Protocol:** HTTP (ALB handles HTTPS termination)
4. **Success Code:** `200`
5. **All traffic:** Forward to backend on port `5000`

**No special routing needed** - all endpoints are handled by the Flask application internally. ALB just needs to forward all traffic to the backend target group.

---

**Contact:** For questions, contact the backend team or refer to `DEPLOYMENT_AWS.md`
