"""
OIDC flow tests — verify login redirect behavior and session management.

These tests mock the OIDC provider since we can't hit a real IdP in tests.
"""

from __future__ import annotations


def test_login_redirects_to_dashboard_in_demo_mode(client, db):
    """In demo mode, /admin/login should redirect straight to dashboard."""
    client.application.config["DEMO_MODE"] = True
    try:
        resp = client.get("/admin/login")
        assert resp.status_code == 302
        assert "/admin/dashboard" in resp.headers.get("Location", "")
    finally:
        client.application.config["DEMO_MODE"] = False


def test_login_renders_page_when_no_oidc(client, db):
    """When OIDC is not configured and not demo mode, show login page."""
    resp = client.get("/admin/login")
    assert resp.status_code == 200
    assert b"Sign in with SSO" in resp.data


def test_callback_redirects_to_dashboard_in_demo_mode(client, db):
    """In demo mode, /admin/callback should redirect to dashboard."""
    client.application.config["DEMO_MODE"] = True
    try:
        resp = client.get("/admin/callback")
        assert resp.status_code == 302
        assert "/admin/dashboard" in resp.headers.get("Location", "")
    finally:
        client.application.config["DEMO_MODE"] = False


def test_callback_errors_when_no_oidc(client, db):
    """When OIDC is not configured and not demo, callback returns error."""
    resp = client.get("/admin/callback")
    assert resp.status_code == 500


def test_health_always_accessible(client, db):
    """Health endpoint should always work, regardless of auth state."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_public_endpoints_accessible_without_auth(client, db):
    """Public endpoints like /summary/today should be accessible."""
    resp = client.get("/summary/today")
    assert resp.status_code == 200

    resp = client.get("/apps")
    assert resp.status_code == 200

    resp = client.get("/daily?days=3")
    assert resp.status_code == 200

    resp = client.get("/db-stats")
    assert resp.status_code == 200
