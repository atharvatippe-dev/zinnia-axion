# SAML SSO Setup Request - Zinnia Axion Productivity Platform

**To:** Senior Infrastructure Engineer  
**From:** Atharva Tippe  
**Date:** March 24, 2026  
**Subject:** SAML 2.0 SSO Configuration for Zinnia Axion Admin Dashboard

---

## Application Overview

**Application Name:** Zinnia Axion - Productivity Intelligence Platform  
**Purpose:** Enterprise productivity tracking and team management  
**Authentication:** SAML 2.0 SSO for admin/manager access  
**Users:** Managers and team leads only (employees use device tokens)

---

## 1️⃣ Service Provider (SP) Information

### **Application Name**
```
Zinnia Axion - Admin Dashboard
```

### **Entity ID (SP Entity ID / Issuer)**
```
https://axion.yourcompany.com/saml/metadata
```
**Alternative formats (if required by IdP):**
```
urn:amazon:webservices:zinnia-axion
api://zinnia-axion
```

### **Assertion Consumer Service (ACS) URL**
```
Production:
https://axion.yourcompany.com/saml/acs

Development/Testing (optional):
http://localhost:5000/saml/acs
https://axion-staging.yourcompany.com/saml/acs
```

**Protocol Binding:** HTTP-POST  
**Default:** Yes

---

## 2️⃣ Single Logout (SLO) Configuration

### **Single Logout Service URL**
```
https://axion.yourcompany.com/saml/slo
```

**Protocol Binding:** HTTP-POST or HTTP-Redirect  
**Sign Logout Requests:** Yes

---

## 3️⃣ Required SAML Attributes

Please map these user attributes in the SAML assertion:

| SAML Attribute | Description | Required | Example |
|----------------|-------------|----------|---------|
| `email` | User's email address | ✅ Yes | `atharva.tippe@zinnia.com` |
| `firstName` | User's first name | ✅ Yes | `Atharva` |
| `lastName` | User's last name | ✅ Yes | `Tippe` |
| `displayName` | Full display name | ✅ Yes | `Atharva Tippe` |
| `employeeId` | Employee ID / LAN ID | Recommended | `atharvat` |
| `department` | Department name | Optional | `Engineering` |
| `jobTitle` | Job title | Optional | `Software Engineer` |

### **Attribute Format**
```
Name Format: urn:oasis:names:tc:SAML:2.0:attrname-format:basic
```

---

## 4️⃣ Name ID Format

### **Preferred Format**
```
urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress
```

**Alternative (if email not available):**
```
urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
```

**Value:** User's email address (e.g., `atharva.tippe@zinnia.com`)

---

## 5️⃣ SAML Signing & Encryption

### **Assertion Signing**
```
Sign Assertions: Yes (Required)
Sign Response: Yes (Recommended)
Signature Algorithm: RSA-SHA256
```

### **Encryption** (Optional)
```
Encrypt Assertions: No (not required, HTTPS provides transport security)
```

### **Certificate Requirements**
- **Algorithm:** RSA 2048-bit or higher
- **Validity:** At least 1 year
- **Format:** X.509

---

## 6️⃣ Identity Provider (IdP) Configuration

### **What We Need From You:**

#### **1. IdP Metadata URL** (Preferred)
```
Example: https://your-idp.com/saml/metadata
```
This auto-configures the SAML integration.

#### **OR Manual Configuration:**

**2. IdP Entity ID (Issuer)**
```
Example: https://sts.windows.net/{TENANT_ID}/
Example: http://www.okta.com/{ORG_ID}
```

**3. SSO URL (Single Sign-On URL)**
```
Example: https://login.microsoftonline.com/{TENANT_ID}/saml2
Example: https://yourcompany.okta.com/app/{APP_ID}/sso/saml
```

**4. Sign-Out URL (SLO URL)**
```
Example: https://login.microsoftonline.com/{TENANT_ID}/saml2/logout
```

**5. X.509 Certificate (Public Key)**
```
-----BEGIN CERTIFICATE-----
MIIDdzCCAl+gAwIBAgIEAgAAuTANBgkqhkiG9w0BAQUFADBaMQswCQYDVQQGEwJJ
... (full certificate content) ...
-----END CERTIFICATE-----
```

---

## 7️⃣ IdP Configuration Steps (For Your Team)

### **For Azure AD (Microsoft Entra ID):**

1. **Create Enterprise Application**
   - Go to Azure AD → Enterprise Applications
   - Click "New Application" → "Create your own application"
   - Name: `Zinnia Axion - Admin Dashboard`
   - Select: "Integrate any other application you don't find in the gallery (Non-gallery)"

2. **Set up Single Sign-On**
   - Select "SAML" as SSO method
   - Basic SAML Configuration:
     - **Identifier (Entity ID):** `https://axion.yourcompany.com/saml/metadata`
     - **Reply URL (ACS URL):** `https://axion.yourcompany.com/saml/acs`
     - **Sign on URL:** `https://axion.yourcompany.com/admin/login`
     - **Logout URL:** `https://axion.yourcompany.com/saml/slo`

3. **User Attributes & Claims**
   - Add claims:
     - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` → `user.mail`
     - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname` → `user.givenname`
     - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname` → `user.surname`
     - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name` → `user.displayname`

4. **Download Certificate**
   - Download "Certificate (Base64)"
   - Copy "Login URL" and "Azure AD Identifier"

5. **Assign Users/Groups**
   - Assign team managers and department heads

---

### **For Okta:**

1. **Create SAML 2.0 App Integration**
   - Go to Applications → Create App Integration
   - Select "SAML 2.0"
   - App name: `Zinnia Axion - Admin Dashboard`

2. **SAML Settings**
   - **Single sign on URL:** `https://axion.yourcompany.com/saml/acs`
   - **Audience URI (SP Entity ID):** `https://axion.yourcompany.com/saml/metadata`
   - **Default RelayState:** (leave blank)
   - **Name ID format:** EmailAddress
   - **Application username:** Email

3. **Attribute Statements**
   - `email` → `user.email`
   - `firstName` → `user.firstName`
   - `lastName` → `user.lastName`
   - `displayName` → `user.displayName`

4. **Download Metadata**
   - View Setup Instructions → Download metadata XML
   - Or copy "Identity Provider metadata" link

5. **Assign Users**
   - Assign people or groups

---

## 8️⃣ User Assignment & Access Control

### **Who Should Have Access:**
- ✅ Team Managers
- ✅ Engineering Managers
- ✅ Department Heads
- ✅ HR Leads (for analytics)

### **Who Should NOT Have Access:**
- ❌ Regular employees (they use desktop tracker with device tokens)

**Estimated Users:** 10-50 managers initially, scaling to 100-200

---

## 9️⃣ Conditional Access & Security

### **Recommended Policies:**
- ✅ Require Multi-Factor Authentication (MFA)
- ✅ Require compliant device
- ✅ Block access from untrusted locations
- ✅ Require managed device (optional)

### **Session Lifetime:**
- **Recommended:** 8 hours (standard work day)
- **Maximum:** 24 hours

---

## 🔟 SP Metadata (For Your Reference)

Once our backend is deployed, we'll provide SP metadata at:
```
https://axion.yourcompany.com/saml/metadata
```

**Metadata will include:**
- Entity ID
- ACS URL
- SLO URL
- Public certificate (for request signing, if required)
- Supported NameID formats

---

## 1️⃣1️⃣ What We Need From You (Deliverables)

Please provide:

### **Option 1: IdP Metadata URL (Preferred)**
```
https://your-idp.com/saml/metadata
```
We'll auto-configure from this.

### **Option 2: Manual Configuration**
If metadata URL not available, provide:

1. **IdP Entity ID (Issuer)**
   ```
   Example: ____________________________________
   ```

2. **SSO URL (HTTP-POST)**
   ```
   Example: ____________________________________
   ```

3. **Sign-Out URL (SLO)**
   ```
   Example: ____________________________________
   ```

4. **X.509 Certificate**
   ```
   -----BEGIN CERTIFICATE-----
   (paste full certificate here)
   -----END CERTIFICATE-----
   ```

5. **Signature Algorithm**
   ```
   RSA-SHA256 (recommended)
   ```

---

## 1️⃣2️⃣ Backend Configuration (We'll Handle)

Once you provide the IdP details, we'll configure:

```python
# SAML SSO Configuration
SAML_IDP_ENTITY_ID = "https://sts.windows.net/{TENANT_ID}/"
SAML_IDP_SSO_URL = "https://login.microsoftonline.com/{TENANT_ID}/saml2"
SAML_IDP_SLO_URL = "https://login.microsoftonline.com/{TENANT_ID}/saml2/logout"
SAML_IDP_X509_CERT = "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
SAML_SP_ENTITY_ID = "https://axion.yourcompany.com/saml/metadata"
SAML_SP_ACS_URL = "https://axion.yourcompany.com/saml/acs"
```

---

## 1️⃣3️⃣ Testing Plan

After configuration, we'll test:

1. ✅ Initiate SSO from SP (our app)
2. ✅ Redirect to IdP login page
3. ✅ Authenticate with corporate credentials
4. ✅ SAML assertion validation
5. ✅ User attribute mapping
6. ✅ Session creation
7. ✅ Access admin dashboard
8. ✅ Single logout (SLO)

---

## 1️⃣4️⃣ Quick Reference Summary

| Item | Value |
|------|-------|
| **App Name** | Zinnia Axion - Admin Dashboard |
| **Protocol** | SAML 2.0 |
| **Entity ID (SP)** | `https://axion.yourcompany.com/saml/metadata` |
| **ACS URL** | `https://axion.yourcompany.com/saml/acs` |
| **SLO URL** | `https://axion.yourcompany.com/saml/slo` |
| **Binding** | HTTP-POST |
| **NameID Format** | EmailAddress |
| **Sign Assertions** | Yes (RSA-SHA256) |
| **Users** | Managers only (10-50 initially) |

---

## 1️⃣5️⃣ Important URLs

| Purpose | URL |
|---------|-----|
| **Sign-In (Initiate SSO)** | `https://axion.yourcompany.com/admin/login` |
| **ACS (Assertion Consumer)** | `https://axion.yourcompany.com/saml/acs` |
| **SLO (Single Logout)** | `https://axion.yourcompany.com/saml/slo` |
| **SP Metadata** | `https://axion.yourcompany.com/saml/metadata` |
| **Admin Dashboard** | `https://axion.yourcompany.com/admin/dashboard` |

---

## 1️⃣6️⃣ Support Contacts

**Technical Lead:** Atharva Tippe (atharva.tippe@zinnia.com)  
**DevOps Team:** [DevOps email]  
**Security Team:** [Security email]

---

## 1️⃣7️⃣ Timeline

**Requested Completion:** [Your target date]

**Deployment Sequence:**
1. IdP SAML app configuration (Infra team) ✅ You
2. Provide IdP metadata/details (Infra team) ✅ You
3. Backend SAML integration (DevOps + Dev team) ✅ Us
4. Deploy to AWS ECS (DevOps team) ✅ Us
5. Test SAML SSO flow (QA + Atharva) ✅ Us
6. Production rollout (All teams) ✅ Everyone

---

## 1️⃣8️⃣ Additional Notes

### **Why SAML 2.0?**
- ✅ Enterprise standard for SSO
- ✅ No client secrets to manage
- ✅ Works with all major IdPs (Azure AD, Okta, Ping, etc.)
- ✅ Strong security with signed assertions
- ✅ Centralized user management
- ✅ Single Logout support

### **Backend SAML Library:**
We'll use **python3-saml** or **flask-saml** for SAML integration.

---

## 📧 **Please Reply With:**

1. ✅ SAML app created confirmation
2. ✅ IdP Metadata URL (or manual details)
3. ✅ X.509 Certificate
4. ✅ SSO URL and SLO URL
5. ✅ User groups assigned
6. ✅ Any conditional access policies applied

---

**Thank you for setting up SAML SSO for the Zinnia Axion platform!**

---

**Prepared by:** Atharva Tippe  
**Project:** Zinnia Axion - Enterprise Productivity Intelligence Platform  
**Protocol:** SAML 2.0  
**Document Version:** 1.0  
**Last Updated:** March 24, 2026
