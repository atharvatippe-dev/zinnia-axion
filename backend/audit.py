"""
Audit logging helper — one-liner to record security-relevant actions.

Usage from any Flask route:

    from backend.audit import log_action
    log_action("admin", "delete_user", target_user="User_32")

Enhanced v2 supports structured fields:
    log_action(
        "admin", "delete_user",
        target_user="User_32",
        actor_user_id=1, actor_team_id=2,
        metadata={"reason": "requested by user"},
    )
"""

from __future__ import annotations

import json
import logging
from flask import request, has_request_context, g
from backend.models import db, AuditLog

logger = logging.getLogger("backend.audit")


def log_action(
    actor: str,
    action: str,
    *,
    target_user: str | None = None,
    detail: str | None = None,
    actor_user_id: int | None = None,
    actor_team_id: int | None = None,
    target_team_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert one row into the audit_log table.

    Automatically captures IP address, User-Agent, and request_id
    from the current Flask request context (if available).
    """
    ip = None
    ua = None
    request_id = None

    if has_request_context():
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent", "")[:512]
        request_id = getattr(g, "request_id", None)

        if actor_user_id is None:
            actor_user_id = getattr(g, "current_user_id", None)
        if actor_team_id is None:
            actor_team_id = getattr(g, "current_team_id", None)

    extra_data = None
    if metadata:
        try:
            extra_data = json.dumps(metadata)
        except (TypeError, ValueError):
            extra_data = str(metadata)

    entry = AuditLog(
        actor=actor,
        action=action,
        target_user=target_user,
        ip_address=ip,
        user_agent=ua,
        detail=detail[:1024] if detail else None,
        actor_user_id=actor_user_id,
        actor_team_id=actor_team_id,
        target_team_id=target_team_id,
        request_id=request_id,
        extra_data=extra_data,
    )
    db.session.add(entry)
    db.session.commit()

    logger.info(
        "AUDIT | %s | actor=%s target=%s | %s",
        action, actor, target_user or "-", detail or "",
    )
