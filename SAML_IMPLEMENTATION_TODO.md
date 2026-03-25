# SAML SSO Implementation - Technical TODO

**Status:** ⚠️ **SAML Integration Required**  
**Current:** OIDC implemented  
**Needed:** SAML 2.0 integration

---

## Current State

The codebase currently implements **OIDC (OpenID Connect)** SSO in:
- `backend/auth/oidc.py` - OIDC client using Authlib
- `backend/blueprints/admin.py` - Login/callback endpoints for OIDC

**This needs to be replaced with SAML 2.0.**

---

## Required Changes

### 1. Install SAML Library

Add to `requirements.txt`:
```python
python3-saml>=1.15.0
```

**Alternative:** `flask-saml` or `pysaml2`

---

### 2. Create SAML Authentication Module

**New file:** `backend/auth/saml.py`

```python
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

def init_saml(app):
    """Initialize SAML configuration from environment variables."""
    # Read IdP metadata
    # Configure SP settings
    # Set up certificates
    pass

def prepare_saml_request(request):
    """Prepare Flask request for python3-saml."""
    # Convert Flask request to SAML-compatible format
    pass

def get_saml_auth(request):
    """Create SAML Auth object for request."""
    # Return OneLogin_Saml2_Auth instance
    pass
```

---

### 3. Update Admin Blueprint

**File:** `backend/blueprints/admin.py`

Replace OIDC endpoints with SAML endpoints:

```python
@admin_bp.route("/saml/metadata", methods=["GET"])
def saml_metadata():
    """Return SP metadata XML for IdP configuration."""
    # Generate and return SAML metadata
    pass

@admin_bp.route("/admin/login", methods=["GET"])
def admin_login():
    """Initiate SAML SSO login (redirect to IdP)."""
    # Generate SAML AuthnRequest
    # Redirect to IdP SSO URL
    pass

@admin_bp.route("/saml/acs", methods=["POST"])
def saml_acs():
    """Assertion Consumer Service - handle SAML response from IdP."""
    # Validate SAML assertion
    # Extract user attributes
    # Create session
    # Redirect to admin dashboard
    pass

@admin_bp.route("/saml/slo", methods=["GET", "POST"])
def saml_slo():
    """Single Logout Service - handle logout from IdP."""
    # Process logout request
    # Clear session
    # Redirect to home or IdP
    pass
```

---

### 4. Configuration in `backend/config.py`

Replace OIDC config with SAML config:

```python
class Config:
    # Remove OIDC config
    # OIDC_ISSUER_URL: str = ...
    # OIDC_CLIENT_ID: str = ...
    # OIDC_CLIENT_SECRET: str = ...
    
    # Add SAML config
    SAML_ENABLED: bool = os.getenv("SAML_ENABLED", "false").lower() == "true"
    
    # IdP Configuration
    SAML_IDP_ENTITY_ID: str = os.getenv("SAML_IDP_ENTITY_ID", "")
    SAML_IDP_SSO_URL: str = os.getenv("SAML_IDP_SSO_URL", "")
    SAML_IDP_SLO_URL: str = os.getenv("SAML_IDP_SLO_URL", "")
    SAML_IDP_X509_CERT: str = os.getenv("SAML_IDP_X509_CERT", "")
    
    # SP Configuration
    SAML_SP_ENTITY_ID: str = os.getenv("SAML_SP_ENTITY_ID", "")
    SAML_SP_ACS_URL: str = os.getenv("SAML_SP_ACS_URL", "")
    SAML_SP_SLO_URL: str = os.getenv("SAML_SP_SLO_URL", "")
    
    # Optional: SP certificate for signing requests
    SAML_SP_X509_CERT: str = os.getenv("SAML_SP_X509_CERT", "")
    SAML_SP_PRIVATE_KEY: str = os.getenv("SAML_SP_PRIVATE_KEY", "")
```

---

### 5. Update `.env` and `.env.example`

Replace OIDC variables:

```env
# ─── SAML SSO Configuration ───
SAML_ENABLED=true

# IdP Settings (provided by infrastructure team)
SAML_IDP_ENTITY_ID=https://sts.windows.net/{TENANT_ID}/
SAML_IDP_SSO_URL=https://login.microsoftonline.com/{TENANT_ID}/saml2
SAML_IDP_SLO_URL=https://login.microsoftonline.com/{TENANT_ID}/saml2/logout
SAML_IDP_X509_CERT=-----BEGIN CERTIFICATE-----\nMIIDdzCC...\n-----END CERTIFICATE-----

# SP Settings (our application)
SAML_SP_ENTITY_ID=https://axion.yourcompany.com/saml/metadata
SAML_SP_ACS_URL=https://axion.yourcompany.com/saml/acs
SAML_SP_SLO_URL=https://axion.yourcompany.com/saml/slo

# Optional: SP certificate (if IdP requires signed requests)
SAML_SP_X509_CERT=
SAML_SP_PRIVATE_KEY=
```

---

### 6. User Attribute Mapping

Map SAML attributes to user session:

```python
def extract_saml_attributes(auth):
    """Extract user attributes from SAML assertion."""
    attributes = auth.get_attributes()
    
    return {
        'email': attributes.get('email', [''])[0],
        'first_name': attributes.get('firstName', [''])[0],
        'last_name': attributes.get('lastName', [''])[0],
        'display_name': attributes.get('displayName', [''])[0],
        'employee_id': attributes.get('employeeId', [''])[0],
    }
```

---

### 7. Session Management

Update session storage to use SAML user info:

```python
session['saml_nameid'] = auth.get_nameid()
session['saml_session_index'] = auth.get_session_index()
session['user_email'] = user_attributes['email']
session['manager_name'] = user_attributes['display_name']
# ... rest of session data
```

---

### 8. Testing Strategy

1. **Unit Tests:** Test SAML request/response parsing
2. **Integration Tests:** Mock IdP responses
3. **Manual Testing:** Test with actual Azure AD/Okta

---

## Implementation Priority

### Phase 1: Core SAML (Before Production)
- ✅ Install python3-saml
- ✅ Create `backend/auth/saml.py`
- ✅ Implement login flow (`/admin/login` → IdP)
- ✅ Implement ACS (`/saml/acs` callback)
- ✅ User attribute extraction
- ✅ Session creation

### Phase 2: Metadata & SLO (Production-Ready)
- ✅ SP metadata endpoint (`/saml/metadata`)
- ✅ Single Logout (`/saml/slo`)
- ✅ Certificate management
- ✅ Error handling

### Phase 3: Testing & Documentation
- ✅ Integration tests
- ✅ Manual testing with Azure AD
- ✅ Update documentation

---

## Timeline Estimate

| Task | Estimated Time |
|------|---------------|
| Install & configure python3-saml | 30 minutes |
| Implement core SAML login | 2-3 hours |
| Implement ACS callback | 2 hours |
| Metadata endpoint | 1 hour |
| Single Logout | 1-2 hours |
| Testing & debugging | 2-3 hours |
| **Total** | **1-2 days** |

---

## Dependencies

**Waiting on infrastructure team:**
1. ✅ IdP Metadata URL or manual configuration
2. ✅ X.509 Certificate
3. ✅ SSO and SLO URLs
4. ✅ User group assignments

**Can start now:**
1. ✅ Install python3-saml library
2. ✅ Create SAML module structure
3. ✅ Update configuration files
4. ✅ Write tests (with mocked IdP responses)

---

## Code Example: Minimal SAML Integration

```python
from onelogin.saml2.auth import OneLogin_Saml2_Auth

@admin_bp.route("/admin/login", methods=["GET"])
def admin_login():
    """Initiate SAML SSO."""
    req = prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, get_saml_settings())
    return redirect(auth.login())

@admin_bp.route("/saml/acs", methods=["POST"])
def saml_acs():
    """Handle SAML response."""
    req = prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, get_saml_settings())
    auth.process_response()
    
    if not auth.is_authenticated():
        return "Authentication failed", 401
    
    # Extract user info
    attributes = auth.get_attributes()
    email = attributes['email'][0]
    name = attributes['displayName'][0]
    
    # Create session
    session['user_email'] = email
    session['manager_name'] = name
    
    return redirect('/admin/dashboard')
```

---

## Next Steps

1. **Wait for backend URL from DevOps** (for correct SP Entity ID and ACS URL)
2. **Send SAML SSO request to infrastructure team** (using `SAML_SSO_SETUP_REQUEST.md`)
3. **Receive IdP configuration** (metadata, certificate, URLs)
4. **Implement SAML integration** (1-2 days development)
5. **Test with Azure AD** (30 minutes - 1 hour)
6. **Deploy to production**

---

## Questions?

Contact Atharva Tippe for implementation details.

---

**Status:** 🔶 Waiting for IdP configuration from infrastructure team  
**Blocker:** Backend URL (from AWS ECS deployment)
