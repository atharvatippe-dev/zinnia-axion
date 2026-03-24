"""
Flask application factory — REST API for Zinnia Axion.

All route logic lives in blueprints (backend/blueprints/):
  admin_bp   — SSO login, team-scoped dashboard, user management
  tracker_bp — telemetry ingest with device auth
  public_bp  — health, summary, apps, daily, cleanup

Endpoints (backward compatible)
-------------------------------
POST /track                              — ingest telemetry events (batch)
GET  /summary/today[?user_id=]           — productivity state totals for today
GET  /apps[?user_id=]                    — per-app breakdown for today
GET  /daily?days=7[&user_id=]            — daily time-series of state totals
POST /cleanup                            — manually purge old events
GET  /db-stats                           — database size and retention info
GET  /dashboard/<user_id>                — self-contained HTML dashboard
GET  /health                             — simple health check
GET  /admin/login                        — SSO login page
GET  /admin/callback                     — OIDC callback
POST /admin/logout                       — clear session
GET  /admin/dashboard                    — team-scoped admin dashboard
GET  /admin/leaderboard                  — team leaderboard
GET  /admin/user/<user_id>/...           — team-scoped user data
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from backend.config import Config
from backend.models import db, TelemetryEvent
from backend.audit import log_action
from backend.logging_config import setup_logging, log_startup_info

# Note: Logging is configured via setup_logging() in create_app()
logger = logging.getLogger("backend")


def _check_production_config(config: Config) -> None:
    """Verify critical security settings when running in production mode."""
    errors: list[str] = []

    if not config.SECRET_KEY:
        errors.append(
            "SECRET_KEY is not set. Flask needs it to sign session cookies securely. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if not config.OIDC_ISSUER_URL:
        if not config.ADMIN_PASSWORD:
            errors.append(
                "Neither OIDC_ISSUER_URL nor ADMIN_PASSWORD is set. "
                "At least one admin authentication method is required."
            )

    uri = config.SQLALCHEMY_DATABASE_URI
    if uri.startswith("sqlite"):
        errors.append(
            f"DATABASE_URI is set to SQLite ({uri}). "
            "Production deployments should use PostgreSQL for reliability and concurrency."
        )

    if errors:
        logger.error("=" * 70)
        logger.error("PRODUCTION MODE STARTUP FAILED — missing required configuration:")
        logger.error("")
        for i, err in enumerate(errors, 1):
            logger.error("  %d. %s", i, err)
        logger.error("")
        logger.error("Fix these in your .env file, then restart.")
        logger.error("Or set DEMO_MODE=true to run without security enforcement.")
        logger.error("=" * 70)
        raise SystemExit(1)


def _seed_demo_hierarchy(database):
    """Seed a 3-level team hierarchy for demo mode.

    Engineering (Nikhil — VP)
      ├── Lifecad (Wasim — Manager)
      │     └── Axion (Atharva — Lead)
      └── Fast (Punit Joshi — Manager)

    Wasim is the default login manager; he sees Lifecad + Axion.
    """
    from backend.models import User, Team, Membership, Manager

    def _ensure_team(name, parent=None):
        t = Team.query.filter_by(name=name).first()
        if not t:
            t = Team(name=name, parent_team_id=parent.id if parent else None)
            database.session.add(t)
            database.session.flush()
            logger.info("Demo seed: created team '%s' (id=%s, parent=%s)",
                        name, t.id, parent.id if parent else None)
        elif parent and t.parent_team_id != parent.id:
            t.parent_team_id = parent.id
        return t

    def _ensure_user(lan_id, email, display_name, role="manager"):
        u = User.query.filter_by(lan_id=lan_id).first()
        if not u:
            u = User(lan_id=lan_id, email=email, display_name=display_name, role=role)
            database.session.add(u)
            database.session.flush()
        else:
            if u.display_name != display_name:
                u.display_name = display_name
            if u.email != email:
                u.email = email
            if u.role != role:
                u.role = role
        return u

    def _ensure_manager(user, team):
        mgr = Manager.query.filter_by(user_id=user.id).first()
        if not mgr:
            mgr = Manager(user_id=user.id, team_id=team.id)
            database.session.add(mgr)
        elif mgr.team_id != team.id:
            mgr.team_id = team.id
        return mgr

    def _ensure_membership(user, team):
        m = Membership.query.filter_by(user_id=user.id, active=True).first()
        if not m:
            m = Membership(user_id=user.id, team_id=team.id, active=True)
            database.session.add(m)
        return m

    team_n = _ensure_team("Engineering")
    team_w = _ensure_team("Lifecad", parent=team_n)
    team_a = _ensure_team("Axion", parent=team_w)
    team_f = _ensure_team("Fast", parent=team_n)

    nikhil = _ensure_user("nikhil", "nikhil@company.local", "Nikhil Saxena", "manager")
    wasim_mgr = _ensure_user("demo_manager", "wasim@company.local", "Wasim Shaikh", "manager")
    atharva_mgr = _ensure_user("atharva_mgr", "atharva@company.local", "Atharva Tippe", "manager")

    _ensure_manager(nikhil, team_n)
    _ensure_manager(wasim_mgr, team_w)
    _ensure_manager(atharva_mgr, team_a)

    _ensure_membership(nikhil, team_n)
    _ensure_membership(wasim_mgr, team_w)
    _ensure_membership(atharva_mgr, team_a)

    punit_mgr = _ensure_user("punit", "punit@company.local", "Punit Joshi", "manager")
    _ensure_manager(punit_mgr, team_f)
    _ensure_membership(punit_mgr, team_f)

    # Tracked users — lan_id must match the USER_ID the tracker agent sends
    atharva_user = _ensure_user("Atharva", "atharva.user@company.local", "Atharva", "user")
    wasim_user = _ensure_user("Wasim", "wasim.user@company.local", "Wasim", "user")
    kumarlu_user = _ensure_user("kumarlu", "kumarlu@company.local", "Kumarlu", "user")
    _ensure_membership(atharva_user, team_a)
    _ensure_membership(wasim_user, team_w)
    _ensure_membership(kumarlu_user, team_f)

    database.session.commit()
    logger.info(
        "Demo seed: hierarchy ready — Engineering(%s) > Lifecad(%s) > Axion(%s), Fast(%s)",
        team_n.id, team_w.id, team_a.id, team_f.id,
    )


def create_app(config: Config | None = None) -> Flask:
    """Application factory."""
    app = Flask(__name__)

    if config is None:
        config = Config()

    # ── Centralized Logging Setup ───────────────────────────────
    # Must be called early before any logging occurs
    setup_logging(app)

    # ── Demo / Production mode gate ─────────────────────────────
    if config.DEMO_MODE:
        logger.warning("=" * 70)
        logger.warning(
            "DEMO MODE ACTIVE — authentication and access control are DISABLED."
        )
        logger.warning(
            "Set DEMO_MODE=false in .env before deploying to production."
        )
        logger.warning("=" * 70)
    else:
        _check_production_config(config)
        logger.info("Production mode enabled — all security features enforced.")

    app.config.from_object(config)
    app.config["SECRET_KEY"] = config.SECRET_KEY or "dev-insecure-key-change-me"
    app.tracker_config = config  # type: ignore[attr-defined]

    # ── Request size limit ──────────────────────────────────────
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_SIZE_KB * 1024

    # ── Session hardening ───────────────────────────────────────
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        minutes=config.PERMANENT_SESSION_LIFETIME_MINUTES
    )
    if not config.DEMO_MODE:
        app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE

    # ── Extensions ──────────────────────────────────────────────
    if config.DEMO_MODE:
        CORS(app)
    else:
        CORS(
            app,
            origins=config.CORS_ALLOWED_ORIGINS,
            supports_credentials=True,
        )

    db.init_app(app)

    # ── CSRF Protection ─────────────────────────────────────────
    csrf = CSRFProtect()
    csrf.init_app(app)
    app.csrf = csrf  # type: ignore[attr-defined]

    # ── Rate Limiting ───────────────────────────────────────────
    def _rate_limit_key():
        return request.headers.get("X-Device-Id", get_remote_address())

    limiter = Limiter(
        key_func=_rate_limit_key,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )
    app.limiter = limiter  # type: ignore[attr-defined]

    # ── OIDC SSO ────────────────────────────────────────────────
    from backend.auth.oidc import init_oidc
    init_oidc(app)

    # ── Middleware ───────────────────────────────────────────────
    from backend.middleware.request_context import init_request_context
    from backend.middleware.security_headers import init_security_headers

    init_request_context(app)
    init_security_headers(app)

    # ── Blueprints ──────────────────────────────────────────────
    from backend.blueprints.admin import admin_bp
    from backend.blueprints.tracker import tracker_bp
    from backend.blueprints.public import public_bp

    # Exempt all blueprints from CSRF — admin APIs are called from Streamlit
    # and JSON clients, not browser forms. The logout form includes a manual
    # CSRF token in the template for defense-in-depth.
    csrf.exempt(admin_bp)
    csrf.exempt(tracker_bp)
    csrf.exempt(public_bp)

    app.register_blueprint(admin_bp)
    app.register_blueprint(tracker_bp)
    app.register_blueprint(public_bp)

    # Apply rate limits to specific endpoints
    limiter.limit(config.RATE_LIMIT_PER_DEVICE)(
        app.view_functions["tracker.track"]
    )
    limiter.limit(config.RATE_LIMIT_PER_DEVICE)(
        app.view_functions["tracker.tracker_ingest"]
    )
    limiter.limit(config.RATE_LIMIT_ADMIN_LOGIN)(
        app.view_functions["admin.admin_login"]
    )

    # ── Error handlers ──────────────────────────────────────────
    @app.errorhandler(413)
    def too_large(e):
        max_kb = config.MAX_REQUEST_SIZE_KB
        device = request.headers.get("X-Device-Id", "unknown")
        log_action(device, "request_too_large",
                   detail=f"Exceeded {max_kb} KB limit")
        return jsonify({
            "error": f"Payload too large. Maximum allowed: {max_kb} KB."
        }), 413

    @app.errorhandler(429)
    def rate_limited(e):
        device = request.headers.get("X-Device-Id", "unknown")
        log_action(device, "rate_limited",
                   detail=str(e.description))
        return jsonify({
            "error": "Too many requests. Slow down.",
            "retry_after": e.description,
        }), 429

    # ── Database initialization ─────────────────────────────────
    with app.app_context():
        db.create_all()
        logger.info("Database tables ensured.")

        inspector = db.inspect(db.engine)
        te_cols = {c["name"] for c in inspector.get_columns("telemetry_events")}

        if "distraction_visible" not in te_cols:
            db.session.execute(
                db.text(
                    "ALTER TABLE telemetry_events "
                    "ADD COLUMN distraction_visible BOOLEAN NOT NULL DEFAULT false"
                )
            )
            db.session.commit()
            logger.info("Migration: added distraction_visible column.")

        if "user_id" not in te_cols:
            db.session.execute(
                db.text(
                    "ALTER TABLE telemetry_events "
                    "ADD COLUMN user_id VARCHAR(128) NOT NULL DEFAULT 'default'"
                )
            )
            db.session.commit()
            logger.info("Migration: added user_id column.")

        # Add parent_team_id to teams if missing (hierarchy support)
        if "teams" in inspector.get_table_names():
            teams_cols = {c["name"] for c in inspector.get_columns("teams")}
            if "parent_team_id" not in teams_cols:
                db.session.execute(
                    db.text("ALTER TABLE teams ADD COLUMN parent_team_id INTEGER REFERENCES teams(id)")
                )
                db.session.commit()
                logger.info("Migration: added teams.parent_team_id column.")

        # Add v2 audit_log columns if missing
        if "audit_log" in inspector.get_table_names():
            al_cols = {c["name"] for c in inspector.get_columns("audit_log")}
            _new_audit_cols = {
                "actor_user_id": "INTEGER",
                "actor_team_id": "INTEGER",
                "target_team_id": "INTEGER",
                "request_id": "VARCHAR(64)",
                "extra_data": "TEXT",
            }
            for col_name, col_type in _new_audit_cols.items():
                if col_name not in al_cols:
                    db.session.execute(
                        db.text(f"ALTER TABLE audit_log ADD COLUMN {col_name} {col_type}")
                    )
                    db.session.commit()
                    logger.info("Migration: added audit_log.%s column.", col_name)

        # ── Demo mode: seed a default team hierarchy ─────────────
        if config.DEMO_MODE:
            _seed_demo_hierarchy(db)

        # Auto-cleanup old events on startup
        from backend.blueprints.public import _run_cleanup
        _run_cleanup(config)

    # ── Log startup information ─────────────────────────────────
    log_startup_info(app)

    return app


# ── Entrypoint for `python -m backend.app` ──────────────────────────
if __name__ == "__main__":
    cfg = Config()
    application = create_app(cfg)
    logger.info("Starting Flask on %s:%s", cfg.FLASK_HOST, cfg.FLASK_PORT)
    application.run(host=cfg.FLASK_HOST, port=cfg.FLASK_PORT, debug=True)
