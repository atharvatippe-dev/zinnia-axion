"""
Hierarchical team visibility + IDOR prevention tests.

Hierarchy:
  Team N (Nikhil)  — root  → sees N, W, A
    └── Team W (Wasim)      → sees W, A
          └── Team A (Atharva) → sees A only

Every test verifies that scoping is enforced server-side and that
out-of-scope access returns 403 + triggers an audit log entry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from backend.models import db as _db, TelemetryEvent, AuditLog


def _add_telemetry(db, user_id: str, count: int = 5):
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


# ── Subtree computation ─────────────────────────────────────────────


class TestSubtreeComputation:
    """Verify get_allowed_team_ids returns the correct subtree."""

    def test_nikhil_sees_all_three(self, app, seed_data, db):
        with app.app_context():
            from backend.auth.team_hierarchy import _subtree_python
            ids = _subtree_python(seed_data["team_n"].id)
            assert set(ids) == {
                seed_data["team_n"].id,
                seed_data["team_w"].id,
                seed_data["team_a"].id,
            }

    def test_wasim_sees_w_and_a(self, app, seed_data, db):
        with app.app_context():
            from backend.auth.team_hierarchy import _subtree_python
            ids = _subtree_python(seed_data["team_w"].id)
            assert set(ids) == {
                seed_data["team_w"].id,
                seed_data["team_a"].id,
            }

    def test_atharva_sees_only_a(self, app, seed_data, db):
        with app.app_context():
            from backend.auth.team_hierarchy import _subtree_python
            ids = _subtree_python(seed_data["team_a"].id)
            assert ids == [seed_data["team_a"].id]


# ── User list scoping ──────────────────────────────────────────────


class TestUserListScoping:
    """Verify /admin/users returns only users in the manager's subtree."""

    def test_nikhil_sees_all_users(self, auth_nikhil, seed_data, db):
        resp = auth_nikhil.get("/admin/users")
        assert resp.status_code == 200
        lan_ids = {u["lan_id"] for u in resp.get_json()}
        assert "user_n1" in lan_ids
        assert "user_w1" in lan_ids
        assert "user_a1" in lan_ids

    def test_wasim_sees_w_and_a_users(self, auth_wasim, seed_data, db):
        resp = auth_wasim.get("/admin/users")
        assert resp.status_code == 200
        lan_ids = {u["lan_id"] for u in resp.get_json()}
        assert "user_w1" in lan_ids
        assert "user_w2" in lan_ids
        assert "user_a1" in lan_ids
        assert "user_a2" in lan_ids
        assert "user_n1" not in lan_ids
        assert "nikhil" not in lan_ids

    def test_atharva_sees_only_a_users(self, auth_atharva, seed_data, db):
        resp = auth_atharva.get("/admin/users")
        assert resp.status_code == 200
        lan_ids = {u["lan_id"] for u in resp.get_json()}
        assert "user_a1" in lan_ids
        assert "user_a2" in lan_ids
        assert "atharva_mgr" in lan_ids
        assert "user_w1" not in lan_ids
        assert "user_n1" not in lan_ids


# ── Leaderboard scoping ────────────────────────────────────────────


class TestLeaderboardScoping:
    """Verify leaderboard only includes users from the manager's subtree."""

    def test_wasim_leaderboard_excludes_n_users(self, auth_wasim, seed_data, db):
        _add_telemetry(db, "user_n1")
        _add_telemetry(db, "user_w1")
        _add_telemetry(db, "user_a1")

        resp = auth_wasim.get("/admin/leaderboard")
        assert resp.status_code == 200
        user_ids = {r["user_id"] for r in resp.get_json()}
        assert "user_w1" in user_ids
        assert "user_a1" in user_ids
        assert "user_n1" not in user_ids

    def test_atharva_leaderboard_excludes_w_and_n(self, auth_atharva, seed_data, db):
        _add_telemetry(db, "user_n1")
        _add_telemetry(db, "user_w1")
        _add_telemetry(db, "user_a1")

        resp = auth_atharva.get("/admin/leaderboard")
        assert resp.status_code == 200
        user_ids = {r["user_id"] for r in resp.get_json()}
        assert "user_a1" in user_ids
        assert "user_w1" not in user_ids
        assert "user_n1" not in user_ids


# ── IDOR: app-breakdown / non-productive-apps ──────────────────────


class TestIDORBlocked:
    """Verify cross-scope user data access returns 403."""

    def test_atharva_cannot_view_w_user_breakdown(self, auth_atharva, seed_data, db):
        _add_telemetry(db, "user_w1")
        resp = auth_atharva.get("/admin/user/user_w1/app-breakdown")
        assert resp.status_code == 403

    def test_atharva_cannot_view_n_user_breakdown(self, auth_atharva, seed_data, db):
        _add_telemetry(db, "user_n1")
        resp = auth_atharva.get("/admin/user/user_n1/app-breakdown")
        assert resp.status_code == 403

    def test_atharva_cannot_view_w_user_np_apps(self, auth_atharva, seed_data, db):
        _add_telemetry(db, "user_w1")
        resp = auth_atharva.get("/admin/user/user_w1/non-productive-apps")
        assert resp.status_code == 403

    def test_wasim_cannot_view_n_user_breakdown(self, auth_wasim, seed_data, db):
        _add_telemetry(db, "user_n1")
        resp = auth_wasim.get("/admin/user/user_n1/app-breakdown")
        assert resp.status_code == 403

    def test_wasim_CAN_view_a_user_breakdown(self, auth_wasim, seed_data, db):
        """Wasim manages W (parent of A) so he can see A's users."""
        _add_telemetry(db, "user_a1")
        resp = auth_wasim.get("/admin/user/user_a1/app-breakdown")
        assert resp.status_code == 200

    def test_nikhil_can_view_any_user(self, auth_nikhil, seed_data, db):
        _add_telemetry(db, "user_a1")
        _add_telemetry(db, "user_w1")
        _add_telemetry(db, "user_n1")
        for uid in ["user_a1", "user_w1", "user_n1"]:
            resp = auth_nikhil.get(f"/admin/user/{uid}/app-breakdown")
            assert resp.status_code == 200, f"Nikhil blocked from {uid}"


# ── IDOR: delete user telemetry ────────────────────────────────────


class TestIDORDelete:
    """Verify cross-scope deletion is blocked."""

    def test_atharva_cannot_delete_w_user(self, auth_atharva, seed_data, db):
        _add_telemetry(db, "user_w1")
        resp = auth_atharva.delete("/admin/user/user_w1")
        assert resp.status_code == 403

    def test_wasim_cannot_delete_n_user(self, auth_wasim, seed_data, db):
        _add_telemetry(db, "user_n1")
        resp = auth_wasim.delete("/admin/user/user_n1")
        assert resp.status_code == 403

    def test_wasim_can_delete_a_user(self, auth_wasim, seed_data, db):
        _add_telemetry(db, "user_a1", count=3)
        resp = auth_wasim.delete("/admin/user/user_a1")
        assert resp.status_code == 200
        assert resp.get_json()["deleted"] == 3


# ── IDOR: audit log creation ───────────────────────────────────────


class TestIDORAuditLog:
    """Verify that blocked IDOR attempts create audit log entries."""

    def test_blocked_access_creates_audit_entry(self, auth_atharva, seed_data, db):
        _add_telemetry(db, "user_w1")

        before_count = AuditLog.query.filter(
            AuditLog.action.in_(["idor_user_blocked", "idor_team_blocked"])
        ).count()

        auth_atharva.get("/admin/user/user_w1/app-breakdown")

        after_count = AuditLog.query.filter(
            AuditLog.action.in_(["idor_user_blocked", "idor_team_blocked"])
        ).count()

        assert after_count > before_count


# ── Teams endpoint ──────────────────────────────────────────────────


class TestTeamsEndpoint:
    """Verify /admin/teams returns only teams in scope."""

    def test_nikhil_sees_all_teams(self, auth_nikhil, seed_data, db):
        resp = auth_nikhil.get("/admin/teams")
        assert resp.status_code == 200
        names = {t["name"] for t in resp.get_json()}
        assert names == {"Engineering", "Lifecad", "Axion"}

    def test_wasim_sees_w_and_a(self, auth_wasim, seed_data, db):
        resp = auth_wasim.get("/admin/teams")
        assert resp.status_code == 200
        names = {t["name"] for t in resp.get_json()}
        assert names == {"Lifecad", "Axion"}
        assert "Engineering" not in names

    def test_atharva_sees_only_a(self, auth_atharva, seed_data, db):
        resp = auth_atharva.get("/admin/teams")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Axion"


# ── Auth: unauthenticated + regular user ────────────────────────────


class TestAuthEnforcement:
    """Verify auth is enforced for all admin endpoints."""

    def test_unauthenticated_redirects_to_login(self, client, seed_data):
        resp = client.get("/admin/dashboard")
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers.get("Location", "")

    def test_regular_user_gets_403(self, client, seed_data):
        with client.session_transaction() as sess:
            sess["user_id"] = seed_data["user_a1"].id
            sess["team_id"] = seed_data["team_a"].id
            sess["role"] = "user"
        resp = client.get("/admin/leaderboard")
        assert resp.status_code == 403

    def test_logout_clears_session(self, auth_wasim, seed_data):
        resp = auth_wasim.post("/admin/logout")
        assert resp.status_code == 302
        resp2 = auth_wasim.get("/admin/dashboard")
        assert resp2.status_code == 302
        assert "/admin/login" in resp2.headers.get("Location", "")
