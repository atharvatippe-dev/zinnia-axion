"""
Admin blueprint — OIDC SSO login + hierarchical team-scoped dashboard.

All data endpoints enforce hierarchical visibility: a manager sees their
own team plus all descendant teams. team_id is NEVER accepted from the
client — it is always derived server-side from the manager's session.

Auth routes:
  GET  /admin/me        — current manager identity + team info
  GET  /admin/login     — SSO login (OIDC or demo)
  GET  /admin/callback  — OIDC callback
  POST /admin/logout    — clear session

Dashboard routes (all team-scoped via g.allowed_team_ids):
  GET  /admin/dashboard        — team overview (HTML)
  GET  /admin/teams            — team tree for allowed subtree
  GET  /admin/users            — list users in allowed teams
  GET  /admin/leaderboard      — team leaderboard (JSON)
  GET  /admin/user/<uid>/*     — user-level data (scoped)
  DELETE /admin/user/<uid>     — delete user telemetry (scoped)
  GET  /admin/tracker-status   — online/offline status (scoped)
  GET  /admin/audit-log        — audit log entries

Team management:
  POST /admin/users/<uid>/assign_to_my_team
  POST /admin/users/<uid>/remove_from_my_team
  POST /admin/users/<uid>/request_move_to_my_team
  POST /admin/team_change_requests/<id>/approve

Device token management:
  POST /admin/device-tokens
  POST /admin/device-tokens/<id>/revoke
  POST /admin/device-tokens/<id>/rotate
"""

from __future__ import annotations

import logging
import secrets
from collections import defaultdict
from datetime import datetime, timezone

from flask import (
    Blueprint, request, jsonify, session, redirect, url_for,
    render_template, g, current_app,
)

from backend.models import db, TelemetryEvent, AuditLog, User, Team, Membership, Manager
from backend.auth.authz import (
    admin_required, team_scoped, get_current_manager,
    assert_team_in_scope, assert_user_in_scope,
)
from backend.auth.oidc import oauth, is_oidc_configured, generate_nonce
from backend.audit import log_action
from backend.productivity import bucketize, summarize_buckets, app_breakdown
from backend.utils import get_config, resolve_range, base_query, today_range, get_local_tz

logger = logging.getLogger("backend.blueprints.admin")

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Scoped user resolution ──────────────────────────────────────────


def _get_scoped_user_ids() -> list[str]:
    """Return LAN IDs of users within g.allowed_team_ids."""
    allowed = getattr(g, "allowed_team_ids", [])
    if not allowed:
        return []
    rows = (
        db.session.query(User.lan_id)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.team_id.in_(allowed), Membership.active.is_(True))
        .all()
    )
    return [r[0] for r in rows]


# ─── Auth routes ────────────────────────────────────────────────────


@admin_bp.route("/me", methods=["GET"])
def admin_me():
    """Return the current manager's identity, team, and hierarchy info."""
    if current_app.config.get("DEMO_MODE", True):
        from backend.auth.authz import _resolve_demo_manager
        uid, tid, role = _resolve_demo_manager()
        if uid:
            user = db.session.get(User, uid)
            team = db.session.get(Team, tid) if tid else None
            if user and team:
                from backend.auth.team_hierarchy import get_allowed_team_ids
                allowed = get_allowed_team_ids(tid) if tid else []
                return jsonify({
                    "user_id": uid,
                    "manager_name": user.display_name,
                    "manager_email": user.email,
                    "team_name": team.name,
                    "team_id": team.id,
                    "role": role,
                    "allowed_team_ids": allowed,
                })
        return jsonify({
            "user_id": None,
            "manager_name": "Admin",
            "manager_email": "admin@local",
            "team_name": "Default",
            "team_id": None,
            "role": "superadmin",
            "allowed_team_ids": [],
        })

    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not authenticated"}), 401
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    mgr = Manager.query.filter_by(user_id=uid).first()
    team = db.session.get(Team, mgr.team_id) if mgr else None

    from backend.auth.team_hierarchy import get_allowed_team_ids
    allowed = get_allowed_team_ids(mgr.team_id) if mgr else []

    return jsonify({
        "user_id": uid,
        "manager_name": user.display_name or user.lan_id,
        "manager_email": user.email,
        "team_name": team.name if team else "Unassigned",
        "team_id": team.id if team else None,
        "role": user.role,
        "allowed_team_ids": allowed,
    })


@admin_bp.route("/login", methods=["GET"])
def admin_login():
    """Render SSO login page or start OIDC flow."""
    if current_app.config.get("DEMO_MODE", True):
        demo_lan = request.args.get("as")
        if demo_lan:
            user = User.query.filter_by(lan_id=demo_lan).first()
            mgr = Manager.query.filter_by(user_id=user.id).first() if user else None
        else:
            mgr = Manager.query.first()
        if mgr:
            session["user_id"] = mgr.user_id
            session["team_id"] = mgr.team_id
            session["role"] = mgr.user.role if mgr.user else "manager"
            session["display_name"] = mgr.user.display_name if mgr.user else "Manager"
        else:
            session["user_id"] = None
            session["team_id"] = None
            session["role"] = "superadmin"
        if demo_lan:
            return jsonify({"user_id": mgr.user_id if mgr else None})
        return redirect(url_for("admin.admin_dashboard"))

    if is_oidc_configured():
        nonce = generate_nonce()
        session["oidc_nonce"] = nonce
        redirect_uri = current_app.config["OIDC_REDIRECT_URI"]
        return oauth.oidc.authorize_redirect(redirect_uri, nonce=nonce)

    return render_template("admin/login.html")


@admin_bp.route("/callback", methods=["GET"])
def admin_callback():
    """Handle OIDC callback — exchange code, validate, set up session."""
    if current_app.config.get("DEMO_MODE", True):
        return redirect(url_for("admin.admin_dashboard"))

    if not is_oidc_configured():
        return jsonify({"error": "OIDC not configured"}), 500

    try:
        token = oauth.oidc.authorize_access_token()
    except Exception as exc:
        logger.error("OIDC token exchange failed: %s", exc)
        log_action("anonymous", "admin_login_failed", detail=f"OIDC token exchange error: {exc}")
        return render_template("admin/login.html", error="SSO authentication failed. Please try again."), 401

    nonce = session.pop("oidc_nonce", None)
    userinfo = token.get("userinfo", {})

    if not userinfo:
        try:
            userinfo = oauth.oidc.parse_id_token(token, nonce=nonce)
        except Exception as exc:
            logger.error("ID token parse failed: %s", exc)
            log_action("anonymous", "admin_login_failed", detail=f"ID token parse error: {exc}")
            return render_template("admin/login.html", error="Token validation failed."), 401

    email = (
        userinfo.get("email")
        or userinfo.get("preferred_username")
        or userinfo.get("upn")
        or ""
    ).strip().lower()
    sub = userinfo.get("sub", "")

    if not email and not sub:
        log_action("anonymous", "admin_login_failed", detail="No email or sub in ID token")
        return render_template("admin/login.html", error="Identity not found in SSO response."), 401

    user = User.query.filter(
        db.or_(User.email == email, User.lan_id == email)
    ).first() if email else None

    if not user and sub:
        user = User.query.filter_by(lan_id=sub).first()

    if not user:
        log_action("anonymous", "admin_login_failed", detail=f"No user record for email={email} sub={sub}")
        return render_template("admin/login.html", error="Your account is not registered in the system."), 403

    if user.role not in ("manager", "superadmin"):
        log_action(user.lan_id, "admin_login_failed", detail=f"User role is {user.role}, not manager/superadmin")
        return render_template("admin/login.html", error="You do not have admin access."), 403

    manager_record = Manager.query.filter_by(user_id=user.id).first()
    if not manager_record:
        log_action(user.lan_id, "admin_login_failed", detail="No manager record found")
        return render_template("admin/login.html", error="No team assignment found for your account."), 403

    session.permanent = True
    session["user_id"] = user.id
    session["team_id"] = manager_record.team_id
    session["role"] = user.role
    session["email"] = email
    session["display_name"] = user.display_name or email

    log_action(user.lan_id, "admin_login_success", detail=f"team_id={manager_record.team_id}")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/logout", methods=["POST"])
def admin_logout():
    """Clear session and redirect to login."""
    user_id = session.get("user_id")
    if user_id:
        user = db.session.get(User, user_id)
        log_action(user.lan_id if user else str(user_id), "admin_logout")
    session.clear()
    return redirect(url_for("admin.admin_login"))


# ─── Dashboard routes ───────────────────────────────────────────────


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
@team_scoped
def admin_dashboard():
    """Render the hierarchical-scoped admin dashboard."""
    from backend.services.admin_service import get_team_leaderboard, get_team_info

    cfg = get_config()
    team_id = g.current_team_id
    allowed = getattr(g, "allowed_team_ids", [])

    team_info = get_team_info(team_id, allowed)
    leaderboard = get_team_leaderboard(allowed, cfg)

    return render_template(
        "admin/dashboard.html",
        team=team_info,
        leaderboard=leaderboard,
        display_name=session.get("display_name", "Admin"),
        demo_mode=current_app.config.get("DEMO_MODE", True),
    )


@admin_bp.route("/teams", methods=["GET"])
@admin_required
@team_scoped
def admin_teams():
    """Return the team tree restricted to the manager's allowed subtree."""
    from backend.services.admin_service import get_team_tree
    allowed = getattr(g, "allowed_team_ids", [])
    tree = get_team_tree(allowed)
    return jsonify(tree), 200


@admin_bp.route("/users", methods=["GET"])
@admin_required
@team_scoped
def admin_users():
    """List users in the manager's allowed team subtree."""
    from backend.services.admin_service import list_team_users

    allowed = getattr(g, "allowed_team_ids", [])
    users = list_team_users(allowed)

    log_action(
        str(g.current_user_id or "demo"),
        "view_team_users",
        detail=f"allowed_teams={allowed}, count={len(users)}",
    )
    return jsonify([u.to_dict() for u in users]), 200


# ─── Team management ────────────────────────────────────────────────


@admin_bp.route("/users/<int:user_id>/assign_to_my_team", methods=["POST"])
@admin_required
@team_scoped
def assign_user(user_id: int):
    """Assign a user to the manager's own team."""
    from backend.services.admin_service import assign_user_to_team

    team_id = g.current_team_id
    assert_team_in_scope(team_id)
    result = assign_user_to_team(user_id, team_id, g.current_user_id)
    return jsonify(result), result.get("status_code", 200)


@admin_bp.route("/users/<int:user_id>/remove_from_my_team", methods=["POST"])
@admin_required
@team_scoped
def remove_user(user_id: int):
    """Remove a user from the manager's own team."""
    from backend.services.admin_service import remove_user_from_team

    team_id = g.current_team_id
    assert_team_in_scope(team_id)
    result = remove_user_from_team(user_id, team_id, g.current_user_id)
    return jsonify(result), result.get("status_code", 200)


@admin_bp.route("/users/<int:user_id>/request_move_to_my_team", methods=["POST"])
@admin_required
@team_scoped
def request_move(user_id: int):
    """Request to move a user from another team to the manager's team."""
    from backend.services.admin_service import request_move_to_team

    team_id = g.current_team_id
    assert_team_in_scope(team_id)
    result = request_move_to_team(user_id, team_id, g.current_user_id)
    return jsonify(result), result.get("status_code", 200)


@admin_bp.route("/team_change_requests/<int:request_id>/approve", methods=["POST"])
@admin_required
@team_scoped
def approve_change_request(request_id: int):
    """Approve a team change request."""
    from backend.services.admin_service import approve_team_change

    allowed = getattr(g, "allowed_team_ids", [])
    result = approve_team_change(request_id, g.current_user_id, allowed)
    return jsonify(result), result.get("status_code", 200)


# ─── Leaderboard + user data endpoints (hierarchically scoped) ─────


@admin_bp.route("/leaderboard", methods=["GET"])
@admin_required
@team_scoped
def admin_leaderboard():
    """Team leaderboard — users in allowed subtree, sorted by NP% descending."""
    from backend.services.admin_service import get_team_leaderboard

    cfg = get_config()
    allowed = getattr(g, "allowed_team_ids", [])
    rows = get_team_leaderboard(allowed, cfg)
    return jsonify(rows), 200


@admin_bp.route("/user/<user_id>/non-productive-apps", methods=["GET"])
@admin_required
@team_scoped
def admin_user_non_productive_apps(user_id: str):
    """Non-productive app breakdown for a user (hierarchy-scoped)."""
    assert_user_in_scope(user_id)

    cfg = get_config()
    start, end = resolve_range(cfg)
    events = base_query(start, end, user_id).all()
    buckets = bucketize(events, cfg)
    breakdown = app_breakdown(buckets, cfg)

    np_apps: list[dict] = []
    for entry in breakdown:
        np_secs = entry.get("states", {}).get("non_productive", 0)
        if np_secs > 0:
            np_apps.append({"app_name": entry["app_name"], "seconds": np_secs})

    np_apps.sort(key=lambda r: r["seconds"], reverse=True)
    return jsonify(np_apps), 200


@admin_bp.route("/user/<user_id>/app-breakdown", methods=["GET"])
@admin_required
@team_scoped
def admin_user_app_breakdown(user_id: str):
    """Full app breakdown for a user (hierarchy-scoped)."""
    assert_user_in_scope(user_id)

    cfg = get_config()
    start, end = resolve_range(cfg)
    events = base_query(start, end, user_id).all()
    buckets = bucketize(events, cfg)
    breakdown = app_breakdown(buckets, cfg)

    result = []
    for entry in breakdown:
        states = entry.get("states", {})
        p = states.get("productive", 0)
        np_val = states.get("non_productive", 0)
        total = p + np_val
        if total > 0:
            result.append({
                "app_name": entry["app_name"],
                "productive": p,
                "non_productive": np_val,
                "total": total,
                "category": entry.get("category", "non_productive"),
            })
    result.sort(key=lambda r: r["total"], reverse=True)
    return jsonify(result), 200


@admin_bp.route("/user/<user_id>", methods=["DELETE"])
@admin_required
@team_scoped
def admin_delete_user(user_id: str):
    """Delete all telemetry events for a given user (hierarchy-scoped)."""
    assert_user_in_scope(user_id)

    count = TelemetryEvent.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    logger.info("Deleted %d events for user %r.", count, user_id)
    log_action(
        str(g.current_user_id or "demo"),
        "delete_user",
        target_user=user_id,
        detail=f"Deleted {count} events",
    )
    return jsonify({"deleted": count, "user_id": user_id}), 200


@admin_bp.route("/tracker-status", methods=["GET"])
@admin_required
@team_scoped
def admin_tracker_status():
    """Online/offline status for users in the manager's allowed subtree."""
    threshold = int(request.args.get("threshold", 60))
    cfg = get_config()
    start, end = today_range(cfg)

    local_tz = get_local_tz(cfg)
    now_naive = datetime.now(local_tz).replace(tzinfo=None)

    q = db.session.query(
        TelemetryEvent.user_id,
        db.func.max(TelemetryEvent.timestamp).label("last_seen"),
    ).filter(
        TelemetryEvent.timestamp >= start,
        TelemetryEvent.timestamp < end,
    )

    allowed = getattr(g, "allowed_team_ids", [])
    if allowed:
        scoped_ids = _get_scoped_user_ids()
        if not scoped_ids:
            return jsonify([]), 200
        q = q.filter(TelemetryEvent.user_id.in_(scoped_ids))

    rows_raw = q.group_by(TelemetryEvent.user_id).all()

    rows = []
    for uid, last_seen in rows_raw:
        ago = (now_naive - last_seen).total_seconds()
        rows.append({
            "user_id": uid,
            "last_seen": last_seen.isoformat(),
            "seconds_ago": round(ago),
            "status": "online" if ago <= threshold else "offline",
        })

    rows.sort(key=lambda r: r["seconds_ago"])
    return jsonify(rows), 200


@admin_bp.route("/audit-log", methods=["GET"])
@admin_required
@team_scoped
def admin_audit_log():
    """Return recent audit log entries."""
    limit = min(int(request.args.get("limit", 100)), 500)
    q = AuditLog.query.order_by(AuditLog.timestamp.desc())

    action_filter = request.args.get("action")
    if action_filter:
        q = q.filter(AuditLog.action == action_filter)

    entries = q.limit(limit).all()
    return jsonify([e.to_dict() for e in entries]), 200


# ─── Device token management ───────────────────────────────────────


@admin_bp.route("/device-tokens", methods=["POST"])
@admin_required
@team_scoped
def create_device_token():
    """Create a new device token for the manager's team."""
    import hashlib
    from backend.models import TrackerDeviceToken

    team_id = g.current_team_id
    if team_id is None:
        return jsonify({"error": "Team context required"}), 400

    assert_team_in_scope(team_id)

    data = request.get_json(silent=True) or {}
    description = data.get("description", "")
    user_id = data.get("user_id")

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    device_token = TrackerDeviceToken(
        token_hash=token_hash,
        team_id=team_id,
        user_id=user_id,
        description=description,
    )
    db.session.add(device_token)
    db.session.commit()

    log_action(
        str(g.current_user_id or "demo"),
        "device_token_created",
        detail=f"token_id={device_token.id} team_id={team_id}",
    )
    return jsonify({
        "id": device_token.id,
        "token": raw_token,
        "team_id": team_id,
        "message": "Store this token securely — it will not be shown again.",
    }), 201


@admin_bp.route("/device-tokens/<int:token_id>/revoke", methods=["POST"])
@admin_required
@team_scoped
def revoke_device_token(token_id: int):
    """Revoke a device token (must be in the manager's subtree)."""
    from backend.models import TrackerDeviceToken

    token = db.session.get(TrackerDeviceToken, token_id)
    if not token:
        return jsonify({"error": "Token not found"}), 404

    assert_team_in_scope(token.team_id)

    token.revoked = True
    db.session.commit()

    log_action(
        str(g.current_user_id or "demo"),
        "device_token_revoked",
        detail=f"token_id={token_id}",
    )
    return jsonify({"message": "Token revoked", "id": token_id}), 200


@admin_bp.route("/device-tokens/<int:token_id>/rotate", methods=["POST"])
@admin_required
@team_scoped
def rotate_device_token(token_id: int):
    """Rotate a device token — revoke old, create new linked to it."""
    import hashlib
    from backend.models import TrackerDeviceToken

    old_token = db.session.get(TrackerDeviceToken, token_id)
    if not old_token:
        return jsonify({"error": "Token not found"}), 404

    assert_team_in_scope(old_token.team_id)

    old_token.revoked = True

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    new_token = TrackerDeviceToken(
        token_hash=token_hash,
        team_id=old_token.team_id,
        user_id=old_token.user_id,
        description=old_token.description,
        rotated_from_id=old_token.id,
    )
    db.session.add(new_token)
    db.session.commit()

    log_action(
        str(g.current_user_id or "demo"),
        "device_token_rotated",
        detail=f"old_id={token_id} new_id={new_token.id}",
    )
    return jsonify({
        "id": new_token.id,
        "token": raw_token,
        "rotated_from": token_id,
        "message": "Store this token securely — it will not be shown again.",
    }), 201
