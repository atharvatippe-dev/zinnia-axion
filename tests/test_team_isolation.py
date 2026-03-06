"""
Team isolation tests — verify that managers can only access
their team subtree data, and cross-scope access is blocked.

Uses the hierarchical seed data from conftest.py:
  Team N (Nikhil) > Team W (Wasim) > Team A (Atharva)
"""

from __future__ import annotations

from datetime import datetime, timezone
from backend.models import db as _db, TelemetryEvent, TeamChangeRequest


def _add_telemetry(db, user_id: str, count: int = 5):
    """Insert sample telemetry events for a user."""
    for i in range(count):
        ev = TelemetryEvent(
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            app_name="TestApp",
            keystroke_count=10 + i,
            mouse_clicks=5,
        )
        db.session.add(ev)
    db.session.commit()


def test_atharva_sees_only_a_users(auth_atharva, seed_data, db):
    """Atharva (Team A leaf) should only see Team A users."""
    resp = auth_atharva.get("/admin/users")
    assert resp.status_code == 200
    lan_ids = {u["lan_id"] for u in resp.get_json()}
    assert "user_a1" in lan_ids
    assert "user_a2" in lan_ids
    assert "user_w1" not in lan_ids
    assert "user_n1" not in lan_ids


def test_wasim_sees_w_and_a_users(auth_wasim, seed_data, db):
    """Wasim (Team W parent of A) should see Team W and A users."""
    resp = auth_wasim.get("/admin/users")
    assert resp.status_code == 200
    lan_ids = {u["lan_id"] for u in resp.get_json()}
    assert "user_w1" in lan_ids
    assert "user_a1" in lan_ids
    assert "user_n1" not in lan_ids


def test_wasim_leaderboard_includes_a_excludes_n(auth_wasim, seed_data, db):
    """Leaderboard for Wasim includes Team A (child) but not Team N (parent)."""
    _add_telemetry(db, "user_a1")
    _add_telemetry(db, "user_w1")
    _add_telemetry(db, "user_n1")

    resp = auth_wasim.get("/admin/leaderboard")
    assert resp.status_code == 200
    user_ids = {r["user_id"] for r in resp.get_json()}
    assert "user_w1" in user_ids
    assert "user_a1" in user_ids
    assert "user_n1" not in user_ids


def test_idor_app_breakdown_blocked(auth_atharva, seed_data, db):
    """Atharva cannot view app breakdown for a Team W user (IDOR)."""
    _add_telemetry(db, "user_w1")
    resp = auth_atharva.get("/admin/user/user_w1/app-breakdown")
    assert resp.status_code == 403


def test_idor_non_productive_apps_blocked(auth_atharva, seed_data, db):
    _add_telemetry(db, "user_w1")
    resp = auth_atharva.get("/admin/user/user_w1/non-productive-apps")
    assert resp.status_code == 403


def test_idor_delete_user_blocked(auth_atharva, seed_data, db):
    _add_telemetry(db, "user_w1")
    resp = auth_atharva.delete("/admin/user/user_w1")
    assert resp.status_code == 403


def test_manager_can_view_own_subtree_user(auth_wasim, seed_data, db):
    """Wasim CAN view app breakdown for Team A user (child team)."""
    _add_telemetry(db, "user_a1")
    resp = auth_wasim.get("/admin/user/user_a1/app-breakdown")
    assert resp.status_code == 200


def test_manager_can_delete_own_subtree_user(auth_wasim, seed_data, db):
    _add_telemetry(db, "user_a1", count=3)
    resp = auth_wasim.delete("/admin/user/user_a1")
    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == 3


def test_assign_user_to_own_team(auth_atharva, seed_data, db):
    """Atharva can assign an unassigned user to Team A."""
    from backend.models import User, Membership

    new_user = User(lan_id="new_hire", display_name="New Hire", role="user")
    db.session.add(new_user)
    db.session.commit()

    resp = auth_atharva.post(f"/admin/users/{new_user.id}/assign_to_my_team")
    assert resp.status_code == 200

    m = Membership.query.filter_by(user_id=new_user.id, active=True).first()
    assert m is not None
    assert m.team_id == seed_data["team_a"].id


def test_assign_cross_team_creates_request(auth_atharva, seed_data, db):
    """Assigning a Team W user to Team A creates a transfer request."""
    resp = auth_atharva.post(
        f"/admin/users/{seed_data['user_w1'].id}/assign_to_my_team"
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert "request_id" in data

    req = _db.session.get(TeamChangeRequest, data["request_id"])
    assert req.status == "pending"
    assert req.from_team_id == seed_data["team_w"].id
    assert req.to_team_id == seed_data["team_a"].id


def test_remove_user_from_own_team(auth_atharva, seed_data, db):
    resp = auth_atharva.post(
        f"/admin/users/{seed_data['user_a1'].id}/remove_from_my_team"
    )
    assert resp.status_code == 200

    from backend.models import Membership
    m = Membership.query.filter_by(user_id=seed_data["user_a1"].id, active=True).first()
    assert m is None
