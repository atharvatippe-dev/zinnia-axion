"""
Shared pytest fixtures for the Zinnia Axion test suite.

Creates an in-memory SQLite test database with a 3-level team hierarchy,
3 managers, and users — providing a ready-made multi-team scenario.

Hierarchy:
  Team N (Nikhil)  — root
    └── Team W (Wasim)
          └── Team A (Atharva)

Visibility:
  Nikhil → N, W, A  (all 3)
  Wasim  → W, A     (2)
  Atharva→ A         (1)
"""

from __future__ import annotations

import os
import hashlib
import secrets

import pytest

os.environ["DEMO_MODE"] = "false"
os.environ["DATABASE_URI"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["OIDC_ISSUER_URL"] = ""

from backend.app import create_app
from backend.config import Config
from backend.models import db as _db, User, Team, Membership, Manager, TrackerDeviceToken


@pytest.fixture(scope="session")
def app():
    """Create the Flask app once per test session."""
    config = Config()
    config.DEMO_MODE = False
    config.SQLALCHEMY_DATABASE_URI = "sqlite://"
    config.SECRET_KEY = "test-secret-key-not-for-production"
    config.OIDC_ISSUER_URL = ""
    config.ADMIN_PASSWORD = "test-admin-password"
    config.WTF_CSRF_ENABLED = False

    import backend.app as _app_module
    _original_check = _app_module._check_production_config

    def _test_check(cfg):
        original_uri = cfg.SQLALCHEMY_DATABASE_URI
        cfg.SQLALCHEMY_DATABASE_URI = "postgresql://fake/for_check"
        try:
            _original_check(cfg)
        finally:
            cfg.SQLALCHEMY_DATABASE_URI = original_uri

    _app_module._check_production_config = _test_check

    application = create_app(config)
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["TESTING"] = True

    _app_module._check_production_config = _original_check
    return application


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """Provide a clean database for each test function."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(scope="function")
def seed_data(db):
    """
    Seed a 3-level team hierarchy with managers and users:

      Team N (Nikhil — manager, root)
        user_n1
        └── Team W (Wasim — manager)
              user_w1, user_w2
              └── Team A (Atharva — manager)
                    user_a1, user_a2

    Returns a dict of all created records.
    """
    team_n = Team(name="Engineering")
    db.session.add(team_n)
    db.session.flush()

    team_w = Team(name="Lifecad", parent_team_id=team_n.id)
    db.session.add(team_w)
    db.session.flush()

    team_a = Team(name="Axion", parent_team_id=team_w.id)
    db.session.add(team_a)
    db.session.flush()

    nikhil = User(lan_id="nikhil", email="nikhil@test.com", display_name="Nikhil Saxena", role="manager")
    wasim = User(lan_id="wasim", email="wasim@test.com", display_name="Wasim Shaikh", role="manager")
    atharva = User(lan_id="atharva_mgr", email="atharva@test.com", display_name="Atharva Tippe", role="manager")
    user_n1 = User(lan_id="user_n1", email="n1@test.com", display_name="User N1", role="user")
    user_w1 = User(lan_id="user_w1", email="w1@test.com", display_name="User W1", role="user")
    user_w2 = User(lan_id="user_w2", email="w2@test.com", display_name="User W2", role="user")
    user_a1 = User(lan_id="user_a1", email="a1@test.com", display_name="User A1", role="user")
    user_a2 = User(lan_id="user_a2", email="a2@test.com", display_name="User A2", role="user")
    db.session.add_all([nikhil, wasim, atharva, user_n1, user_w1, user_w2, user_a1, user_a2])
    db.session.flush()

    db.session.add_all([
        Manager(user_id=nikhil.id, team_id=team_n.id),
        Manager(user_id=wasim.id, team_id=team_w.id),
        Manager(user_id=atharva.id, team_id=team_a.id),
    ])

    membership_map = [
        (nikhil, team_n), (user_n1, team_n),
        (wasim, team_w), (user_w1, team_w), (user_w2, team_w),
        (atharva, team_a), (user_a1, team_a), (user_a2, team_a),
    ]
    for user, team in membership_map:
        db.session.add(Membership(user_id=user.id, team_id=team.id, active=True))

    db.session.commit()

    return {
        "team_n": team_n,
        "team_w": team_w,
        "team_a": team_a,
        "nikhil": nikhil,
        "wasim": wasim,
        "atharva": atharva,
        "user_n1": user_n1,
        "user_w1": user_w1,
        "user_w2": user_w2,
        "user_a1": user_a1,
        "user_a2": user_a2,
    }


def _make_session(client, user, team):
    """Set the Flask session to simulate a logged-in manager."""
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["team_id"] = team.id
        sess["role"] = user.role
        sess["email"] = user.email
        sess["display_name"] = user.display_name
    return client


@pytest.fixture(scope="function")
def auth_nikhil(client, seed_data):
    """Client logged in as Nikhil (Team N — root, sees all)."""
    return _make_session(client, seed_data["nikhil"], seed_data["team_n"])


@pytest.fixture(scope="function")
def auth_wasim(client, seed_data):
    """Client logged in as Wasim (Team W — mid, sees W + A)."""
    return _make_session(client, seed_data["wasim"], seed_data["team_w"])


@pytest.fixture(scope="function")
def auth_atharva(client, seed_data):
    """Client logged in as Atharva (Team A — leaf, sees only A)."""
    return _make_session(client, seed_data["atharva"], seed_data["team_a"])


# Legacy aliases for backward compat with existing tests
@pytest.fixture(scope="function")
def auth_session_a(auth_atharva):
    return auth_atharva


@pytest.fixture(scope="function")
def auth_session_b(auth_wasim):
    return auth_wasim


@pytest.fixture(scope="function")
def device_token_alpha(db, seed_data):
    """Create a valid device token for Team A and return (raw_token, token_obj)."""
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = TrackerDeviceToken(
        token_hash=token_hash,
        team_id=seed_data["team_a"].id,
    )
    db.session.add(token)
    db.session.commit()
    return raw, token
