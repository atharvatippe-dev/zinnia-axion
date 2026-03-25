# SAML SSO - Quick Reference Card

**For:** Senior Infrastructure Engineer  
**App:** Zinnia Axion Admin Dashboard  
**Protocol:** SAML 2.0

---

## ✅ Quick Setup Checklist

### 1. SAML Application Configuration

```yaml
App Name: Zinnia Axion - Admin Dashboard
Protocol: SAML 2.0
Integration Type: Custom / Non-gallery
```

### 2. Service Provider (SP) URLs

```
Entity ID (Identifier):
https://axion.yourcompany.com/saml/metadata

ACS URL (Reply URL):
https://axion.yourcompany.com/saml/acs

Single Logout URL:
https://axion.yourcompany.com/saml/slo

Sign-on URL:
https://axion.yourcompany.com/admin/login
```

### 3. Required User Attributes

```
SAML Attribute Mappings:
  email       → user.mail (or user.email)
  firstName   → user.givenname (or user.firstName)
  lastName    → user.surname (or user.lastName)
  displayName → user.displayname (or user.displayName)
```

### 4. NameID Format

```
urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress

Value: User's email address
```

### 5. Signing Configuration

```
Sign SAML Assertions: ✅ Yes
Sign SAML Response: ✅ Yes
Signature Algorithm: RSA-SHA256
Certificate: X.509 (RSA 2048-bit minimum)
```

---

## 📋 Information Needed From You

Please provide these items:

### Option 1: IdP Metadata URL (Preferred)
```
Metadata URL: _____________________________________
```

### Option 2: Manual Configuration
```
1. IdP Entity ID:  _____________________________________
2. SSO URL:        _____________________________________
3. SLO URL:        _____________________________________
4. X.509 Cert:     (paste full certificate below)

-----BEGIN CERTIFICATE-----
_____________________________________
_____________________________________
-----END CERTIFICATE-----
```

---

## 👥 User Assignment

**Assign these groups:**
- ✅ Team Managers
- ✅ Engineering Managers
- ✅ Department Heads

**Do NOT assign:**
- ❌ Regular employees

**Estimated Users:** 10-50 managers

---

## 🔐 Security Settings

```yaml
Binding: HTTP-POST
Sign Assertions: Yes
Require MFA: Recommended
Session Lifetime: 8 hours recommended
Conditional Access: Enable if available
```

---

## 🌐 For Azure AD Specifically

### Basic SAML Configuration:
```
Identifier (Entity ID):
https://axion.yourcompany.com/saml/metadata

Reply URL (Assertion Consumer Service URL):
https://axion.yourcompany.com/saml/acs

Sign on URL:
https://axion.yourcompany.com/admin/login

Logout URL:
https://axion.yourcompany.com/saml/slo
```

### User Attributes & Claims:
```
http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress
  → user.mail

http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname
  → user.givenname

http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname
  → user.surname

http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name
  → user.displayname
```

### What to Send Us:
```
1. Azure AD Identifier (Entity ID)
2. Login URL (SSO URL)
3. Logout URL
4. Certificate (Base64)
```

---

## 🌐 For Okta Specifically

### SAML Settings:
```
Single sign on URL:
https://axion.yourcompany.com/saml/acs

Audience URI (SP Entity ID):
https://axion.yourcompany.com/saml/metadata

Name ID format: EmailAddress
Application username: Email
```

### Attribute Statements:
```
Name: email       | Value: user.email
Name: firstName   | Value: user.firstName
Name: lastName    | Value: user.lastName
Name: displayName | Value: user.displayName
```

### What to Send Us:
```
Identity Provider metadata link (from View Setup Instructions)
OR
Download metadata XML file
```

---

## ⚡ Quick Test (After Setup)

### From Azure AD:
```
1. Go to Enterprise Application → Zinnia Axion
2. Click "Test this application"
3. Should redirect to our ACS URL
```

### From Okta:
```
1. Go to Application → Zinnia Axion → General
2. Click "View Setup Instructions"
3. Copy metadata URL
```

---

## 📧 Send Configuration To:

**Email:** atharva.tippe@zinnia.com  
**Subject:** Zinnia Axion - SAML SSO Configuration

**Include:**
- IdP Metadata URL (or manual details)
- X.509 Certificate
- SSO and SLO URLs
- IdP Entity ID

---

## 🔄 What Happens Next

1. You configure SAML app in your IdP ✅
2. You send us IdP details ✅
3. We integrate SAML in backend code ✅
4. We deploy to AWS ECS ✅
5. We test SSO login flow ✅
6. Production go-live ✅

---

**Questions?** Contact Atharva Tippe - atharva.tippe@zinnia.com

---

**Full Details:** See `SAML_SSO_SETUP_REQUEST.md` for complete documentation
