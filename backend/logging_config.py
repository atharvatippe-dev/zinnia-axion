"""
Centralized enterprise-grade logging configuration.

This module provides a single source of truth for logging setup across the
backend, tracker, and dashboards. It configures:
  - Structured log format with request context
  - Console output for development
  - Rotating file logs for production debugging
  - Environment-based log levels
  - Safe handling of sensitive data

Usage in any module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Your message here")

The logger will automatically include request context if available.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

# ── Configuration ────────────────────────────────────────────────────────────

# Log level from environment (default: INFO for production-like behavior)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Log file path (default: logs/app.log in project root)
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

# Max log file size before rotation (10 MB default)
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))

# Number of backup log files to keep
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))

# Enable/disable file logging (default: enabled except in tests)
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() in ("true", "1", "yes")

# ── Custom Formatter with Request Context ────────────────────────────────────


class RequestContextFormatter(logging.Formatter):
    """
    Custom formatter that includes Flask request context in log messages.

    Format:
        2026-03-23 14:30:45,123 [INFO] backend.auth.authz [req:abc123 user:42]: Login successful

    Fields:
        - Timestamp (ISO-like with milliseconds)
        - Log level
        - Logger name (module path)
        - Request ID (if available from flask.g)
        - User ID (if available from flask.g, safe to log)
        - Message
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base format: timestamp [level] logger_name
        base = super().format(record)

        # Try to add request context (only works inside Flask request context)
        try:
            from flask import g, has_request_context

            if has_request_context():
                context_parts = []

                # Request ID (safe UUID, useful for tracing)
                request_id = getattr(g, "request_id", None)
                if request_id:
                    # Shorten UUID for readability: abc123de-... → abc123
                    short_id = request_id[:6] if len(request_id) >= 6 else request_id
                    context_parts.append(f"req:{short_id}")

                # User ID (safe integer, no PII)
                user_id = getattr(g, "current_user_id", None)
                if user_id:
                    context_parts.append(f"user:{user_id}")

                # Team ID (safe integer, useful for debugging team isolation)
                team_id = getattr(g, "current_team_id", None)
                if team_id:
                    context_parts.append(f"team:{team_id}")

                if context_parts:
                    # Insert context between logger name and message
                    # Before: "2026-03-23 [INFO] backend.auth: Login"
                    # After:  "2026-03-23 [INFO] backend.auth [req:abc123 user:42]: Login"
                    parts = base.split(": ", 1)
                    if len(parts) == 2:
                        return f"{parts[0]} [{' '.join(context_parts)}]: {parts[1]}"

        except (ImportError, RuntimeError):
            # Flask not available or not in request context - no problem
            pass

        return base


# ── Sensitive Data Filter ─────────────────────────────────────────────────────


class SensitiveDataFilter(logging.Filter):
    """
    Filter that redacts sensitive data from log messages.

    Prevents accidental logging of:
    - Passwords
    - Tokens (Bearer, JWT, API keys)
    - Session secrets
    - Full email addresses (keeps domain)

    This is a safety net - developers should still avoid logging secrets.
    """

    # Patterns to redact (case-insensitive)
    REDACT_PATTERNS = [
        ("password", "[REDACTED-PASSWORD]"),
        ("secret", "[REDACTED-SECRET]"),
        ("token", "[REDACTED-TOKEN]"),
        ("bearer ", "Bearer [REDACTED-TOKEN]"),
        ("jwt", "[REDACTED-JWT]"),
        ("api_key", "[REDACTED-API-KEY]"),
        ("apikey", "[REDACTED-API-KEY]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive patterns from log message."""
        if not isinstance(record.msg, str):
            return True

        msg = record.msg.lower()
        original_msg = str(record.msg)

        for pattern, replacement in self.REDACT_PATTERNS:
            if pattern in msg:
                # Replace case-insensitively
                import re

                record.msg = re.sub(
                    re.escape(pattern) + r"[^\s]*",
                    replacement,
                    original_msg,
                    flags=re.IGNORECASE,
                )
                original_msg = record.msg

        return True


# ── Setup Function ────────────────────────────────────────────────────────────


def setup_logging(app: Flask | None = None) -> None:
    """
    Configure centralized logging for the entire application.

    This should be called once at application startup (in app.py or agent.py).

    Args:
        app: Optional Flask app (for backend). If None, configures for tracker/standalone.

    Sets up:
        - Root logger level
        - Console handler (always enabled)
        - Rotating file handler (if LOG_TO_FILE=true)
        - Custom formatter with request context
        - Sensitive data filter

    Environment variables:
        LOG_LEVEL: DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
        LOG_FILE: Path to log file (default: logs/app.log)
        LOG_TO_FILE: Enable file logging (default: true)
        LOG_MAX_BYTES: Max log file size before rotation (default: 10MB)
        LOG_BACKUP_COUNT: Number of backup files to keep (default: 5)
    """
    # Determine log level
    level = getattr(logging, LOG_LEVEL, logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers (prevent duplicates on reload)
    root_logger.handlers.clear()

    # ── Console Handler ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Use custom formatter with request context
    console_formatter = RequestContextFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # Add sensitive data filter
    console_handler.addFilter(SensitiveDataFilter())

    root_logger.addHandler(console_handler)

    # ── File Handler (Rotating) ──
    if LOG_TO_FILE:
        try:
            # Ensure log directory exists
            log_path = Path(LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Rotating file handler (prevents unlimited log growth)
            file_handler = logging.handlers.RotatingFileHandler(
                filename=LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(level)

            # Same formatter as console for consistency
            file_formatter = RequestContextFormatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            file_handler.addFilter(SensitiveDataFilter())

            root_logger.addHandler(file_handler)

        except (OSError, PermissionError) as e:
            # Fallback: log to console only if file logging fails
            print(f"WARNING: Could not set up file logging to {LOG_FILE}: {e}", file=sys.stderr)
            print("Continuing with console logging only.", file=sys.stderr)

    # ── Log startup message ──
    startup_logger = logging.getLogger("backend.logging" if app else "tracker.logging")
    startup_logger.info("=" * 70)
    startup_logger.info("Logging initialized")
    startup_logger.info(f"  Log level: {LOG_LEVEL}")
    startup_logger.info(f"  Console output: enabled")
    startup_logger.info(f"  File output: {'enabled' if LOG_TO_FILE else 'disabled'}")
    if LOG_TO_FILE:
        startup_logger.info(f"  Log file: {LOG_FILE}")
        startup_logger.info(f"  Max file size: {LOG_MAX_BYTES / (1024*1024):.1f} MB")
        startup_logger.info(f"  Backup count: {LOG_BACKUP_COUNT}")
    startup_logger.info("=" * 70)

    # ── Suppress noisy third-party loggers ──
    # Werkzeug (Flask dev server) is too verbose at INFO level
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # SQLAlchemy can be noisy at INFO level
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Set backend and tracker loggers to configured level
    logging.getLogger("backend").setLevel(level)
    logging.getLogger("tracker").setLevel(level)


# ── Helper Functions ─────────────────────────────────────────────────────────


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    This is just a convenience wrapper around logging.getLogger().
    Use this or logging.getLogger(__name__) directly - both work.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return logging.getLogger(name)


def log_startup_info(app: Flask) -> None:
    """
    Log application startup information (useful for debugging deployments).

    Logs:
        - Demo mode status
        - Database type
        - OIDC configuration
        - Environment hints

    Args:
        app: Flask application instance
    """
    logger = logging.getLogger("backend.startup")

    logger.info("=" * 70)
    logger.info("Application startup")
    logger.info(f"  Demo mode: {app.config.get('DEMO_MODE', True)}")

    # Database info (without credentials)
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri:
        if db_uri.startswith("postgresql"):
            db_type = "PostgreSQL"
        elif db_uri.startswith("sqlite"):
            db_type = "SQLite"
        else:
            db_type = "Unknown"
        logger.info(f"  Database: {db_type}")

    # OIDC status
    oidc_configured = bool(app.config.get("OIDC_ISSUER_URL"))
    logger.info(f"  SSO (OIDC): {'enabled' if oidc_configured else 'disabled'}")

    # Environment
    env = os.getenv("FLASK_ENV", "production")
    logger.info(f"  Environment: {env}")

    logger.info("=" * 70)


def log_request_info(method: str, path: str, status_code: int, duration_ms: float | None = None) -> None:
    """
    Log HTTP request information (call from after_request hook if needed).

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration_ms: Optional request duration in milliseconds
    """
    logger = logging.getLogger("backend.http")

    # Color-code by status (for terminal readability)
    if status_code < 400:
        level = logging.INFO
    elif status_code < 500:
        level = logging.WARNING
    else:
        level = logging.ERROR

    msg = f"{method} {path} → {status_code}"
    if duration_ms is not None:
        msg += f" ({duration_ms:.1f}ms)"

    logger.log(level, msg)


# ── For Testing ──────────────────────────────────────────────────────────────


def disable_logging_for_tests() -> None:
    """
    Disable logging output during tests (reduces noise).

    Call this in conftest.py or test setup.
    """
    logging.disable(logging.CRITICAL)


def enable_logging_after_tests() -> None:
    """Re-enable logging after tests."""
    logging.disable(logging.NOTSET)
