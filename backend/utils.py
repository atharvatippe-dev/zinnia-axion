"""
Shared utility functions extracted from the original monolithic app.py.
Used by blueprints and services.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo

from flask import current_app, request

from backend.config import Config
from backend.models import TelemetryEvent


def get_config() -> Config:
    return current_app.tracker_config  # type: ignore[attr-defined]


def get_local_tz(config: Config) -> ZoneInfo:
    try:
        return ZoneInfo(config.TIMEZONE)
    except (KeyError, Exception):
        return ZoneInfo("UTC")


def today_range(config: Config) -> tuple[datetime, datetime]:
    """(start_of_today, start_of_tomorrow) as UTC datetimes using configured tz."""
    local_tz = get_local_tz(config)
    now_local = datetime.now(local_tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def day_range(date_obj, config: Config) -> tuple[datetime, datetime]:
    """(start_of_day, start_of_next_day) as UTC datetimes for a given date."""
    local_tz = get_local_tz(config)
    start_local = datetime.combine(date_obj, time.min, tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def resolve_range(config: Config) -> tuple[datetime, datetime]:
    """Resolve date range from ?date= query param or default to today."""
    from datetime import date as _date_cls

    date_str = request.args.get("date")
    if date_str:
        try:
            d = _date_cls.fromisoformat(date_str)
            return day_range(d, config)
        except ValueError:
            pass
    return today_range(config)


def base_query(start: datetime, end: datetime, user_id: str | None = None):
    """Build a filtered TelemetryEvent query for a time window."""
    q = TelemetryEvent.query.filter(
        TelemetryEvent.timestamp >= start,
        TelemetryEvent.timestamp < end,
    )
    if user_id:
        q = q.filter(TelemetryEvent.user_id == user_id)
    return q.order_by(TelemetryEvent.timestamp.asc())


def validate_event(raw: dict) -> str | None:
    """Validate a single telemetry event dict. Returns error string or None."""
    if not isinstance(raw, dict):
        return "event must be a JSON object"

    ts = raw.get("timestamp")
    if ts is not None and not isinstance(ts, str):
        return f"timestamp must be an ISO 8601 string, got {type(ts).__name__}"

    app_name = raw.get("app_name")
    if app_name is not None and not isinstance(app_name, str):
        return f"app_name must be a string, got {type(app_name).__name__}"

    for int_field in ("keystroke_count", "mouse_clicks"):
        val = raw.get(int_field)
        if val is not None:
            if not isinstance(val, (int, float)):
                return f"{int_field} must be a number, got {type(val).__name__}"
            if val < 0:
                return f"{int_field} must be >= 0, got {val}"

    for num_field in ("mouse_distance", "idle_seconds"):
        val = raw.get(num_field)
        if val is not None:
            if not isinstance(val, (int, float)):
                return f"{num_field} must be a number, got {type(val).__name__}"
            if val < 0:
                return f"{num_field} must be >= 0, got {val}"

    return None
