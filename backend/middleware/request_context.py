"""
Request context middleware.

- Generates a unique request_id (UUID) for every request.
- Attaches the request_id to flask.g for use by audit logging.
- Sets PostgreSQL session variable for Row-Level Security (when applicable).
"""

from __future__ import annotations

import uuid
import logging

from flask import Flask, g, request, session

logger = logging.getLogger("backend.middleware.request_context")


def init_request_context(app: Flask) -> None:
    """Register before/after request hooks for request context."""

    @app.before_request
    def _set_request_context():
        g.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))

        g.current_user_id = session.get("user_id")
        g.current_team_id = session.get("team_id")
        g.current_role = session.get("role", "user")

        if not app.config.get("DEMO_MODE", True) and g.current_team_id:
            _set_rls_context(app, g.current_team_id)

    @app.after_request
    def _add_request_id(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        return response


def _set_rls_context(app: Flask, team_id: int) -> None:
    """Set PostgreSQL session variable for RLS policies."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("postgresql"):
        return

    try:
        from backend.models import db
        db.session.execute(
            db.text("SET LOCAL app.user_team_id = :team_id"),
            {"team_id": str(team_id)},
        )
    except Exception as exc:
        logger.warning("Failed to set RLS context: %s", exc)
