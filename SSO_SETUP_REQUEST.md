# SSO Setup Request - Zinnia Axion Productivity Platform

**To:** Senior Infrastructure Engineer  
**From:** Atharva Tippe  
**Date:** March 24, 2026  
**Subject:** Azure AD / OIDC SSO Configuration for Zinnia Axion Admin Dashboard

---

## Application Overview

**Application Name:** Zinnia Axion - Productivity Intelligence Platform  
**Purpose:** Enterprise productivity tracking and team management  
**Authentication:** OIDC SSO (Microsoft Azure AD) for admin/manager access  
**Users:** Managers and team leads only (employees use device tokens)

---

## 1️⃣ Application Registration Details

### **Application Name (Display Name)**
```
Zinnia Axion - Admin Dashboard
```

### **Application Type**
```
Web Application
```

### **Supported Account Types**
```
Accounts in this organizational directory only (Zinnia - Single tenant)
```

---

## 2️⃣ Redirect URIs (Reply URLs)

**IMPORTANT:** You need to configure **BOTH** environments:

### **Production (After AWS ECS Deployment)**
```
https://axion.yourcompany.com/admin/callback
```

### **Development/Testing (Optional)**
```
http://localhost:5000/admin/callback
https://axion-staging.yourcompany.com/admin/callback
```

**Protocol:** HTTPS (except localhost for dev)  
**Endpoint:** `/admin/callback`

---

## 3️⃣ Application ID URI (Identifier / Entity ID)

### **Recommended Format:**
```
api://zinnia-axion
```

### **Alternative (if domain-based required):**
```
https://axion.yourcompany.com
```

**Note:** This is the unique identifier for the application in Azure AD.

---

## 4️⃣ Required API Permissions (Scopes)

### **Microsoft Graph API Permissions:**

| Permission | Type | Purpose |
|------------|------|---------|
| `openid` | Delegated | Sign in and read user profile |
| `profile` | Delegated | Read user's basic profile |
| `email` | Delegated | Read user's email address |
| `User.Read` | Delegated | Read signed-in user's profile |

**Admin Consent Required:** Yes (please pre-approve these permissions)

---

## 5️⃣ Token Configuration

### **Access Tokens (Optional Claims)**
Please include these claims in ID tokens:
- `email`
- `family_name`
- `given_name`
- `upn` (User Principal Name)

### **Token Version**
```
v2.0
```

---

## 6️⃣ Authentication Configuration

### **Supported Authentication Flows**
- ✅ **Authorization Code Flow** (PKCE optional)
- ❌ Implicit grant (not needed)
- ❌ Client credentials (not needed)

### **Logout URL (Front-channel)**
```
https://axion.yourcompany.com/admin/logout
```

---

## 7️⃣ Application Secrets (Client Credentials)

### **Client Secret Configuration**
- **Description:** `Zinnia Axion Backend Production`
- **Expiration:** 24 months (or per company policy)
- **Storage:** Will be stored in AWS Secrets Manager

**Please provide:**
1. **Client ID** (Application ID)
2. **Client Secret** (Value, not Secret ID)
3. **Tenant ID** (Directory ID)

---

## 8️⃣ OIDC Discovery Endpoint (Auto-Configuration)

### **Expected Format:**
```
https://login.microsoftonline.com/{TENANT_ID}/v2.0
```

**Example:**
```
https://login.microsoftonline.com/12345678-1234-1234-1234-123456789abc/v2.0
```

**Well-known endpoint (for verification):**
```
https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration
```

---

## 9️⃣ User Assignment (Enterprise Application)

### **Assignment Required**
```
Yes - Only assigned users/groups can access
```

### **Users/Groups to Assign**
Please assign the following groups:
- ✅ **Team Managers** (all team leads)
- ✅ **Engineering Managers**
- ✅ **Department Heads**
- ❌ Regular employees (they use desktop tracker, not admin dashboard)

**Estimated Users:** 10-50 managers initially

---

## 🔟 Branding (Optional)

### **Logo**
- Upload Zinnia logo (if available)

### **Application Home Page**
```
https://axion.yourcompany.com/admin/dashboard
```

### **Terms of Service URL**
```
https://yourcompany.com/terms
```

### **Privacy Statement URL**
```
https://yourcompany.com/privacy
```

---

## 1️⃣1️⃣ Security Recommendations

### **Conditional Access Policies**
Please apply the following (if available):
- ✅ Require MFA for admin dashboard access
- ✅ Require compliant device
- ✅ Block access from untrusted locations (optional)

### **Session Lifetime**
- **Recommended:** 8 hours (standard work day)
- **Maximum:** 24 hours

---

## 1️⃣2️⃣ What We Need From You (Deliverables)

After creating the Azure AD application registration, please provide:

### **Required Information:**

1. **Tenant ID** (Directory ID)
   ```
   Example: 12345678-1234-1234-1234-123456789abc
   ```

2. **Client ID** (Application ID)
   ```
   Example: 87654321-4321-4321-4321-cba987654321
   ```

3. **Client Secret** (Secret Value)
   ```
   Example: abc123~XYZ789-SecretValue-Here
   ```

4. **OIDC Issuer URL**
   ```
   Format: https://login.microsoftonline.com/{TENANT_ID}/v2.0
   ```

5. **Authorization Endpoint** (for verification)
   ```
   Format: https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize
   ```

6. **Token Endpoint** (for verification)
   ```
   Format: https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token
   ```

---

## 1️⃣3️⃣ Backend Configuration (We'll Handle This)

Once you provide the credentials, we'll configure the backend:

```env
# OIDC SSO Configuration
OIDC_ISSUER_URL=https://login.microsoftonline.com/{TENANT_ID}/v2.0
OIDC_CLIENT_ID={CLIENT_ID}
OIDC_CLIENT_SECRET={CLIENT_SECRET}
OIDC_REDIRECT_URI=https://axion.yourcompany.com/admin/callback
OIDC_SCOPES=openid profile email
```

---

## 1️⃣4️⃣ Testing Plan

After configuration, we'll test:

1. ✅ Admin login flow (redirect to Azure AD)
2. ✅ User authentication and callback
3. ✅ Token validation
4. ✅ Profile information retrieval
5. ✅ Session management
6. ✅ Logout functionality

---

## 1️⃣5️⃣ Quick Reference Summary

| Item | Value |
|------|-------|
| **App Name** | Zinnia Axion - Admin Dashboard |
| **App Type** | Web Application |
| **Redirect URI (Prod)** | `https://axion.yourcompany.com/admin/callback` |
| **Identifier (Entity ID)** | `api://zinnia-axion` |
| **Scopes** | `openid profile email` |
| **Token Version** | v2.0 |
| **Authorization Flow** | Authorization Code |
| **Users** | Managers only (10-50 users) |

---

## 1️⃣6️⃣ Support Contacts

**Technical Lead:** Atharva Tippe (atharva.tippe@zinnia.com)  
**DevOps Team:** [DevOps email]  
**Project Manager:** [PM email]

---

## 1️⃣7️⃣ Timeline

**Requested Completion:** [Your target date]

**Deployment Sequence:**
1. Azure AD app registration setup (Infra team)
2. Provide Client ID/Secret (Infra team)
3. Configure backend environment variables (DevOps team)
4. Deploy to AWS ECS (DevOps team)
5. Test SSO login (QA + Atharva)
6. Production rollout (All teams)

---

## 1️⃣8️⃣ Additional Notes

### **Why OIDC/Azure AD?**
- ✅ Centralized identity management
- ✅ Single sign-on (no separate passwords)
- ✅ MFA support
- ✅ Audit trail via Azure AD logs
- ✅ Automatic deprovisioning when users leave

### **Security Features Already Implemented:**
- ✅ CSRF protection
- ✅ Secure session cookies (HTTP-only, Secure, SameSite)
- ✅ Rate limiting
- ✅ Audit logging
- ✅ RBAC (Role-Based Access Control)

---

## 📧 **Please Reply With:**

1. ✅ Azure AD App Registration confirmation
2. ✅ Client ID
3. ✅ Client Secret
4. ✅ Tenant ID
5. ✅ OIDC Issuer URL
6. ✅ Any conditional access policies applied

---

**Thank you for your support in setting up SSO for the Zinnia Axion platform!**

---

**Prepared by:** Atharva Tippe  
**Project:** Zinnia Axion - Enterprise Productivity Intelligence Platform  
**Document Version:** 1.0  
**Last Updated:** March 24, 2026
