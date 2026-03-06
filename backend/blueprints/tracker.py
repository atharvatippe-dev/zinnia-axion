"""
Tracker blueprint — ingest telemetry events from desktop agents.

POST /track          — legacy endpoint (backward compat)
POST /tracker/ingest — new canonical endpoint

When DEMO_MODE=false, both require a valid device token + LAN-ID.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app

from backend.models import db, TelemetryEvent, TrackerDeviceToken, User, Membership
from backend.audit import log_action
from backend.utils import validate_event

logger = logging.getLogger("backend.blueprints.tracker")

tracker_bp = Blueprint("tracker", __name__)


def _verify_tracker_auth():
    """
    Validate the device token and LAN-ID from request headers.
    Returns (user_lan_id, error_response) — error_response is None on success.
    """
    if current_app.config.get("DEMO_MODE", True):
        return request.headers.get("X-LAN-ID", request.json.get("events", [{}])[0].get("user_id", "default") if request.json else "default"), None

    auth_header = request.headers.get("Authorization", "")
    lan_id = request.headers.get("X-LAN-ID", "")

    if not auth_header.startswith("Bearer ") or not lan_id:
        log_action("anonymous", "tracker_auth_failed", detail="Missing Authorization or X-LAN-ID header")
        return None, (jsonify({"error": "Missing Authorization header or X-LAN-ID"}), 401)

    raw_token = auth_header[7:]
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    device_token = TrackerDeviceToken.query.filter_by(token_hash=token_hash).first()
    if not device_token or not device_token.is_valid():
        log_action("anonymous", "tracker_auth_failed", detail=f"Invalid or expired device token for lan_id={lan_id}")
        return None, (jsonify({"error": "Invalid or expired device token"}), 401)

    user = User.query.filter_by(lan_id=lan_id).first()
    if not user:
        log_action("anonymous", "tracker_auth_failed", detail=f"Unknown lan_id={lan_id}")
        return None, (jsonify({"error": "Unknown LAN ID"}), 403)

    active_membership = Membership.query.filter_by(user_id=user.id, active=True).first()
    if not active_membership:
        log_action(lan_id, "tracker_auth_failed", detail="User has no active team membership")
        return None, (jsonify({"error": "User has no active team membership"}), 403)

    if device_token.team_id != active_membership.team_id:
        log_action(lan_id, "tracker_auth_failed", detail=f"Token team {device_token.team_id} != user team {active_membership.team_id}")
        return None, (jsonify({"error": "Device token team mismatch"}), 403)

    return lan_id, None


def _ingest_events():
    """Shared ingest logic for both /track and /tracker/ingest."""
    cfg = current_app.tracker_config  # type: ignore[attr-defined]

    lan_id, err = _verify_tracker_auth()
    if err:
        return err

    data = request.get_json(silent=True)
    if not data or "events" not in data:
        return jsonify({"error": "Missing 'events' array in payload"}), 400

    events_raw = data["events"]
    if not isinstance(events_raw, list):
        return jsonify({"error": "'events' must be a list"}), 400

    errors: list[str] = []
    for i, raw in enumerate(events_raw):
        err_msg = validate_event(raw)
        if err_msg:
            errors.append(f"event[{i}]: {err_msg}")
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    drop_titles = cfg.DROP_TITLES
    created = 0

    for raw in events_raw:
        try:
            ts = raw.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                ts = datetime.now(timezone.utc)

            title = "" if drop_titles else raw.get("window_title", "")
            resolved_user_id = raw.get("user_id", lan_id or "default")

            event = TelemetryEvent(
                timestamp=ts,
                user_id=resolved_user_id,
                app_name=raw.get("app_name", "unknown"),
                window_title=title,
                keystroke_count=int(raw.get("keystroke_count", 0)),
                mouse_clicks=int(raw.get("mouse_clicks", 0)),
                mouse_distance=float(raw.get("mouse_distance", 0.0)),
                idle_seconds=float(raw.get("idle_seconds", 0.0)),
                distraction_visible=bool(raw.get("distraction_visible", False)),
            )
            db.session.add(event)
            created += 1
        except (ValueError, TypeError) as exc:
            logger.warning("Skipping malformed event: %s — %s", raw, exc)

    db.session.commit()
    logger.info("Ingested %d / %d events.", created, len(events_raw))
    return jsonify({"ingested": created}), 201


@tracker_bp.route("/track", methods=["POST"])
def track():
    """Legacy ingest endpoint — backward compatible."""
    return _ingest_events()


@tracker_bp.route("/tracker/ingest", methods=["POST"])
def tracker_ingest():
    """Canonical ingest endpoint with device auth."""
    return _ingest_events()
