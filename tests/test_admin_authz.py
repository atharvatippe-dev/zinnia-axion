"""
Authorization tests — verify that admin endpoints enforce authentication
and that unauthenticated access is blocked.
"""

from __future__ import annotations


def test_unauthenticated_dashboard_redirects_to_login(client, seed_data):
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("Location", "")


def test_unauthenticated_leaderboard_redirects(client, seed_data):
    resp = client.get("/admin/leaderboard")
    assert resp.status_code == 302


def test_unauthenticated_users_redirects(client, seed_data):
    resp = client.get("/admin/users")
    assert resp.status_code == 302


def test_authenticated_manager_can_access_dashboard(auth_wasim, seed_data):
    resp = auth_wasim.get("/admin/dashboard")
    assert resp.status_code == 200


def test_authenticated_manager_can_access_leaderboard(auth_wasim, seed_data):
    resp = auth_wasim.get("/admin/leaderboard")
    assert resp.status_code == 200


def test_authenticated_manager_can_access_users(auth_wasim, seed_data):
    resp = auth_wasim.get("/admin/users")
    assert resp.status_code == 200
    data = resp.get_json()
    lan_ids = {u["lan_id"] for u in data}
    assert "user_w1" in lan_ids
    assert "user_a1" in lan_ids


def test_regular_user_cannot_access_admin(client, seed_data):
    with client.session_transaction() as sess:
        sess["user_id"] = seed_data["user_a1"].id
        sess["team_id"] = seed_data["team_a"].id
        sess["role"] = "user"
    resp = client.get("/admin/leaderboard")
    assert resp.status_code == 403


def test_logout_clears_session(auth_wasim, seed_data):
    resp = auth_wasim.post("/admin/logout")
    assert resp.status_code == 302
    resp2 = auth_wasim.get("/admin/dashboard")
    assert resp2.status_code == 302
    assert "/admin/login" in resp2.headers.get("Location", "")
