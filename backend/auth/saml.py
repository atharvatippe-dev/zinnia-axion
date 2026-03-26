"""
SAML 2.0 Authentication for Zinnia Axion Admin Dashboard.

Integrates with Azure AD (or any SAML 2.0 IdP) for enterprise SSO.
Handles SP metadata generation, SAML assertion validation, and session management.
"""

import base64
import logging
from urllib.parse import urlparse

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

logger = logging.getLogger(__name__)


def init_saml_auth(config, request, sp_settings):
    """
    Initialize SAML Auth object with Flask request context.
    
    Args:
        config: Flask config object with SAML settings
        request: Flask request object
        sp_settings: Service Provider settings dict
    
    Returns:
        OneLogin_Saml2_Auth object
    """
    req = {
        'http_host': request.host,
        'script_name': request.path,
        'get_data': request.args.to_dict(),
        'post_data': request.form.to_dict(),
        'https': 'on' if request.scheme == 'https' else 'off',
    }
    
    auth = OneLogin_Saml2_Auth(req, sp_settings)
    return auth


def get_sp_settings(config):
    """
    Generate Service Provider (SP) settings from Flask config.
    
    Args:
        config: Flask config with SAML settings
    
    Returns:
        dict with SP and IdP settings for python3-saml
    """
    # Extract X509 certificate from IdP metadata XML
    idp_cert = extract_idp_cert_from_metadata(config.SAML_IDP_METADATA_XML)
    
    settings = {
        'sp': {
            'entityID': config.SAML_SP_ENTITY_ID,
            'assertionConsumerService': {
                'url': config.SAML_SP_ACS_URL,
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
            },
            'singleLogoutService': {
                'url': config.SAML_SP_SLO_URL,
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            },
            'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',
            'x509cert': '',
            'privateKey': '',
        },
        'idp': {
            'entityID': config.SAML_IDP_ENTITY_ID,
            'singleSignOnService': {
                'url': config.SAML_IDP_SSO_URL,
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            },
            'singleLogoutService': {
                'url': config.SAML_IDP_SLO_URL,
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            },
            'x509cert': idp_cert,
        },
        'security': {
            'nameIdEncrypted': False,
            'authnRequestsSigned': False,
            'wantAssertionsSigned': True,
            'wantAssertionsEncrypted': False,
            'signMetadata': False,
            'wantNameId': True,
            'wantNameIdEncrypted': False,
            'requestedAuthnContext': {
                'comparison': 'exact',
                'authnContextClassRef': [
                    'urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport'
                ],
            },
        },
    }
    
    return settings


def extract_idp_cert_from_metadata(metadata_xml):
    """
    Extract X509 certificate from IdP metadata XML.
    
    Args:
        metadata_xml: SAML metadata XML string
    
    Returns:
        X509 certificate string (base64 decoded)
    """
    import xml.etree.ElementTree as ET
    
    try:
        root = ET.fromstring(metadata_xml)
        
        # Define namespaces
        namespaces = {
            'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
        }
        
        # Find X509Certificate in IDPSSODescriptor
        cert_elem = root.find(
            './/md:IDPSSODescriptor/md:KeyDescriptor/ds:KeyInfo/ds:X509Data/ds:X509Certificate',
            namespaces
        )
        
        if cert_elem is not None and cert_elem.text:
            cert_data = cert_elem.text.strip()
            return cert_data
        
        logger.warning("No X509Certificate found in IdP metadata")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting certificate from metadata: {e}")
        return None


def validate_saml_response(auth, config):
    """
    Validate SAML response from IdP.
    
    Args:
        auth: OneLogin_Saml2_Auth object
        config: Flask config
    
    Returns:
        tuple: (is_valid, errors, attributes)
    """
    auth.process_response()
    
    errors = auth.get_errors()
    if errors:
        logger.error(f"SAML validation errors: {errors}")
        return False, errors, None
    
    if not auth.is_authenticated():
        logger.warning("User is not authenticated after SAML response")
        return False, ["User not authenticated"], None
    
    # Extract user attributes
    attributes = auth.get_attributes()
    
    return True, [], attributes


def extract_user_info_from_saml(attributes):
    """
    Extract user information from SAML attributes.
    
    Maps SAML attributes to application user fields:
    - email: http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress
    - first_name: http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname
    - last_name: http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname
    - display_name: http://schemas.microsoft.com/identity/claims/displayname
    
    Args:
        attributes: dict of SAML attributes from IdP
    
    Returns:
        dict with user info: email, first_name, last_name, display_name
    """
    user_info = {
        'email': None,
        'first_name': None,
        'last_name': None,
        'display_name': None,
    }
    
    # Map SAML attribute URIs to user fields
    attr_map = {
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress': 'email',
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname': 'first_name',
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname': 'last_name',
        'http://schemas.microsoft.com/identity/claims/displayname': 'display_name',
    }
    
    for saml_attr, user_field in attr_map.items():
        if saml_attr in attributes:
            value = attributes[saml_attr]
            # SAML attributes are lists; get the first value
            if isinstance(value, list) and value:
                user_info[user_field] = value[0]
            elif isinstance(value, str):
                user_info[user_field] = value
    
    # Fallback: use displayName if email not available
    if not user_info['email'] and user_info['display_name']:
        user_info['email'] = user_info['display_name']
    
    logger.info(f"Extracted user info: {user_info}")
    
    return user_info


def generate_saml_metadata(config):
    """
    Generate Service Provider (SP) SAML metadata XML.
    
    Used by IdP admin to register this SP.
    
    Args:
        config: Flask config with SAML settings
    
    Returns:
        XML metadata string
    """
    settings = get_sp_settings(config)
    metadata = OneLogin_Saml2_Utils.metadata_builder(
        settings,
        valid_until=None,
        organization_info={
            'en': {
                'displayname': 'Zinnia Axion',
                'name': 'Zinnia Axion',
                'url': 'https://zinnia.com',
            }
        },
        contacts={
            'technical': {
                'emailAddress': 'tech@zinnia.com',
                'givenName': 'Technical Support',
            },
            'support': {
                'emailAddress': 'support@zinnia.com',
                'givenName': 'Support',
            },
        },
    )
    
    return metadata
