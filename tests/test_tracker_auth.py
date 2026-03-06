"""
Tracker authentication tests — verify device token validation
on /track and /tracker/ingest endpoints.
"""

from __future__ import annotations

import json


SAMPLE_EVENTS = {
    "events": [
        {
            "timestamp": "2026-03-04T10:00:00+00:00",
            "user_id": "user_a1",
            "app_name": "TestApp",
            "keystroke_count": 10,
            "mouse_clicks": 5,
            "mouse_distance": 100.0,
            "idle_seconds": 0.0,
        }
    ]
}


def test_track_rejects_missing_token(client, seed_data):
    """POST /track without Authorization header should be rejected."""
    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_track_rejects_invalid_token(client, seed_data):
    """POST /track with a garbage token should be rejected."""
    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": "Bearer totally-invalid-token",
            "X-LAN-ID": "user_a1",
        },
    )
    assert resp.status_code == 401


def test_track_rejects_missing_lan_id(client, seed_data, device_token_alpha):
    """POST /track with valid token but no X-LAN-ID should be rejected."""
    raw_token, _ = device_token_alpha

    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw_token}",
        },
    )
    assert resp.status_code == 401


def test_track_rejects_unknown_lan_id(client, seed_data, device_token_alpha):
    """POST /track with valid token but unknown LAN ID should be rejected."""
    raw_token, _ = device_token_alpha

    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw_token}",
            "X-LAN-ID": "nonexistent_user",
        },
    )
    assert resp.status_code == 403


def test_track_accepts_valid_token_and_lan_id(client, seed_data, device_token_alpha):
    """POST /track with valid token + known LAN ID should succeed."""
    raw_token, _ = device_token_alpha

    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw_token}",
            "X-LAN-ID": "user_a1",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["ingested"] == 1


def test_tracker_ingest_endpoint_works(client, seed_data, device_token_alpha):
    """POST /tracker/ingest should also work with valid auth."""
    raw_token, _ = device_token_alpha

    resp = client.post(
        "/tracker/ingest",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw_token}",
            "X-LAN-ID": "user_a1",
        },
    )
    assert resp.status_code == 201


def test_track_rejects_revoked_token(client, seed_data, device_token_alpha, db):
    """POST /track with a revoked token should be rejected."""
    raw_token, token_obj = device_token_alpha
    token_obj.revoked = True
    db.session.commit()

    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw_token}",
            "X-LAN-ID": "user_a1",
        },
    )
    assert resp.status_code == 401


def test_track_rejects_team_mismatch(client, seed_data, db):
    """Token for Team N should not work for a Team A user."""
    import hashlib
    import secrets
    from backend.models import TrackerDeviceToken

    raw = secrets.token_urlsafe(48)
    token = TrackerDeviceToken(
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        team_id=seed_data["team_n"].id,
    )
    db.session.add(token)
    db.session.commit()

    resp = client.post(
        "/track",
        data=json.dumps(SAMPLE_EVENTS),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw}",
            "X-LAN-ID": "user_a1",
        },
    )
    assert resp.status_code == 403


def test_track_validation_still_works(client, seed_data, device_token_alpha):
    """Malformed events should still be rejected with 400."""
    raw_token, _ = device_token_alpha

    bad_payload = {"events": [{"keystroke_count": "not_a_number"}]}
    resp = client.post(
        "/track",
        data=json.dumps(bad_payload),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {raw_token}",
            "X-LAN-ID": "user_a1",
        },
    )
    assert resp.status_code == 400
