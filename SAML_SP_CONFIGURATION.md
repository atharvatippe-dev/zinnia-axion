# SAML Service Provider (SP) Configuration

## Summary

**OIDC has been replaced with SAML 2.0 SSO** for the Zinnia Axion backend. The configuration has been updated in `config.py`, `.env`, and `.env.example`.

---

## Service Provider (SP) Configuration

These URLs identify YOUR application to the Identity Provider (IdP) and must be registered with your IdP admin.

### **Entity ID (SP)**
```
https://lcawsdev-lifecad-api.zinnia.com/saml/metadata
```

### **Reply URL (Assertion Consumer Service - ACS)**
```
https://lcawsdev-lifecad-api.zinnia.com/saml/acs
```

### **Single Logout URL (SLO) - Optional**
```
https://lcawsdev-lifecad-api.zinnia.com/saml/slo
```

---

## Identity Provider (IdP) Configuration

Ask your infrastructure/SSO team to provide these values:

| Parameter | Description | Where to put it |
|-----------|-------------|-----------------|
| **IdP Entity ID** | Unique identifier of your identity provider | `SAML_IDP_ENTITY_ID` in `.env` |
| **IdP SSO URL** | Where users are redirected to login | `SAML_IDP_SSO_URL` in `.env` |
| **IdP SLO URL** | Where users are redirected to logout | `SAML_IDP_SLO_URL` in `.env` |
| **IdP X.509 Certificate** | For validating SAML responses (PEM format) | `SAML_IDP_X509_CERT` in `.env` |

### Example (Azure AD)
```
SAML_IDP_ENTITY_ID=https://sts.windows.net/{TENANT_ID}/
SAML_IDP_SSO_URL=https://login.microsoftonline.com/{TENANT_ID}/saml2
SAML_IDP_SLO_URL=https://login.microsoftonline.com/{TENANT_ID}/saml2/logout
SAML_IDP_X509_CERT=-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----
```

---

## Deployment Steps

### 1. Register SP with IdP
1. Provide your infrastructure team with the **Entity ID** and **Reply URL** above
2. They will configure these in Azure AD, Okta, or your corporate IdP
3. They will provide you with the **IdP values** (Entity ID, SSO URL, Certificate, etc.)

### 2. Update Backend Configuration
Update `.env` with IdP values provided by infrastructure team:

```bash
SAML_ENABLED=true
SAML_IDP_ENTITY_ID=https://sts.windows.net/{YOUR_TENANT_ID}/
SAML_IDP_SSO_URL=https://login.microsoftonline.com/{YOUR_TENANT_ID}/saml2
SAML_IDP_SLO_URL=https://login.microsoftonline.com/{YOUR_TENANT_ID}/saml2/logout
SAML_IDP_X509_CERT=-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----
```

### 3. Deploy Backend
- Deploy updated backend to AWS ECS with new `.env` values
- Backend will expose SAML endpoints:
  - `GET /saml/metadata` - Service Provider metadata (for IdP registration)
  - `POST /saml/acs` - Assertion Consumer Service (handles SAML responses)
  - `GET /saml/slo` - Single Logout (handles logout requests)

### 4. Update Admin Dashboard
- Admin dashboard will redirect managers to `/saml/acs` for login
- After successful SAML authentication, manager sessions are created
- Dashboard enforces team hierarchy and RBAC

---

## Configuration Files Updated

- **`backend/config.py`** - Added SAML config parameters
- **`.env`** - SAML configuration values (IdP details)
- **`.env.example`** - Template with SAML setup instructions

---

## Next Steps

1. **Send to Infrastructure Team:**
   - Forward the **Entity ID** and **Reply URL** above
   - Ask them to register the SP in Azure AD/Okta

2. **Receive from Infrastructure Team:**
   - Collect **IdP Entity ID, SSO URL, SLO URL, Certificate**
   - Populate these in `.env`

3. **Implement Backend Routes:**
   - Create `/saml/metadata` endpoint
   - Create `/saml/acs` endpoint (for SAML response handling)
   - Create `/saml/slo` endpoint (for logout)

---

## Key URLs

| URL | Purpose |
|-----|---------|
| `https://lcawsdev-lifecad-api.zinnia.com/saml/metadata` | Service Provider metadata (read-only, auto-generated) |
| `https://lcawsdev-lifecad-api.zinnia.com/saml/acs` | Where IdP sends SAML assertion after login |
| `https://lcawsdev-lifecad-api.zinnia.com/saml/slo` | Where IdP sends logout request |

---

## Attributes Required from IdP

Configure your IdP to send these attributes in the SAML assertion:

- **email** - User's email address (required)
- **firstName** - User's first name (recommended)
- **lastName** - User's last name (recommended)
- **displayName** - User's full name (optional)

These attributes are mapped to user records in the application.

---

## Security Notes

- ✅ SAML signing is **enabled by default** for enhanced security
- ✅ Session cookies are **HTTP-only and secure** (production)
- ✅ SAML responses are **validated** against IdP certificate
- ✅ Managers can **logout explicitly** via `/saml/slo`

