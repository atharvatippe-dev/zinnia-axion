# SSO Login Setup — Complete Guide for Zinnia Axion

This document explains **everything** about setting up company SSO login for the
Zinnia Axion admin dashboard — from what to request from IT, to what happens at
every step inside the backend, to what security gaps still exist.

---

## Table of Contents

1. [Big Picture — How Login Works](#1-big-picture--how-login-works)
2. [Your Company's Login Flow (What You See)](#2-your-companys-login-flow-what-you-see)
3. [What IT Admin Needs to Do (Azure AD Setup)](#3-what-it-admin-needs-to-do-azure-ad-setup)
4. [What You Need to Do (.env Configuration)](#4-what-you-need-to-do-env-configuration)
5. [What Happens at the Backend (Every Single Step)](#5-what-happens-at-the-backend-every-single-step)
6. [Database Requirements — Manager Records](#6-database-requirements--manager-records)
7. [Endpoint Authentication Map](#7-endpoint-authentication-map)
8. [Security Features Built In](#8-security-features-built-in)
9. [What Can Go Wrong (Troubleshooting)](#9-what-can-go-wrong-troubleshooting)
10. [IT Admin Request Template](#10-it-admin-request-template)
11. [Team Hierarchy — How Managers See Only Their Team's Data](#11-team-hierarchy--how-managers-see-only-their-teams-data)

---

## 1. Big Picture — How Login Works

The login uses **OpenID Connect (OIDC)** — an industry standard protocol built
on top of OAuth 2.0. Your company's Azure AD acts as the **Identity Provider
(IdP)** and Zinnia Axion is the **Relying Party (RP)**.

```
Manager           Zinnia Axion          Azure AD (IdP)
  |                 (Flask)               (Microsoft)
  |                   |                      |
  |  1. Click         |                      |
  |  "Sign in with    |                      |
  |   SSO"            |                      |
  |------------------>|                      |
  |                   |                      |
  |  2. Redirect to   |                      |
  |  Azure AD with    |                      |
  |  client_id +      |                      |
  |  redirect_uri +   |                      |
  |  nonce + scopes   |                      |
  |<------------------|                      |
  |                                          |
  |  3. Company SAML page (ess.bdo.in)       |
  |  "Sign in with SAML" button              |
  |----------------------------------------->|
  |                                          |
  |  4. login.microsoftonline.com            |
  |  Shows your email, you enter password    |
  |  + MFA if configured                     |
  |<-----------------------------------------|
  |                                          |
  |  5. Azure AD validates credentials       |
  |  Generates authorization code            |
  |  Redirects to /admin/callback?code=...   |
  |----------------------------------------->|
  |                   |                      |
  |                   |  6. Backend exchanges |
  |                   |  code for ID token   |
  |                   |--------------------->|
  |                   |                      |
  |                   |  7. Azure returns    |
  |                   |  ID token (JWT)      |
  |                   |<---------------------|
  |                   |                      |
  |                   |  8. Backend validates |
  |                   |  token (signature,   |
  |                   |  nonce, expiry)      |
  |                   |                      |
  |                   |  9. Extracts email   |
  |                   |  from token          |
  |                   |                      |
  |                   |  10. Looks up User + |
  |                   |  Manager in DB       |
  |                   |                      |
  |                   |  11. Creates secure  |
  |                   |  session             |
  |                   |                      |
  |  12. Redirect to  |                      |
  |  Admin Dashboard  |                      |
  |<------------------|                      |
  |                   |                      |
  |  Manager sees     |                      |
  |  their team data  |                      |
```

---

## 2. Your Company's Login Flow (What You See)

Based on your company's setup, this is the exact user experience:

**Step 1 — Open Admin Dashboard**
You navigate to the Zinnia Axion admin dashboard URL. Since you're not logged
in, you see a "Sign in with SSO" button.

**Step 2 — Company SAML Page (ess.bdo.in / Ascent)**
Clicking the button redirects you to your company's identity broker page
(Ascent, powered by Eilisys). This is the page with the Zinnia logo and
"Sign-in with SAML" orange button.

**Step 3 — Microsoft Login Page (login.microsoftonline.com)**
After clicking "Sign-in with SAML", you're redirected to Microsoft's login
page. Your company email (e.g., atharva.tippe@zinnia.com) is pre-filled at the
top. You enter your password.

**Step 4 — MFA (if configured)**
If your company has MFA enabled, you complete the second factor (authenticator
app, SMS, etc.).

**Step 5 — Redirected Back to Dashboard**
Azure AD sends you back to Zinnia Axion with an authorization code. The backend
silently exchanges this for your identity, creates a session, and you land on
the admin dashboard seeing your team's data.

The entire process takes 5-10 seconds. After the first login, your session
lasts for 30 minutes (configurable).

---

## 3. What IT Admin Needs to Do (Azure AD Setup)

Your IT admin needs to do **6 things** in the Azure Portal. Send them the
template in Section 10.

### 3.1 — Register a New Application

1. Go to **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Click **New registration**
3. Fill in:
   - **Name**: `Zinnia Axion Admin`
   - **Supported account types**: "Accounts in this organizational directory
     only" (Single tenant)
   - **Redirect URI**: Platform = **Web**, URI = your callback URL:
     - Local development: `http://localhost:5000/admin/callback`
     - Production: `https://your-prod-domain.com/admin/callback`
4. Click **Register**

After creation, you'll see the **Overview** page with:
- **Application (client) ID** → this is `OIDC_CLIENT_ID`
- **Directory (tenant) ID** → used in `OIDC_ISSUER_URL`

### 3.2 — Create a Client Secret

1. Go to **Certificates & secrets** → **Client secrets**
2. Click **New client secret**
3. Description: `zinnia-axion-admin`
4. Expiry: Choose (recommended: 12 months, set a calendar reminder to rotate)
5. Click **Add**
6. **IMMEDIATELY copy the Value** (it's only shown once) → this is
   `OIDC_CLIENT_SECRET`

### 3.3 — Set API Permissions

1. Go to **API permissions**
2. Verify these Microsoft Graph permissions exist (they should by default):
   - `openid` — Allows sign-in
   - `profile` — Reads user's basic profile (name)
   - `email` — Reads user's email address
3. If any are missing, click **Add a permission** → **Microsoft Graph** →
   **Delegated permissions** → search and add them
4. Click **Grant admin consent for [Your Org]** (requires admin privileges)

### 3.4 — Add Email Claim to ID Token

By default, Azure AD may not include the `email` claim in the ID token. To
ensure it does:

1. Go to **Token configuration**
2. Click **Add optional claim**
3. Token type: **ID**
4. Select: `email`
5. Click **Add**
6. If prompted about Microsoft Graph permissions, check the box and click **Add**

### 3.5 — Assign Users to the Application

This is the step that controls WHO can log in. If this is not done, users get
the `AADSTS50105` error you saw.

1. Go to **Azure Portal** → **Enterprise applications** → search for
   `Zinnia Axion Admin`
2. Go to **Users and groups**
3. Click **Add user/group**
4. Select the managers who need admin dashboard access:
   - Individual users: `wasim.shaikh@zinnia.com`, `atharva.tippe@zinnia.com`,
     `nikhil.saxena@zinnia.com`
   - OR create a security group (e.g., "Zinnia Axion Managers") and add all
     managers to it
5. Click **Assign**

**Important**: If "User assignment required?" is set to **Yes** under
Properties, ONLY explicitly assigned users can log in. This is the recommended
setting for security.

### 3.6 — Provide Values Back to You

After completing the above, the IT admin needs to give you these 3 values:

| Value | Where to Find It | Example |
|-------|-------------------|---------|
| **Tenant ID** | App registration → Overview → Directory (tenant) ID | `a1b2c3d4-e5f6-...` |
| **Client ID** | App registration → Overview → Application (client) ID | `x1y2z3w4-a5b6-...` |
| **Client Secret** | Certificates & secrets → Value (copied in step 3.2) | `Abc123~xyz...` |

---

## 4. What You Need to Do (.env Configuration)

Once you have the 3 values from IT, update your `.env` file:

```bash
# ─── Disable Demo Mode ───
DEMO_MODE=false

# ─── Generate a strong secret key for sessions ───
# Run this to generate: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-64-char-hex-string-here

# ─── OIDC SSO Configuration ───
OIDC_ISSUER_URL=https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
OIDC_CLIENT_ID=your-client-id-from-azure
OIDC_CLIENT_SECRET=your-client-secret-from-azure
OIDC_REDIRECT_URI=http://localhost:5000/admin/callback
OIDC_SCOPES=openid profile email
```

Replace:
- `YOUR_TENANT_ID` with the Directory (tenant) ID
- `your-client-id-from-azure` with the Application (client) ID
- `your-client-secret-from-azure` with the Client Secret value

For production deployment, also update:
- `OIDC_REDIRECT_URI` to your production URL
- `SESSION_COOKIE_SECURE=true` (auto-set when DEMO_MODE=false)

---

## 5. What Happens at the Backend (Every Single Step)

Here is exactly what happens in the code when a manager logs in.

### Step 5.1 — Application Startup (`backend/auth/oidc.py`)

When Flask starts, `init_oidc(app)` runs:

```python
# backend/auth/oidc.py — init_oidc()

issuer_url = "https://login.microsoftonline.com/{tenant}/v2.0"

# Authlib fetches this URL automatically:
# https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration
#
# This returns a JSON document containing:
#   - authorization_endpoint (where to send the user to login)
#   - token_endpoint (where to exchange the code for tokens)
#   - jwks_uri (public keys to verify token signatures)
#   - issuer (expected issuer value in tokens)
#   - supported scopes, claims, etc.
#
# Authlib caches this metadata so it doesn't fetch it on every request.

oauth.register(
    name="oidc",
    server_metadata_url=metadata_url,        # The discovery URL above
    client_id="your-client-id",              # From Azure
    client_secret="your-client-secret",      # From Azure
    client_kwargs={"scope": "openid profile email"},
)
```

**What this does**: Authlib now knows everything about your Azure AD tenant —
where to send users, where to get tokens, and how to verify them. No manual
endpoint configuration needed.

### Step 5.2 — Manager Clicks "Sign in with SSO" (`GET /admin/login`)

```python
# backend/blueprints/admin.py — admin_login()

# 1. Generate a random nonce (one-time-use value to prevent replay attacks)
nonce = generate_nonce()  # e.g., "aB3x_Kz9m2..."

# 2. Store it in the server-side session
session["oidc_nonce"] = nonce

# 3. Redirect the browser to Azure AD's authorization endpoint
# The redirect URL looks like:
#   https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize
#     ?client_id=your-client-id
#     &redirect_uri=http://localhost:5000/admin/callback
#     &response_type=code
#     &scope=openid+profile+email
#     &nonce=aB3x_Kz9m2...
#     &state=random-csrf-token
return oauth.oidc.authorize_redirect(redirect_uri, nonce=nonce)
```

**What the nonce does**: The nonce is embedded in the ID token by Azure AD. When
the token comes back, Authlib checks that the nonce in the token matches the one
stored in the session. This prevents an attacker from replaying a stolen token.

**What the state parameter does**: Authlib automatically generates a `state`
parameter (a random value) and stores it in the session. On callback, it verifies
the state matches. This prevents CSRF attacks where an attacker tricks the
browser into completing someone else's login.

### Step 5.3 — Azure AD Login (Outside Our Control)

This happens entirely on Microsoft's servers:

1. User sees the company SAML page (ess.bdo.in / Ascent)
2. User clicks "Sign-in with SAML"
3. Redirected to login.microsoftonline.com
4. User's email is pre-filled (from browser cookies/SSO session)
5. User enters password
6. MFA challenge if configured
7. Azure AD validates credentials against the company directory
8. Azure AD checks if the user is assigned to the "Zinnia Axion Admin" app
   - If NOT assigned → `AADSTS50105` error (the error you saw)
   - If assigned → proceeds
9. Azure AD generates an **authorization code** (a short-lived, one-time token)
10. Redirects browser to: `http://localhost:5000/admin/callback?code=abc123&state=xyz`

### Step 5.4 — Callback: Code Exchange (`GET /admin/callback`)

```python
# backend/blueprints/admin.py — admin_callback()

# 1. Exchange the authorization code for tokens
#    Authlib sends a POST to Azure's token endpoint:
#      POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
#      Body: grant_type=authorization_code
#            &code=abc123
#            &redirect_uri=http://localhost:5000/admin/callback
#            &client_id=your-client-id
#            &client_secret=your-client-secret
#
#    This is a server-to-server call (browser never sees the client_secret)
token = oauth.oidc.authorize_access_token()
```

**Why the code exchange exists**: The authorization code itself is useless to an
attacker who intercepts the URL. It can only be exchanged for tokens by someone
who also has the `client_secret`. Since the exchange happens server-to-server,
the secret never leaves the backend.

### Step 5.5 — Token Validation

```python
# The token response contains:
# {
#   "access_token": "eyJ...",     # For calling Microsoft Graph APIs (not used)
#   "id_token": "eyJ...",         # The identity proof (JWT)
#   "token_type": "Bearer",
#   "expires_in": 3600,
# }

# 2. Extract user info from the ID token
nonce = session.pop("oidc_nonce", None)
userinfo = token.get("userinfo", {})

if not userinfo:
    # Parse and validate the ID token (JWT) manually
    userinfo = oauth.oidc.parse_id_token(token, nonce=nonce)
```

**What `parse_id_token` validates** (all done automatically by Authlib):

| Check | What It Verifies |
|-------|-----------------|
| **Signature** | The JWT is signed by Azure AD's private key. Authlib fetches the public keys from the JWKS endpoint and verifies the signature. If an attacker modifies the token, the signature breaks. |
| **Issuer (iss)** | The token was issued by `https://login.microsoftonline.com/{tenant}/v2.0`, not some other server. |
| **Audience (aud)** | The token was intended for YOUR application (matches your client_id), not some other app. |
| **Expiry (exp)** | The token has not expired. ID tokens typically expire in 1 hour. |
| **Not Before (nbf)** | The token is not being used before it's valid. |
| **Nonce** | The nonce in the token matches the one you stored in the session (prevents replay attacks). |

### Step 5.6 — Identity Resolution

```python
# 3. Extract the user's email from the validated token
email = (
    userinfo.get("email")                # Primary: email claim
    or userinfo.get("preferred_username") # Fallback: UPN (user@domain.com)
    or userinfo.get("upn")               # Fallback: on-prem UPN
    or ""
).strip().lower()

sub = userinfo.get("sub", "")  # Unique, immutable user ID from Azure AD

# 4. Look up the user in our database
user = User.query.filter(
    db.or_(User.email == email, User.lan_id == email)
).first()

# Fallback: try matching by Azure AD's sub claim
if not user and sub:
    user = User.query.filter_by(lan_id=sub).first()
```

**Three checks happen next:**

```python
# CHECK 1: Does this person exist in our system?
if not user:
    # ERROR: "Your account is not registered in the system."
    # The email from Azure AD doesn't match any User.email or User.lan_id
    return 403

# CHECK 2: Are they a manager or superadmin?
if user.role not in ("manager", "superadmin"):
    # ERROR: "You do not have admin access."
    # The user exists but their role is "user" (regular employee)
    return 403

# CHECK 3: Do they have a team assignment?
manager_record = Manager.query.filter_by(user_id=user.id).first()
if not manager_record:
    # ERROR: "No team assignment found for your account."
    # They're marked as a manager but don't have a Manager record with a team_id
    return 403
```

### Step 5.7 — Session Creation

```python
# 5. Create a secure server-side session
session.permanent = True  # Session lives for PERMANENT_SESSION_LIFETIME_MINUTES (default 30)
session["user_id"] = user.id              # Database ID of the manager
session["team_id"] = manager_record.team_id  # Their team (NEVER from client input)
session["role"] = user.role               # "manager" or "superadmin"
session["email"] = email                  # For display purposes
session["display_name"] = user.display_name or email

# 6. Audit log the successful login
log_action(user.lan_id, "admin_login_success", detail=f"team_id={manager_record.team_id}")

# 7. Redirect to the admin dashboard
return redirect(url_for("admin.admin_dashboard"))
```

**Session cookie settings** (from `backend/config.py`):

| Setting | Value | Purpose |
|---------|-------|---------|
| `SESSION_COOKIE_SECURE` | `True` (in production) | Cookie only sent over HTTPS, not HTTP |
| `SESSION_COOKIE_HTTPONLY` | `True` | JavaScript cannot read the cookie (prevents XSS theft) |
| `SESSION_COOKIE_SAMESITE` | `Lax` | Cookie not sent on cross-site requests (prevents CSRF) |
| `PERMANENT_SESSION_LIFETIME` | 30 minutes | Session expires after 30 min of inactivity |

### Step 5.8 — Every Subsequent Request

After login, every request to an admin endpoint goes through two decorators:

**`@admin_required`** (from `backend/auth/authz.py`):
```python
# 1. Check if user_id exists in session
user_id = session.get("user_id")
if not user_id:
    # Not logged in → redirect to /admin/login
    return redirect("/admin/login")

# 2. Look up the user in DB and verify role
user = db.session.get(User, user_id)
if not user or user.role not in ("manager", "superadmin"):
    abort(403)  # Forbidden

# 3. Set identity on the request context
g.current_user_id = user.id
g.current_team_id = session.get("team_id")
g.current_role = user.role
```

**`@team_scoped`** (from `backend/auth/authz.py`):
```python
# 4. Compute the manager's allowed team subtree
#    e.g., Wasim manages Lifecad → allowed = [Lifecad, Axion]
g.allowed_team_ids = get_allowed_team_ids(g.current_team_id)

# 5. If the URL references a specific team, verify it's in scope
if url_team_id not in g.allowed_team_ids:
    log_action(..., "cross_team_access_blocked", ...)
    abort(403)  # IDOR attempt blocked
```

---

## 6. Database Requirements — Manager Records

For SSO login to work, each manager needs these records in the database:

### User Record
```
users table:
  id:           1
  lan_id:       "atharva.tippe"         # Or the email prefix
  email:        "atharva.tippe@zinnia.com"  # MUST match Azure AD email
  display_name: "Atharva Tippe"
  role:         "manager"               # MUST be "manager" or "superadmin"
```

### Manager Record
```
managers table:
  id:      1
  user_id: 1        # Links to the User above
  team_id: 3        # The team this manager oversees
```

### Membership Record
```
memberships table:
  id:      1
  user_id: 1
  team_id: 3
  active:  true
```

**Critical**: The `email` field in the `users` table MUST match exactly what
Azure AD returns. If your Azure AD returns `atharva.tippe@zinnia.com`, the
User record must have `email = "atharva.tippe@zinnia.com"`.

---

## 7. Endpoint Authentication Map

### IMPORTANT: Current Security Status

| Endpoint Group | Auth in DEMO_MODE | Auth in Production | Status |
|----------------|-------------------|-------------------|--------|
| **Admin API** (`/admin/*`) | Session identity faked from DB | Full SSO session required | SECURE in production |
| **Tracker API** (`/track`, `/tracker/ingest`) | No auth (reads user_id from payload) | Bearer device token + X-LAN-ID required | SECURE in production |
| **Public API** (`/summary/today`, `/apps`, `/daily`, etc.) | **NO AUTH** | **NO AUTH** | SECURITY GAP |
| **Health** (`/health`) | No auth | No auth | Intentional (monitoring) |

### Public Endpoints — Security Gap

These endpoints have **NO authentication regardless of mode**:

| Endpoint | Method | Risk |
|----------|--------|------|
| `/summary/today` | GET | Anyone can read productivity summaries |
| `/apps` | GET | Anyone can see app breakdown data |
| `/daily` | GET | Anyone can see daily trends |
| `/cleanup` | POST | **CRITICAL: Anyone can DELETE old events** |
| `/db-stats` | GET | Anyone can see database size info |
| `/dashboard/<user_id>` | GET | Anyone can see a user's full dashboard |

**Impact**: If the backend is exposed to the internet (e.g., via ngrok or a
public deployment), anyone who knows the URL can read all productivity data and
even delete events.

**Recommendation**: Before production deployment, either:
1. Add authentication to public endpoints (require a valid session or API key)
2. Restrict the backend to only be accessible from the internal network/VPN
3. Use a reverse proxy (nginx) to block public endpoints from external access

---

## 8. Security Features Built In

### Authentication
- OIDC Authorization Code Flow (industry standard)
- JWKS signature validation on ID tokens
- Nonce-based replay attack prevention
- State parameter for CSRF protection during login
- Session cookie hardening (Secure, HttpOnly, SameSite=Lax)
- 30-minute session timeout

### Authorization
- Role-based access: only `manager` and `superadmin` can access admin endpoints
- Hierarchical team scoping: managers only see their team + subtree
- IDOR protection: `team_id` derived server-side, never from client input
- Cross-team access attempts are blocked and audit-logged

### Audit Logging
- Every login success is logged with `admin_login_success`
- Every login failure is logged with `admin_login_failed` (with reason)
- IDOR attempts logged as `cross_team_access_blocked`
- All audit logs include actor, action, timestamp, and detail

### Tracker Authentication (Production Mode)
- Device tokens: hashed with SHA-256, stored in DB
- Token expiry and revocation support
- Team membership validation on every ingest
- LAN-ID header required alongside Bearer token

---

## 9. What Can Go Wrong (Troubleshooting)

### Error: AADSTS50105 — "Your administrator has configured the application to block users"
**Cause**: The user is not assigned to the Azure AD enterprise app.
**Fix**: IT admin must assign the user in Azure Portal → Enterprise Applications →
Zinnia Axion Admin → Users and groups → Add user/group.

### Error: "Your account is not registered in the system."
**Cause**: The email from Azure AD doesn't match any `User.email` or `User.lan_id`
in the database.
**Fix**: Create a User record with `email` matching the Azure AD email exactly.

### Error: "You do not have admin access."
**Cause**: The User record exists but `role` is "user" instead of "manager".
**Fix**: Update the User record: `UPDATE users SET role = 'manager' WHERE email = '...'`

### Error: "No team assignment found for your account."
**Cause**: The User has role=manager but no entry in the `managers` table.
**Fix**: Create a Manager record linking the user to a team.

### Error: "SSO authentication failed. Please try again."
**Cause**: The authorization code exchange failed. This can happen if:
- The `OIDC_CLIENT_SECRET` is wrong or expired
- The `OIDC_REDIRECT_URI` doesn't match what's registered in Azure AD
- Network issues between the backend and Azure AD
**Fix**: Verify the client secret and redirect URI match Azure AD configuration.

### Error: "Token validation failed."
**Cause**: The ID token couldn't be verified. Possible reasons:
- Clock skew between server and Azure AD (token appears expired)
- Wrong `OIDC_ISSUER_URL` (issuer mismatch)
**Fix**: Verify the issuer URL uses the correct tenant ID. Ensure server clock
is accurate (use NTP).

### Error: "OIDC not configured"
**Cause**: `OIDC_ISSUER_URL` is empty in the `.env` file.
**Fix**: Set all 4 OIDC environment variables.

### Infinite redirect loop
**Cause**: Session not being created properly. Usually because `SECRET_KEY` is
empty (sessions can't be encrypted).
**Fix**: Generate and set a SECRET_KEY: `python3 -c "import secrets; print(secrets.token_hex(32))"`

---

## 10. IT Admin Request Template

Copy and send this to your IT admin:

---

**Subject: Azure AD App Registration Request — Zinnia Axion Admin Portal**

Hi [IT Admin Name],

I need an Azure AD app registration for our internal productivity monitoring
tool (Zinnia Axion). This will allow team managers to log in to the admin
dashboard using company SSO.

**App Registration Details:**
- App Name: `Zinnia Axion Admin`
- App Type: Web application
- Supported account types: Single tenant (this org only)
- Redirect URI (Web): `http://localhost:5000/admin/callback`
  (We will add the production URL later)

**API Permissions Required (Delegated, Microsoft Graph):**
- `openid` — Sign users in
- `profile` — Read basic profile
- `email` — Read email address

**Token Configuration:**
- Please add `email` as an optional claim on the **ID token**

**User Assignment:**
- Please set "User assignment required?" to **Yes**
- Please assign the following users (or create a security group):
  - wasim.shaikh@zinnia.com
  - atharva.tippe@zinnia.com
  - nikhil.saxena@zinnia.com
  - [add other managers as needed]

**What I Need Back:**
1. Directory (tenant) ID
2. Application (client) ID
3. Client Secret value

Thank you!

---

## 11. Team Hierarchy — How Managers See Only Their Team's Data

After SSO login, the system automatically restricts each manager to their own
team and all child teams below it. Here is exactly how this works.

### 11.1 — The Database Structure

The hierarchy is defined by three tables working together:

```
teams table (parent_team_id creates the tree):
  id=2  name="Engineering"   parent_team_id=NULL   ← root (no parent)
  id=1  name="Lifecad"       parent_team_id=2      ← child of Engineering
  id=3  name="Axion"         parent_team_id=1      ← child of Lifecad

Visual tree:
  Engineering (id=2)  ← Nikhil manages this
    └── Lifecad (id=1)  ← Wasim manages this
          └── Axion (id=3)  ← Atharva manages this
```

Each manager is linked to exactly one team via the `managers` table:

```
managers table:
  user_id=1 (Wasim)   → team_id=1 (Lifecad)
  user_id=2 (Atharva) → team_id=3 (Axion)
  user_id=3 (Nikhil)  → team_id=2 (Engineering)
```

Users (employees being tracked) are linked to teams via `memberships`:

```
memberships table:
  user_id=1 (Wasim)   → team_id=1 (Lifecad)    active=true
  user_id=2 (Atharva) → team_id=3 (Axion)       active=true
```

### 11.2 — What Happens When Wasim Logs In Via SSO

**Step 1 — SSO returns email**: Azure AD returns `wasim.shaikh@zinnia.com`

**Step 2 — User lookup**: Backend finds `User(id=1, role="manager")`

**Step 3 — Manager lookup**: Backend finds `Manager(user_id=1, team_id=1)`
→ Wasim manages Lifecad (team_id=1)

**Step 4 — Session created**:
```python
session["user_id"] = 1      # Wasim's DB id
session["team_id"] = 1      # Lifecad — derived from DB, NEVER from client
session["role"] = "manager"
```

**Step 5 — Wasim opens the dashboard, @admin_required runs**:
```python
g.current_user_id = 1   # From session
g.current_team_id = 1   # From session (Lifecad)
```

**Step 6 — @team_scoped computes the hierarchy**:

The backend runs a recursive query starting from Wasim's team (Lifecad, id=1)
to find all descendant teams:

```sql
-- Postgres recursive CTE (SQLite uses Python BFS fallback)
WITH RECURSIVE team_tree AS (
    SELECT id FROM teams WHERE id = 1          -- Start: Lifecad
    UNION ALL
    SELECT t.id FROM teams t
    INNER JOIN team_tree tt ON t.parent_team_id = tt.id
)
SELECT id FROM team_tree;

-- Result: [1, 3]  → Lifecad + Axion (its child)
```

So `g.allowed_team_ids = [1, 3]`

**Step 7 — Data queries are filtered**:
```python
# Only fetch users whose team is in Wasim's allowed set [1, 3]
lan_ids = _lan_ids_for_teams(allowed_team_ids=[1, 3])
# Returns: ["Wasim", "Atharva"] — users in Lifecad and Axion

# All telemetry queries filter by these users
events = TelemetryEvent.query.filter(
    TelemetryEvent.user_id.in_(["Wasim", "Atharva"]), ...
)
```

Wasim sees his own data AND Atharva's data (because Axion is a child of
Lifecad in the hierarchy).

### 11.3 — What Each Manager Sees After Login

| Manager | Manages Team | allowed_team_ids | Sees Users | Scope |
|---------|-------------|-----------------|------------|-------|
| **Atharva** | Axion (id=3) | [3] | Only Atharva | Leaf team — sees only his own team |
| **Wasim** | Lifecad (id=1) | [1, 3] | Wasim + Atharva | Mid-level — sees Lifecad + child Axion |
| **Nikhil** | Engineering (id=2) | [2, 1, 3] | Everyone | Top-level — sees entire hierarchy |

### 11.4 — Security: What Prevents Cheating

Five layers of protection ensure a manager cannot see data outside their scope:

**Layer 1 — team_id from DB, not client**: The `team_id` stored in the session
comes from the `managers` table lookup, not from any URL parameter, form field,
or header. There is no way for the client to inject a different team_id.

**Layer 2 — Server-side hierarchy computation**: `get_allowed_team_ids()` runs
on the server using a database query. The client never sends a list of
allowed teams.

**Layer 3 — @team_scoped decorator on every admin endpoint**: Every endpoint
that serves team data has `@admin_required` + `@team_scoped` decorators. If
either is missing, the endpoint won't have access to `g.allowed_team_ids`.

**Layer 4 — Service-level guards**: Even inside service functions, there are
additional checks:
```python
# Before accessing any team's data:
assert_team_in_scope(team_id)    # Aborts 403 if team not in manager's subtree

# Before accessing any user's data:
assert_user_in_scope(user_id)    # Aborts 403 if user's team not in subtree
```

**Layer 5 — Audit logging of blocked attempts**: If someone somehow tries to
access data outside their subtree (e.g., by manipulating URLs), it is:
- Blocked with HTTP 403
- Logged to the audit_log table with action `cross_team_access_blocked` or
  `idor_team_blocked` or `idor_user_blocked`
- Includes the attacker's user_id, the attempted team_id, and the allowed set

### 11.5 — Setting Up the Hierarchy for Production

For each real manager in your company, you need these records:

**1. Team records** (define the tree structure):
```sql
INSERT INTO teams (id, name, parent_team_id) VALUES
  (1, 'Engineering', NULL),        -- Root team
  (2, 'Backend Team', 1),          -- Child of Engineering
  (3, 'Frontend Team', 1),         -- Child of Engineering
  (4, 'QA Team', 2);               -- Child of Backend Team
```

**2. User records** (email MUST match Azure AD):
```sql
INSERT INTO users (lan_id, email, display_name, role) VALUES
  ('wasim.shaikh', 'wasim.shaikh@zinnia.com', 'Wasim Shaikh', 'manager'),
  ('atharva.tippe', 'atharva.tippe@zinnia.com', 'Atharva Tippe', 'manager');
```

**3. Manager records** (link each manager to their team):
```sql
INSERT INTO managers (user_id, team_id) VALUES
  (1, 1),   -- Wasim manages Engineering (root → sees everything)
  (2, 2);   -- Atharva manages Backend Team (sees Backend + QA)
```

**4. Membership records** (link tracked users to teams):
```sql
INSERT INTO memberships (user_id, team_id, active) VALUES
  (1, 1, true),   -- Wasim is in Engineering
  (2, 2, true);   -- Atharva is in Backend Team
```

You can use `scripts/backfill_teams.py` as a reference, or create an Alembic
migration with your actual company structure.

### 11.6 — Adding a New Manager Later

To add a new manager after initial setup:

1. IT admin assigns them in Azure AD (so they can log in via SSO)
2. You create a `User` record with their Azure AD email
3. You create a `Manager` record linking them to the right team
4. You create a `Membership` record for them
5. They log in via SSO → the system automatically scopes them to their team

No code changes needed. The hierarchy is entirely data-driven.

---

## Summary Checklist

- [ ] IT admin registers Azure AD app
- [ ] IT admin creates client secret
- [ ] IT admin adds email claim to ID token
- [ ] IT admin assigns managers to the enterprise app
- [ ] IT admin provides Tenant ID, Client ID, Client Secret
- [ ] You set `DEMO_MODE=false` in `.env`
- [ ] You set `SECRET_KEY` in `.env`
- [ ] You set `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` in `.env`
- [ ] You verify manager User records have matching emails in the database
- [ ] You test login with one manager account
- [ ] You address the public endpoint security gap before production deployment
