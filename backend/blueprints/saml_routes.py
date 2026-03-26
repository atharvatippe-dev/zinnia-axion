"""
SAML 2.0 SSO routes for admin authentication.

Routes:
  GET  /admin/saml/metadata  — Service Provider metadata (for IdP registration)
  POST /admin/saml/acs       — Assertion Consumer Service (handles SAML login)
  GET  /admin/saml/slo       — Single Logout (handles SAML logout)
  GET  /admin/saml/login     — Initiate SAML login
"""

from __future__ import annotations

import logging
from flask import (
    Blueprint, request, session, redirect, url_for, jsonify,
    render_template, current_app, g,
)

from backend.models import db, User, Team, Manager
from backend.auth.saml import (
    init_saml_auth, get_sp_settings, validate_saml_response,
    extract_user_info_from_saml, generate_saml_metadata,
)
from backend.audit import log_action
from backend.auth.team_hierarchy import get_allowed_team_ids

logger = logging.getLogger("backend.blueprints.saml_routes")

saml_bp = Blueprint("saml", __name__, url_prefix="/saml")


# ── SAML Metadata ────────────────────────────────────────────────────


@saml_bp.route("/metadata", methods=["GET"])
def saml_metadata():
    """
    Return Service Provider (SP) SAML metadata.
    
    This is used by the IdP admin to register this application.
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


# ── SAML Login Flow ──────────────────────────────────────────────────


@saml_bp.route("/login", methods=["GET"])
def saml_login():
    """
    Initiate SAML login by redirecting to IdP.
    """
    cfg = current_app.config
    
    if not cfg.get("SAML_ENABLED"):
        return jsonify({"error": "SAML not enabled"}), 503
    
    if not cfg.SAML_IDP_METADATA_XML:
        logger.error("SAML IdP metadata not configured")
        return jsonify({"error": "SAML not properly configured"}), 500
    
    try:
        sp_settings = get_sp_settings(cfg)
        auth = init_saml_auth(cfg, request, sp_settings)
        
        # Generate SAML AuthnRequest and redirect to IdP
        sso_url = auth.login()
        logger.info(f"Redirecting to IdP SSO: {sso_url}")
        
        return redirect(sso_url)
    except Exception as e:
        logger.error(f"Error initiating SAML login: {e}", exc_info=True)
        return jsonify({"error": "SAML login initiation failed"}), 500


# ── SAML Assertion Consumer Service (ACS) ──────────────────────────


@saml_bp.route("/acs", methods=["POST"])
def saml_acs():
    """
    Handle SAML assertion from IdP (Assertion Consumer Service).
    
    Validates the SAML response, extracts user attributes,
    creates/updates user record, and establishes session.
    """
    cfg = current_app.config
    
    if not cfg.get("SAML_ENABLED"):
        return jsonify({"error": "SAML not enabled"}), 503
    
    if not cfg.SAML_IDP_METADATA_XML:
        logger.error("SAML IdP metadata not configured")
        return jsonify({"error": "SAML not properly configured"}), 500
    
    try:
        sp_settings = get_sp_settings(cfg)
        auth = init_saml_auth(cfg, request, sp_settings)
        
        # Validate SAML response
        is_valid, errors, attributes = validate_saml_response(auth, cfg)
        
        if not is_valid:
            logger.warning(f"SAML validation failed: {errors}")
            log_action("anonymous", "saml_login_failed", detail=f"SAML validation error: {errors}")
            return render_template(
                "admin/login.html",
                error="SAML authentication failed. Please try again."
            ), 401
        
        # Extract user information
        user_info = extract_user_info_from_saml(attributes)
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
                error="User is not authorized as a manager. Please contact your administrator."
            ), 403
        
        # Create session
        session["user_id"] = user.id
        session["team_id"] = manager.team_id
        session["role"] = user.role
        session["display_name"] = user.display_name
        session.permanent = True
        
        logger.info(f"SAML session created for {user.lan_id} in team {manager.team_id}")
        log_action(user.lan_id, "saml_login_success", detail=f"SAML login successful, team={manager.team_id}")
        
        # Redirect to admin dashboard
        return redirect(url_for("admin.admin_dashboard"))
        
    except Exception as e:
        logger.error(f"SAML ACS processing failed: {e}", exc_info=True)
        log_action("anonymous", "saml_acs_error", detail=f"SAML ACS error: {str(e)}")
        return render_template(
            "admin/login.html",
            error="An error occurred during authentication. Please try again."
        ), 500


# ── SAML Single Logout (SLO) ────────────────────────────────────────


@saml_bp.route("/slo", methods=["GET", "POST"])
def saml_slo():
    """
    Handle SAML Single Logout (SLO) from IdP.
    
    Clears the user session and optionally redirects to IdP logout URL.
    """
    cfg = current_app.config
    
    if not cfg.get("SAML_ENABLED"):
        return jsonify({"error": "SAML not enabled"}), 503
    
    if not cfg.SAML_IDP_METADATA_XML:
        logger.error("SAML IdP metadata not configured")
        return jsonify({"error": "SAML not properly configured"}), 500
    
    try:
        user_id = session.get("user_id")
        if user_id:
            user = db.session.get(User, user_id)
            log_action(user.lan_id if user else "unknown", "saml_logout", detail="SAML logout")
        
        # Clear session
        session.clear()
        
        logger.info("SAML logout completed")
        
        # Redirect to login page or home
        return redirect(url_for("admin.admin_login"))
        
    except Exception as e:
        logger.error(f"SAML SLO processing failed: {e}", exc_info=True)
        session.clear()
        return redirect(url_for("admin.admin_login"))
