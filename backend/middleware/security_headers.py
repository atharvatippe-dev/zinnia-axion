"""
Security headers middleware.

Applies hardened HTTP headers to all responses:
  - HSTS (Strict-Transport-Security)
  - CSP (Content-Security-Policy)
  - X-Content-Type-Options
  - X-Frame-Options
  - Referrer-Policy
  - Permissions-Policy
"""

from __future__ import annotations

from flask import Flask


def init_security_headers(app: Flask) -> None:
    """Register after_request hook that sets security headers."""

    @app.after_request
    def _set_security_headers(response):
        if app.config.get("DEMO_MODE", True):
            return response

        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request_is_admin(response):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "frame-ancestors 'none'"
            )

        return response


def request_is_admin(response) -> bool:
    """Check if the current response is for an admin page (HTML content)."""
    content_type = response.content_type or ""
    return "text/html" in content_type
