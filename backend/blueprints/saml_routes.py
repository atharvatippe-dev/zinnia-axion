"""
SAML 2.0 SSO routes for admin authentication.

Routes:
  GET  /saml/metadata  — Service Provider metadata (for IdP registration)
  GET  /saml/login     — Initiate SAML login (redirect to Azure AD)
  POST /saml/acs       — Assertion Consumer Service (handle SAML response)
  GET  /saml/slo       — Single Logout (handle SAML logout)
"""

from __future__ import annotations

import logging
from flask import (
    Blueprint, request, session, redirect, url_for, jsonify,
    render_template, current_app, g,
)

from backend.models import db, User, Team, Manager
from backend.auth.saml import (
    create_authn_request, parse_saml_response,
    extract_user_from_saml, generate_saml_metadata,
)
from backend.audit import log_action
from backend.auth.team_hierarchy import get_allowed_team_ids

logger = logging.getLogger("backend.blueprints.saml_routes")

saml_bp = Blueprint("saml", __name__, url_prefix="/saml")


# ── SAML Metadata ────────────────────────────────────────────────────────


@saml_bp.route("/metadata", methods=["GET"])
def saml_metadata():
    """
    Return Service Provider (SP) SAML metadata.
    
    This is used by the IdP admin to register this application in Azure AD.
    No authentication required.
    """
    cfg = current_app.config
    
    if not cfg.get("SAML_ENABLED"):
        return jsonify({"error": "SAML not enabled"}), 503
    
    try:
        metadata_xml = generate_saml_metadata(cfg)
        return metadata_xml, 200, {"Content-Type": "application/xml"}
    except Exception as e:
        logger.error(f"Error generating SAML metadata: {e}")
        return jsonify({"error": "Failed to generate metadata"}), 500


# ── SAML Login Flow ──────────────────────────────────────────────────────


@saml_bp.route("/login", methods=["GET"])
def saml_login():
    """
    Initiate SAML login by redirecting to Azure AD.
    """
    cfg = current_app.config
    
    if not cfg.get("SAML_ENABLED"):
        return jsonify({"error": "SAML not enabled"}), 503
    
    try:
        sp_entity_id = cfg.get("SAML_SP_ENTITY_ID")
        acs_url = cfg.get("SAML_SP_ACS_URL")
        idp_sso_url = cfg.get("SAML_IDP_SSO_URL")
        
        if not all([sp_entity_id, acs_url, idp_sso_url]):
            logger.error("SAML configuration incomplete")
            return jsonify({"error": "SAML not properly configured"}), 500
        
        # Create AuthnRequest and get redirect URL
        redirect_url = create_authn_request(sp_entity_id, acs_url, idp_sso_url)
        
        logger.info(f"Redirecting to Azure AD for SAML login")
        return redirect(redirect_url)
        
    except Exception as e:
        logger.error(f"Error initiating SAML login: {e}", exc_info=True)
        return jsonify({"error": "SAML login initiation failed"}), 500


# ── SAML Assertion Consumer Service (ACS) ────────────────────────────────


@saml_bp.route("/acs", methods=["POST"])
def saml_acs():
    """
    Handle SAML assertion from Azure AD (Assertion Consumer Service).
    
    Validates the SAML response, extracts user attributes,
    creates/updates user record, and establishes session.
    """
    cfg = current_app.config
    
    if not cfg.get("SAML_ENABLED"):
        return jsonify({"error": "SAML not enabled"}), 503
    
    try:
        # Get SAML response from POST
        saml_response = request.form.get('SAMLResponse')
        relay_state = request.form.get('RelayState', '/')
        
        if not saml_response:
            logger.warning("No SAMLResponse in POST data")
            return render_template(
                "admin/login.html",
                error="Invalid SAML response received"
            ), 400
        
        logger.info("Received SAML response from Azure AD")
        
        # Parse SAML response
        attributes = parse_saml_response(saml_response)
        
        if not attributes:
            logger.warning("Failed to parse SAML response")
            return render_template(
                "admin/login.html",
                error="Failed to parse SAML response. Please try again."
            ), 401
        
        # Extract user information
        user_info = extract_user_from_saml(attributes)
        email = user_info.get("email")
        
        if not email:
            logger.warning("No email attribute in SAML response")
            log_action("anonymous", "saml_login_failed", detail="No email in SAML attributes")
            return render_template(
                "admin/login.html",
                error="Email not provided by identity provider. Please contact support."
            ), 401
        
        logger.info(f"SAML user authenticated: {email}")
        
        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            # Create new user from SAML attributes
            lan_id = user_info.get("first_name", "").lower() or email.split("@")[0]
            user = User(
                lan_id=lan_id,
                email=email,
                display_name=user_info.get("display_name") or
                            f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
                role="admin",  # Can be "admin", "manager", "user"
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"Created new user from SAML: {user.lan_id}")
            log_action(user.lan_id, "user_created", detail="User created via SAML SSO")
        else:
            # Update user display name if changed
            new_display_name = user_info.get("display_name") or \
                              f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
            if new_display_name and user.display_name != new_display_name:
                user.display_name = new_display_name
                db.session.commit()
        
        # Check if user has manager role
        manager = Manager.query.filter_by(user_id=user.id).first()
        if not manager:
            logger.warning(f"User {user.lan_id} authenticated but not a manager")
            log_action(user.lan_id, "saml_login_non_manager", detail="SAML user not authorized as manager")
            return render_template(
                "admin/login.html",
                error="Your account is not authorized as a manager. Please contact your administrator."
            ), 403
        
        # Create session
        session['_login_lan_id'] = user.lan_id
        session['_login_user_id'] = user.id
        session['_login_team_ids'] = get_allowed_team_ids(user.id)
        session.permanent = True
        
        logger.info(f"SAML login successful for manager: {user.lan_id}")
        log_action(user.lan_id, "saml_login_success", detail=f"Manager {user.lan_id} logged in via SAML")
        
        # Redirect to admin dashboard
        return redirect(relay_state or url_for('admin.dashboard'))
        
    except Exception as e:
        logger.error(f"Error processing SAML ACS: {e}", exc_info=True)
        return render_template(
            "admin/login.html",
            error="An error occurred during login. Please try again."
        ), 500


# ── SAML Single Logout (SLO) ────────────────────────────────────────────


@saml_bp.route("/slo", methods=["GET", "POST"])
def saml_slo():
    """
    Handle SAML Single Logout (SLO).
    
    Clears local session and optionally redirects to IdP logout.
    """
    cfg = current_app.config
    
    try:
        # Clear session
        user_lan_id = session.get('_login_lan_id', 'unknown')
        session.clear()
        
        logger.info(f"SAML logout for user: {user_lan_id}")
        log_action(user_lan_id, "saml_logout", detail="User logged out via SAML")
        
        # Redirect to login page
        return redirect(url_for('admin.login_page'))
        
    except Exception as e:
        logger.error(f"Error during SAML SLO: {e}", exc_info=True)
        return redirect(url_for('admin.login_page'))
