# SSO Configuration - Quick Reference Card

**For:** Senior Infrastructure Engineer  
**App:** Zinnia Axion Admin Dashboard

---

## ✅ Quick Setup Checklist

### 1. Azure AD App Registration

```yaml
App Name: Zinnia Axion - Admin Dashboard
App Type: Web Application
Tenant: Zinnia (Single tenant)
```

### 2. Redirect URIs (Reply URLs)

```
Production:
https://axion.yourcompany.com/admin/callback

Development (optional):
http://localhost:5000/admin/callback
```

### 3. Application ID URI (Entity ID)

```
api://zinnia-axion
```

### 4. API Permissions

```
Microsoft Graph:
  - openid (Delegated)
  - profile (Delegated)
  - email (Delegated)
  - User.Read (Delegated)

Admin Consent: ✅ Required
```

### 5. Client Secret

```
Description: Zinnia Axion Backend Production
Expiration: 24 months
```

---

## 📋 Information Needed From You

Please provide these 4 items:

```
1. Tenant ID:    ____________________________________
2. Client ID:    ____________________________________
3. Client Secret: ____________________________________
4. Issuer URL:   https://login.microsoftonline.com/{TENANT_ID}/v2.0
```

---

## 🎯 URLs to Configure

| Purpose | URL |
|---------|-----|
| **Redirect URI** | `https://axion.yourcompany.com/admin/callback` |
| **Logout URL** | `https://axion.yourcompany.com/admin/logout` |
| **Home Page** | `https://axion.yourcompany.com/admin/dashboard` |

---

## 👥 User Assignment

**Assign these groups:**
- ✅ Team Managers
- ✅ Engineering Managers
- ✅ Department Heads

**Do NOT assign:**
- ❌ Regular employees (they use device tokens)

**Estimated Users:** 10-50 managers

---

## 🔐 Security Settings

```yaml
Authorization Flow: Authorization Code
Token Version: v2.0
Assignment Required: Yes
Conditional Access: MFA recommended
Session Lifetime: 8 hours recommended
```

---

## 📧 Send Credentials To:

**Email:** atharva.tippe@zinnia.com  
**Subject:** Zinnia Axion - Azure AD SSO Credentials

**Include:**
- Tenant ID
- Client ID
- Client Secret
- OIDC Issuer URL

---

## ⚡ Quick Test (After Setup)

```bash
# Verify OIDC discovery endpoint works
curl https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration

# Should return JSON with authorization_endpoint, token_endpoint, etc.
```

---

**Questions?** Contact Atharva Tippe - atharva.tippe@zinnia.com

---

**Full Details:** See `SSO_SETUP_REQUEST.md` for complete documentation
