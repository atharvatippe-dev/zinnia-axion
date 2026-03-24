# Infrastructure Request: SSO Authentication Setup for Zinnia Axion Productivity Tracker

**Date:** March 19, 2026  
**Requested By:** Atharva Tippe  
**Project:** Zinnia Axion - Employee Productivity Tracking System  
**Priority:** High  
**Estimated Timeline:** 2-3 weeks  

---

## Executive Summary

We are deploying an enterprise productivity tracking system (Zinnia Axion) that requires **Single Sign-On (SSO) authentication** for manager access to the admin dashboard. This request outlines the infrastructure requirements for Azure AD / Okta SAML 2.0 or OIDC integration.

---

## 1. Application Overview

### What is Zinnia Axion?
An internal productivity monitoring system that:
- Tracks employee computer activity (apps, mouse/keyboard interaction, idle time)
- Provides managers with team productivity dashboards
- Classifies time into productive/non-productive categories
- Stores data in PostgreSQL database

### Architecture:
```
Employees (Tracker) → Backend API → PostgreSQL Database
Managers (SSO Login) → Admin Dashboard → Backend API → Data
```

### Technology Stack:
- **Backend:** Python 3.9 + Flask (REST API)
- **Frontend:** Streamlit (Admin Dashboard)
- **Database:** PostgreSQL 15
- **Authentication:** OIDC/SAML 2.0 (Azure AD, Okta, or Google Workspace)

---

## 2. SSO Requirements

### Authentication Protocol
We support both (infra team can choose):

1. **OIDC (OpenID Connect)** - Preferred ✓
2. **SAML 2.0** - Also supported

### Identity Provider (IdP)
Please configure SSO using one of:
- Azure AD (Microsoft Entra ID) ← **Recommended if company uses Microsoft 365**
- Okta
- Google Workspace
- Any OIDC/SAML 2.0 compliant provider

---

## 3. Application Registration Details

### Application Information

| Field | Value |
|---|---|
| **Application Name** | Zinnia Axion Productivity Tracker |
| **Application Type** | Web Application |
| **Description** | Employee productivity monitoring and analytics platform |
| **Access Type** | Internal only (company employees) |
| **User Base** | ~10-100 managers (initial rollout: 10 managers) |

### Redirect URIs (Callback URLs)

**Development:**
```
http://localhost:5000/admin/oidc/callback
http://127.0.0.1:5000/admin/oidc/callback
```

**Production (TBD - will be updated once deployed):**
```
https://productivity.company.com/admin/oidc/callback
https://axion.company.com/admin/oidc/callback
```

### Logout URIs

**Development:**
```
http://localhost:5000/admin/logout
```

**Production:**
```
https://productivity.company.com/admin/logout
```

---

## 4. Required Information from Infra Team

Once SSO application is registered, please provide:

### For OIDC (Preferred):

| Parameter | Example | Description |
|---|---|---|
| **Issuer URL** | `https://login.microsoftonline.com/{tenant-id}/v2.0` | Azure AD issuer endpoint |
| **Client ID** | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` | Application ID from Azure AD |
| **Client Secret** | `xYz...abc` | Application secret (keep secure) |
| **Authorization Endpoint** | Auto-discovered | OAuth 2.0 auth endpoint |
| **Token Endpoint** | Auto-discovered | OAuth 2.0 token endpoint |
| **JWKS URI** | Auto-discovered | Public keys for token validation |

### For SAML 2.0 (Alternative):

| Parameter | Example | Description |
|---|---|---|
| **Entity ID** | `https://productivity.company.com` | SP entity identifier |
| **SSO URL** | `https://login.microsoftonline.com/{tenant}/saml2` | IdP SSO endpoint |
| **X.509 Certificate** | `-----BEGIN CERTIFICATE-----...` | Public certificate for signature validation |
| **Logout URL** | `https://login.microsoftonline.com/{tenant}/saml2/logout` | Single logout endpoint |

---

## 5. User Attributes / Claims Required

The SSO response should include the following user attributes:

| Attribute | OIDC Claim | SAML Attribute | Required? | Usage |
|---|---|---|---|---|
| **Email** | `email` | `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` | ✓ Yes | Primary user identifier |
| **Display Name** | `name` | `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name` | ✓ Yes | Manager's full name |
| **User ID** | `sub` or `oid` | `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier` | Optional | Unique identifier |
| **Groups** | `groups` | `http://schemas.xmlsoap.org/claims/Group` | Optional | For role-based access (future) |

### Example OIDC ID Token:
```json
{
  "iss": "https://login.microsoftonline.com/{tenant-id}/v2.0",
  "sub": "AAAAAAAAAAAAAAAAAAAAAIkzqFVrSaSaFHy782bbtaQ",
  "aud": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "exp": 1710854400,
  "iat": 1710850800,
  "email": "wasim.shaikh@company.com",
  "name": "Wasim Shaikh",
  "oid": "00000000-0000-0000-0000-000000000001"
}
```

---

## 6. Authorization / Access Control

### Who Can Access?

| Role | Access Level | SSO Required? |
|---|---|---|
| **Managers** | Admin Dashboard (view team data) | ✓ Yes |
| **Employees** | User Dashboard (view own data) | ✗ No (public access) |
| **Superadmin** | Full system access | ✓ Yes |

### User Provisioning

**Option 1 (Recommended):** Manual Database Entry
- Infra team doesn't need to provision users in Azure AD
- We manually add manager emails to our database (`users` table)
- Only users in our database can login (even if they have valid company credentials)

**Option 2 (Future):** Automatic Provisioning via Groups
- Create Azure AD group: `Axion-Managers`
- Add managers to this group
- Our app validates group membership during login

For initial rollout, **Option 1** is preferred (simpler, faster).

---

## 7. Security Configuration

### Required Scopes / Permissions

For OIDC, please grant the following scopes:

| Scope | Purpose |
|---|---|
| `openid` | Enable OpenID Connect |
| `profile` | Access user's profile information (name) |
| `email` | Access user's email address |

**No additional Microsoft Graph API permissions needed** at this time.

### Token Validation

Our backend will validate:
- ✓ JWT signature using IdP's public keys (JWKS)
- ✓ Token expiration (`exp` claim)
- ✓ Token audience (`aud` claim matches our Client ID)
- ✓ Token issuer (`iss` claim matches expected IdP)

### Session Management

- Session duration: **8 hours** (configurable)
- Session storage: **Server-side** (PostgreSQL or Redis)
- Session cookies: **HttpOnly, Secure, SameSite=Lax**

---

## 8. Network & Firewall Requirements

### Outbound Access Required

Our backend server needs to reach:

| Destination | Port | Purpose |
|---|---|---|
| `login.microsoftonline.com` | 443 (HTTPS) | Azure AD authentication |
| `graph.microsoft.com` | 443 (HTTPS) | Token validation (JWKS) |

**No inbound firewall rules needed** from Azure AD (all communication is outbound from our server).

### Deployment Environment

**Phase 1 (Current - Development):**
- Running on: Local development machines
- Backend URL: `http://localhost:5000`
- Dashboard URL: `http://localhost:8501`

**Phase 2 (Planned - Production):**
- Platform: AWS ECS Fargate or Azure Container Instances
- Backend URL: `https://productivity.company.com` (domain TBD)
- Dashboard URL: `https://productivity.company.com/admin`
- Database: AWS RDS PostgreSQL or Azure Database for PostgreSQL

---

## 9. Configuration on Our Side

Once you provide the SSO details, we will configure our `.env` file:

```bash
# SSO Configuration (OIDC)
OIDC_ISSUER_URL=https://login.microsoftonline.com/{tenant-id}/v2.0
OIDC_CLIENT_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
OIDC_CLIENT_SECRET=xYz...abc
OIDC_SCOPES=openid profile email

# Application Settings
DEMO_MODE=false
SECRET_KEY={random-256-bit-key}
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
```

**No additional software installation required on infra side** — all SSO logic is handled by our Python backend using industry-standard libraries (Authlib).

---

## 10. Testing Plan

After SSO is configured, we will test:

### Test Scenarios:

1. ✓ **Valid Manager Login**
   - Manager `wasim.shaikh@company.com` logs in via SSO
   - Redirected to Azure AD, enters credentials
   - Successfully redirected back to dashboard
   - Email and name populated correctly

2. ✓ **Invalid User Login**
   - User `random.person@company.com` (not in our database) tries to login
   - SSO succeeds, but our app rejects with "Access Denied"

3. ✓ **Session Expiry**
   - Manager logs in, works for 8 hours
   - Session expires, redirected to login

4. ✓ **Logout**
   - Manager clicks "Sign Out"
   - Session cleared, redirected to login page

5. ✓ **Token Validation**
   - Manipulated/expired tokens rejected
   - Signature verification works

### Test Users Needed:

Please provide 2-3 test accounts for initial validation:
- `test.manager1@company.com`
- `test.manager2@company.com`

---

## 11. Initial Manager List (Rollout Phase)

Please note: Only the following users will have access (manually added to our database):

| Name | Email | Team | Role |
|---|---|---|---|
| Wasim Shaikh | wasim.shaikh@company.com | Lifecad | Manager |
| Nikhil Saxena | nikhil.saxena@company.com | Engineering | Manager |
| Atharva Tippe | atharva.tippe@company.com | Axion | Manager |
| Punit Joshi | punit.joshi@company.com | Fast | Manager |

Additional managers can be added later by updating our database.

---

## 12. Data Privacy & Compliance

### What Data is Transmitted to/from SSO?

**To Azure AD (during login):**
- Application Client ID
- Redirect URI
- Requested scopes (openid, profile, email)

**From Azure AD (in response):**
- User's email address
- User's display name
- User's unique ID (optional)

**NOT transmitted:**
- No employee activity data
- No productivity metrics
- No telemetry events

### Data Storage

- SSO tokens: **Not stored** (validated and discarded)
- Session data: Stored server-side (user email, name, team ID)
- User profile: Stored in PostgreSQL (`users` table)

### Compliance

- GDPR: User can request data deletion
- Data retention: 14 days for telemetry, indefinite for user profiles
- No PII beyond email and name

---

## 13. Support & Contacts

### Development Team

| Role | Name | Email |
|---|---|---|
| Project Lead | Atharva Tippe | atharva.tippe@company.com |
| Backend Developer | [Your Name] | [your.email@company.com] |

### Support Needed from Infra Team

1. **Azure AD/Okta App Registration** (1-2 hours)
2. **Provide configuration details** (Client ID, Secret, Issuer URL)
3. **Firewall rule verification** (if needed)
4. **Test account creation** (optional, 2-3 test users)

### Timeline

| Phase | Task | Duration | Status |
|---|---|---|---|
| 1 | Infra team registers SSO app | 1-2 days | Pending |
| 2 | Dev team configures backend | 1 day | Ready |
| 3 | Testing with test accounts | 2-3 days | Pending |
| 4 | Production rollout | 1 week | Pending |

**Target Go-Live:** 2-3 weeks from SSO setup completion

---

## 14. Troubleshooting & Logs

### Common Issues We'll Handle

| Issue | Our Solution |
|---|---|
| Token signature validation fails | Verify JWKS endpoint, update public keys |
| Redirect loop | Check redirect URI matches exactly |
| "Access Denied" for valid user | Add user email to database |
| Session not persisting | Verify cookie settings (Secure, SameSite) |

### Logs We'll Provide for Debugging

```
2026-03-19 14:23:01 [INFO] OIDC: Redirecting to Azure AD for authentication
2026-03-19 14:23:15 [INFO] OIDC: Received callback with code=ABC123...
2026-03-19 14:23:16 [INFO] OIDC: Token exchange successful
2026-03-19 14:23:16 [INFO] OIDC: ID token validated, email=wasim.shaikh@company.com
2026-03-19 14:23:16 [INFO] AUTH: User found in database, user_id=1, team_id=1
2026-03-19 14:23:16 [INFO] SESSION: Created session for user_id=1
2026-03-19 14:23:16 [INFO] OIDC: Redirecting to dashboard
```

---

## 15. Appendix: Technical Documentation

### A. SSO Login Flow Diagram

```
┌─────────┐                                  ┌──────────┐
│ Manager │                                  │ Azure AD │
└────┬────┘                                  └────┬─────┘
     │                                            │
     │ 1. Access Dashboard                        │
     │ http://localhost:8501                      │
     ▼                                            │
┌─────────────┐                                  │
│ Streamlit   │                                  │
│ Dashboard   │                                  │
└──────┬──────┘                                  │
       │ 2. Redirect to Backend                  │
       │ /admin/login                             │
       ▼                                          │
  ┌─────────┐                                    │
  │ Flask   │ 3. Redirect to Azure AD            │
  │ Backend ├────────────────────────────────────►
  └─────────┘    with Client ID + Redirect URI   │
                                                  │
                 4. Show Microsoft login page     │
       ┌──────────────────────────────────────────┤
       │                                          │
       │ 5. User enters email + password         │
       │    (+ MFA if enabled)                   │
       ├─────────────────────────────────────────►
       │                                          │
       │ 6. Return authorization code            │
       ◄─────────────────────────────────────────┤
       │    Redirect: /admin/oidc/callback?code= │
       │                                          │
  ┌────▼────┐                                    │
  │ Flask   │ 7. Exchange code for ID token      │
  │ Backend ├────────────────────────────────────►
  └────┬────┘                                    │
       │                                          │
       │ 8. Return ID token (JWT)                │
       ◄──────────────────────────────────────────
       │    {email, name, sub, ...}              │
       │                                          │
       │ 9. Validate JWT signature               │
       │ 10. Check email in database             │
       │ 11. Create session                      │
       │                                          │
       │ 12. Redirect to dashboard               │
       ▼                                          │
┌─────────────┐                                  │
│ Streamlit   │ 13. Show team data               │
│ Dashboard   │                                  │
└─────────────┘                                  │
```

### B. Example Azure AD App Registration Steps

**For Infra Team Reference:**

1. **Navigate to:** Azure Portal > Azure Active Directory > App registrations
2. **Click:** New registration
3. **Fill in:**
   - Name: `Zinnia Axion Productivity Tracker`
   - Supported account types: `Accounts in this organizational directory only`
   - Redirect URI: `Web` → `http://localhost:5000/admin/oidc/callback`
4. **Click:** Register
5. **Note down:** Application (client) ID
6. **Navigate to:** Certificates & secrets
7. **Click:** New client secret
8. **Note down:** Secret value (only shown once!)
9. **Navigate to:** Token configuration
10. **Add optional claims:**
    - ID token: `email`, `name`
11. **Navigate to:** API permissions
12. **Verify:** `openid`, `profile`, `email` are granted
13. **Done!** Provide Client ID + Secret to dev team

### C. Security Checklist

- [ ] HTTPS enforced in production
- [ ] Client secret stored in environment variables (not code)
- [ ] Token signature validation enabled
- [ ] Token expiration (`exp`) checked
- [ ] Audience (`aud`) validation enabled
- [ ] Issuer (`iss`) validation enabled
- [ ] Session cookies: HttpOnly, Secure, SameSite
- [ ] Session timeout: 8 hours
- [ ] CSRF protection enabled
- [ ] Rate limiting on login endpoint
- [ ] Audit logs for all authentication events

---

## 16. Questions?

If you have any questions or need clarification, please contact:

**Atharva Tippe**  
Email: atharva.tippe@company.com  
Project: Zinnia Axion Productivity Tracker  

---

**Attachments:**
1. Architecture diagram: `architecture.svg`
2. Technical documentation: `README.md`
3. Security questionnaire: `SECURITY_QUESTIONNAIRE.md`
4. SSO setup guide: `SSO_LOGIN_SETUP.md`

---

_This document is confidential and intended for internal use only._
