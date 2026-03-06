"""
Authorization decorators and helpers for admin endpoints.

@admin_required   — verifies the caller is an authenticated manager or superadmin.
@team_scoped      — computes g.allowed_team_ids from manager's team subtree.

Service-level guards:
  assert_team_in_scope(team_id)   — 403 + audit if team_id not in allowed set
  assert_user_in_scope(user_id)   — 403 + audit if user's team not in allowed set

In DEMO_MODE, identity is resolved from:
  1. Flask session (if present — the Streamlit login sets this), or
  2. X-Manager-User-Id header (Streamlit API calls), or
  3. First Manager record in DB (fallback).
team_id is NEVER accepted from the client — always derived server-side.
"""

from __future__ import annotations

import logging
from functools import wraps

from flask import current_app, g, session, abort, redirect, url_for, request

from backend.models import db, User, Manager, Membership

logger = logging.getLogger("backend.auth.authz")


def _is_demo_mode() -> bool:
    return current_app.config.get("DEMO_MODE", True)


def _resolve_demo_manager() -> tuple[int | None, int | None, str]:
    """In demo mode, determine the acting manager from session, header, or DB."""
    uid = session.get("user_id")
    tid = session.get("team_id")
    role = session.get("role")
    if uid and tid and role:
        return uid, tid, role

    header_uid = request.headers.get("X-Manager-User-Id")
    if header_uid:
        try:
            header_uid_int = int(header_uid)
            mgr = Manager.query.filter_by(user_id=header_uid_int).first()
            if mgr:
                return mgr.user_id, mgr.team_id, mgr.user.role if mgr.user else "manager"
        except (ValueError, TypeError):
            pass

    mgr = Manager.query.first()
    if mgr:
        return mgr.user_id, mgr.team_id, mgr.user.role if mgr.user else "manager"
    return None, None, "superadmin"


def get_current_manager() -> tuple[int | None, int | None, str]:
    """Return (user_id, team_id, role) from session. Safe in demo mode."""
    if _is_demo_mode():
        return _resolve_demo_manager()
    user_id = session.get("user_id")
    team_id = session.get("team_id")
    role = session.get("role", "user")
    return user_id, team_id, role


def admin_required(f):
    """Reject unauthenticated or non-admin callers.

    Sets g.current_user_id, g.current_team_id, g.current_role.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if _is_demo_mode():
            uid, tid, role = _resolve_demo_manager()
            g.current_user_id = uid
            g.current_team_id = tid
            g.current_role = role
            return f(*args, **kwargs)

        user_id = session.get("user_id")
        if not user_id:
            logger.warning("Unauthenticated access attempt to admin endpoint.")
            return redirect(url_for("admin.admin_login"))

        user = db.session.get(User, user_id)
        if not user or user.role not in ("manager", "superadmin"):
            logger.warning(
                "Forbidden: user %s (role=%s) attempted admin access.",
                user_id, user.role if user else "N/A",
            )
            abort(403)

        g.current_user_id = user.id
        g.current_team_id = session.get("team_id")
        g.current_role = user.role
        return f(*args, **kwargs)

    return decorated


def team_scoped(f):
    """Must be applied AFTER @admin_required.

    Computes g.allowed_team_ids from the manager's team subtree.
    All downstream code should use g.allowed_team_ids (a list[int])
    instead of a single g.current_team_id.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from backend.auth.team_hierarchy import get_allowed_team_ids

        team_id = g.current_team_id

        if team_id is None:
            g.allowed_team_ids = []
            return f(*args, **kwargs)

        g.allowed_team_ids = get_allowed_team_ids(team_id)

        url_team_id = kwargs.get("team_id")
        if url_team_id is not None:
            try:
                url_tid = int(url_team_id)
                if url_tid not in g.allowed_team_ids:
                    from backend.audit import log_action
                    log_action(
                        actor=str(g.current_user_id),
                        action="cross_team_access_blocked",
                        detail=f"Attempted team_id={url_tid}, allowed={g.allowed_team_ids}",
                        target_team_id=url_tid,
                    )
                    logger.warning(
                        "Cross-team access blocked: user %s tried team %s (allowed %s).",
                        g.current_user_id, url_tid, g.allowed_team_ids,
                    )
                    abort(403)
            except (ValueError, TypeError):
                abort(400)

        return f(*args, **kwargs)

    return decorated


# ── Service-level guards ────────────────────────────────────────────


def assert_team_in_scope(team_id: int) -> None:
    """Abort 403 if team_id is not in the current manager's allowed subtree."""
    allowed = getattr(g, "allowed_team_ids", [])
    if not allowed:
        return
    if team_id not in allowed:
        from backend.audit import log_action
        log_action(
            actor=str(getattr(g, "current_user_id", "unknown")),
            action="idor_team_blocked",
            detail=f"team_id={team_id} not in allowed={allowed}",
            target_team_id=team_id,
        )
        abort(403)


def assert_user_in_scope(user_id: int | str) -> None:
    """Abort 403 if the user's active team is not in the manager's subtree.

    Accepts either a numeric user PK or a string lan_id.
    """
    allowed = getattr(g, "allowed_team_ids", [])
    if not allowed:
        return

    if isinstance(user_id, str):
        membership = (
            db.session.query(Membership.team_id)
            .join(User, User.id == Membership.user_id)
            .filter(User.lan_id == user_id, Membership.active.is_(True))
            .first()
        )
    else:
        membership = (
            Membership.query
            .filter_by(user_id=user_id, active=True)
            .with_entities(Membership.team_id)
            .first()
        )

    if membership is None:
        return

    if membership.team_id not in allowed:
        from backend.audit import log_action
        log_action(
            actor=str(getattr(g, "current_user_id", "unknown")),
            action="idor_user_blocked",
            detail=f"user={user_id} in team={membership.team_id}, allowed={allowed}",
            target_team_id=membership.team_id,
        )
        abort(403)
