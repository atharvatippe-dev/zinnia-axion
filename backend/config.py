"""
Backend configuration — loaded from environment / .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Config:
    """Flask + app configuration."""

    # ── Flask / DB ──────────────────────────────────────────────
    FLASK_HOST: str = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URI", "sqlite:///telemetry.db")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ── Productivity thresholds (tuned for 10-second buckets) ───
    BUCKET_SIZE_SEC: int = int(os.getenv("BUCKET_SIZE_SEC", "10"))
    PRODUCTIVE_INTERACTION_THRESHOLD: int = int(
        os.getenv("PRODUCTIVE_INTERACTION_THRESHOLD", "2")
    )
    PRODUCTIVE_KEYSTROKE_THRESHOLD: int = int(
        os.getenv("PRODUCTIVE_KEYSTROKE_THRESHOLD", "1")
    )
    PRODUCTIVE_MOUSE_THRESHOLD: int = int(
        os.getenv("PRODUCTIVE_MOUSE_THRESHOLD", "1")
    )

    # ── Reading / Active Presence detection (tuned for 10s buckets) ──
    MOUSE_MOVEMENT_THRESHOLD: float = float(
        os.getenv("MOUSE_MOVEMENT_THRESHOLD", "8")
    )
    IDLE_AWAY_THRESHOLD: float = float(
        os.getenv("IDLE_AWAY_THRESHOLD", "30")
    )
    MOUSE_MOVEMENT_MIN_SAMPLES: int = int(
        os.getenv("MOUSE_MOVEMENT_MIN_SAMPLES", "3")
    )

    # ── Anti-cheat: Interaction variance (tuned for 10s buckets) ──
    MIN_ZERO_SAMPLE_RATIO: float = float(
        os.getenv("MIN_ZERO_SAMPLE_RATIO", "0.25")
    )
    MIN_DISTINCT_VALUES: int = int(
        os.getenv("MIN_DISTINCT_VALUES", "2")
    )

    # ── Multi-monitor / Split-screen / PiP distraction ─────────
    DISTRACTION_MIN_RATIO: float = float(
        os.getenv("DISTRACTION_MIN_RATIO", "0.3")
    )

    # ── Meeting apps (always productive) ────────────────────────
    MEETING_APPS: list[str] = [
        s.strip().lower()
        for s in os.getenv(
            "MEETING_APPS",
            "zoom,microsoft teams,google meet,webex,facetime,slack huddle,discord call,skype,around,tuple,gather",
        ).split(",")
        if s.strip()
    ]

    # ── Data Retention ────────────────────────────────────────────
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "14"))

    # ── Timezone ──────────────────────────────────────────────────
    TIMEZONE: str = os.getenv("TIMEZONE", "UTC")

    # ── Browser apps (website-level breakdown) ──────────────────
    BROWSER_APPS: list[str] = [
        s.strip().lower()
        for s in os.getenv(
            "BROWSER_APPS",
            "safari,google chrome,chrome,firefox,microsoft edge,msedge,brave browser,brave,arc,chromium,opera",
        ).split(",")
        if s.strip()
    ]

    # ── App classification ──────────────────────────────────────
    NON_PRODUCTIVE_APPS: list[str] = [
        s.strip().lower()
        for s in os.getenv(
            "NON_PRODUCTIVE_APPS",
            "youtube,netflix,reddit,twitter,x.com,instagram,facebook,tiktok,twitch,discord,spotify,steam,epic games",
        ).split(",")
        if s.strip()
    ]

    # ── Data Minimization ──────────────────────────────────────
    DROP_TITLES: bool = os.getenv("DROP_TITLES", "false").lower() in ("true", "1", "yes")

    # ── Rate Limiting & Input Validation ────────────────────────
    MAX_REQUEST_SIZE_KB: int = int(os.getenv("MAX_REQUEST_SIZE_KB", "512"))
    RATE_LIMIT_PER_DEVICE: str = os.getenv("RATE_LIMIT_PER_DEVICE", "120/minute")
    RATE_LIMIT_ADMIN_LOGIN: str = os.getenv("RATE_LIMIT_ADMIN_LOGIN", "5/minute")
    RATE_LIMIT_ADMIN_MUTATION: str = os.getenv("RATE_LIMIT_ADMIN_MUTATION", "30/minute")

    # ── Enterprise Hardening ─────────────────────────────────────
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    # Legacy admin credentials (kept for backward compat; OIDC is primary in production)
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # ── OIDC SSO Configuration ───────────────────────────────────
    OIDC_ISSUER_URL: str = os.getenv("OIDC_ISSUER_URL", "")
    OIDC_CLIENT_ID: str = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET: str = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_REDIRECT_URI: str = os.getenv("OIDC_REDIRECT_URI", "http://localhost:5000/admin/callback")
    OIDC_SCOPES: str = os.getenv("OIDC_SCOPES", "openid profile email")

    # ── Break-glass admin login (emergency only) ─────────────────
    ADMIN_BREAK_GLASS: bool = os.getenv("ADMIN_BREAK_GLASS", "false").lower() in ("true", "1", "yes")
    ADMIN_BREAK_GLASS_IPS: list[str] = [
        s.strip()
        for s in os.getenv("ADMIN_BREAK_GLASS_IPS", "127.0.0.1").split(",")
        if s.strip()
    ]

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ALLOWED_ORIGINS: list[str] = [
        s.strip()
        for s in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:8501,http://localhost:8502",
        ).split(",")
        if s.strip()
    ]

    # ── Session ──────────────────────────────────────────────────
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME_MINUTES: int = int(os.getenv("PERMANENT_SESSION_LIFETIME_MINUTES", "30"))
