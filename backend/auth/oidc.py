"""
OIDC SSO client configuration using Authlib.

Handles admin login via authorization code flow.
On successful auth, resolves the manager identity and team_id,
stores them in the Flask session.
"""

from __future__ import annotations

import logging
import secrets

from authlib.integrations.flask_client import OAuth
from flask import Flask

logger = logging.getLogger("backend.auth.oidc")

oauth = OAuth()


def init_oidc(app: Flask) -> None:
    """Register the OIDC provider with Authlib's OAuth client."""
    issuer_url = app.config.get("OIDC_ISSUER_URL", "")

    if not issuer_url:
        logger.info("OIDC_ISSUER_URL not configured — SSO login disabled.")
        return

    oauth.init_app(app)

    metadata_url = issuer_url.rstrip("/")
    if not metadata_url.endswith("/.well-known/openid-configuration"):
        metadata_url += "/.well-known/openid-configuration"

    oauth.register(
        name="oidc",
        server_metadata_url=metadata_url,
        client_id=app.config["OIDC_CLIENT_ID"],
        client_secret=app.config["OIDC_CLIENT_SECRET"],
        client_kwargs={
            "scope": app.config.get("OIDC_SCOPES", "openid profile email"),
        },
    )
    logger.info("OIDC provider registered: %s", issuer_url)


def is_oidc_configured() -> bool:
    """Check whether OIDC was registered (i.e. issuer URL was provided)."""
    return "oidc" in oauth._clients  # noqa: SLF001


def generate_nonce() -> str:
    return secrets.token_urlsafe(32)
