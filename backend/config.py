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

    # ── Logging ─────────────────────────────────────────────────
    # Centralized logging configuration (see backend/logging_config.py)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() in ("true", "1", "yes")
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # ── Productivity thresholds (scaled for 60-second buckets / 60 samples) ──
    BUCKET_SIZE_SEC: int = int(os.getenv("BUCKET_SIZE_SEC", "60"))
    PRODUCTIVE_INTERACTION_THRESHOLD: int = int(
        os.getenv("PRODUCTIVE_INTERACTION_THRESHOLD", "12")
    )
    PRODUCTIVE_KEYSTROKE_THRESHOLD: int = int(
        os.getenv("PRODUCTIVE_KEYSTROKE_THRESHOLD", "6")
    )
    PRODUCTIVE_MOUSE_THRESHOLD: int = int(
        os.getenv("PRODUCTIVE_MOUSE_THRESHOLD", "6")
    )

    # ── Confidence threshold (v2 decision tree) ──────────────────
    CONFIDENCE_THRESHOLD: float = float(
        os.getenv("CONFIDENCE_THRESHOLD", "0.60")
    )

    # ── Reading / Active Presence detection (scaled for 60s buckets) ──
    MOUSE_MOVEMENT_THRESHOLD: float = float(
        os.getenv("MOUSE_MOVEMENT_THRESHOLD", "48")
    )
    IDLE_AWAY_THRESHOLD: float = float(
        os.getenv("IDLE_AWAY_THRESHOLD", "30")
    )
    # With 10s polling: 3 out of 6 samples should have mouse movement
    MOUSE_MOVEMENT_MIN_SAMPLES: int = int(
        os.getenv("MOUSE_MOVEMENT_MIN_SAMPLES", "3")
    )

    # ── Anti-cheat: Interaction variance (scaled for 60s buckets) ──
    MIN_ZERO_SAMPLE_RATIO: float = float(
        os.getenv("MIN_ZERO_SAMPLE_RATIO", "0.25")
    )
    MIN_DISTINCT_VALUES: int = int(
        os.getenv("MIN_DISTINCT_VALUES", "3")
    )

    # ── Multi-monitor / Split-screen / PiP distraction ─────────
    DISTRACTION_MIN_RATIO: float = float(
        os.getenv("DISTRACTION_MIN_RATIO", "0.3")
    )

    # ── Decision tree v2: rule thresholds ─────────────────────────
    PRODUCTIVE_DOMINANT_RATIO: float = float(
        os.getenv("PRODUCTIVE_DOMINANT_RATIO", "0.70")
    )
    NON_PROD_DOMINANT_RATIO: float = float(
        os.getenv("NON_PROD_DOMINANT_RATIO", "0.6667")
    )
    MEETING_DOMINANT_RATIO: float = float(
        os.getenv("MEETING_DOMINANT_RATIO", "0.50")
    )
    DISTRACTION_CONFIDENCE_MULT: float = float(
        os.getenv("DISTRACTION_CONFIDENCE_MULT", "0.70")
    )
    NON_PROD_MIX_WEIGHT: float = float(
        os.getenv("NON_PROD_MIX_WEIGHT", "0.50")
    )
    ANTI_CHEAT_CONFIDENCE_MULT: float = float(
        os.getenv("ANTI_CHEAT_CONFIDENCE_MULT", "0.30")
    )

    # ── App classification ───────────────────────────────────────
    # Productive apps (if dominant ≥70%, bucket classified as productive)
    PRODUCTIVE_APPS: list[str] = [
        s.strip().lower()
        for s in os.getenv(
            "PRODUCTIVE_APPS",
            "visual studio code,vscode,pycharm,intellij,android studio,xcode,sublime text,atom,vim,emacs,cursor,figma,sketch,adobe photoshop,adobe illustrator,blender,unity,unreal engine,docker,postman,tableau,excel,word,powerpoint,outlook,notion,obsidian,roam research,jira,confluence,linear,asana,trello,monday.com",
        ).split(",")
        if s.strip()
    ]

    # Non-productive apps (if dominant ≥66.67%, bucket classified as non-productive)
    NON_PRODUCTIVE_APPS: list[str] = [
        s.strip().lower()
        for s in os.getenv(
            "NON_PRODUCTIVE_APPS",
            "youtube,netflix,reddit,twitter,x.com,instagram,facebook,tiktok,twitch,discord,spotify,steam,epic games,league of legends,fortnite,valorant,minecraft,roblox",
        ).split(",")
        if s.strip()
    ]

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

    # ── SAML 2.0 SSO Configuration ───────────────────────────────────
    # Service Provider (SP) Configuration
    SAML_ENABLED: bool = os.getenv("SAML_ENABLED", "false").lower() in ("true", "1", "yes")
    SAML_SP_ENTITY_ID: str = os.getenv(
        "SAML_SP_ENTITY_ID",
        "https://lcawsdev-lifecad-api.zinnia.com/saml/metadata"
    )
    SAML_SP_ACS_URL: str = os.getenv(
        "SAML_SP_ACS_URL",
        "https://lcawsdev-lifecad-api.zinnia.com/saml/acs"
    )
    SAML_SP_SLO_URL: str = os.getenv(
        "SAML_SP_SLO_URL",
        "https://lcawsdev-lifecad-api.zinnia.com/saml/slo"
    )
    
    # Identity Provider (IdP) Configuration
    SAML_IDP_ENTITY_ID: str = os.getenv("SAML_IDP_ENTITY_ID", "")
    SAML_IDP_SSO_URL: str = os.getenv("SAML_IDP_SSO_URL", "")
    SAML_IDP_SLO_URL: str = os.getenv("SAML_IDP_SLO_URL", "")
    SAML_IDP_X509_CERT: str = os.getenv("SAML_IDP_X509_CERT", "")
    SAML_IDP_METADATA_XML: str = os.getenv("SAML_IDP_METADATA_XML", "")
    
    # SAML Signing & Security
    SAML_SIGNING_ENABLED: bool = os.getenv("SAML_SIGNING_ENABLED", "true").lower() in ("true", "1", "yes")
    SAML_SIGNING_KEY: str = os.getenv("SAML_SIGNING_KEY", "")  # PEM-encoded private key
    SAML_SIGNING_CERT: str = os.getenv("SAML_SIGNING_CERT", "")  # PEM-encoded certificate

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
    # Defaults to True in production (DEMO_MODE=false), False in demo mode
    SESSION_COOKIE_SECURE: bool = os.getenv(
        "SESSION_COOKIE_SECURE",
        "false" if os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes") else "true",
    ).lower() in ("true", "1", "yes")
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME_MINUTES: int = int(os.getenv("PERMANENT_SESSION_LIFETIME_MINUTES", "30"))
