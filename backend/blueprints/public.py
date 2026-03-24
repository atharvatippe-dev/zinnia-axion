"""
Public blueprint — unauthenticated read-only endpoints.

GET  /summary/today     — productivity state totals
GET  /apps              — per-app breakdown
GET  /daily             — daily time-series
POST /cleanup           — purge old events
GET  /db-stats          — database size info
GET  /dashboard/<uid>   — self-contained HTML dashboard
GET  /health            — health check
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, render_template

from backend.models import db, TelemetryEvent
from backend.audit import log_action
from backend.productivity import bucketize, summarize_buckets, app_breakdown
from backend.utils import get_config, resolve_range, base_query, today_range, day_range, get_local_tz

logger = logging.getLogger("backend.blueprints.public")

public_bp = Blueprint("public", __name__)


def _run_cleanup(config) -> int:
    """Delete events older than DATA_RETENTION_DAYS. Returns rows deleted."""
    retention = config.DATA_RETENTION_DAYS
    if retention <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
    count = TelemetryEvent.query.filter(TelemetryEvent.timestamp < cutoff).delete()
    db.session.commit()

    if count > 0:
        logger.info(
            "Cleanup: deleted %d events older than %d days (before %s).",
            count, retention, cutoff.isoformat(),
        )
        log_action("system", "retention_cleanup",
                   detail=f"Deleted {count} events older than {retention}d")
    else:
        logger.info("Cleanup: no events older than %d days to delete.", retention)

    return count


def _bucketize_per_user(events, cfg):
    """Bucketize events per-user, then merge all buckets.

    When events span multiple users, mixing them into a single stream
    inflates per-bucket activity metrics (keystrokes, mouse, etc.) and
    corrupts the confidence score.  This helper groups by user_id first,
    bucketizes each user independently, then returns the combined list.
    """
    if not events:
        return []
    user_ids = {e.user_id for e in events}
    if len(user_ids) <= 1:
        return bucketize(events, cfg)

    by_user: dict[str, list] = defaultdict(list)
    for e in events:
        by_user[e.user_id].append(e)

    all_buckets = []
    for uid_events in by_user.values():
        all_buckets.extend(bucketize(uid_events, cfg))
    return all_buckets


@public_bp.route("/summary/today", methods=["GET"])
def summary_today():
    """Productivity state totals for today (or ?date=YYYY-MM-DD)."""
    cfg = get_config()
    user_id = request.args.get("user_id")
    start, end = resolve_range(cfg)
    events = base_query(start, end, user_id).all()
    buckets = _bucketize_per_user(events, cfg)
    summary = summarize_buckets(buckets)
    return jsonify(summary), 200


@public_bp.route("/apps", methods=["GET"])
def apps():
    """Per-app breakdown for today (or ?date=YYYY-MM-DD)."""
    cfg = get_config()
    user_id = request.args.get("user_id")
    start, end = resolve_range(cfg)
    events = base_query(start, end, user_id).all()
    buckets = _bucketize_per_user(events, cfg)
    breakdown = app_breakdown(buckets, cfg)
    return jsonify(breakdown), 200


@public_bp.route("/daily", methods=["GET"])
def daily():
    """Daily time-series of state totals."""
    try:
        num_days = int(request.args.get("days", 7))
    except ValueError:
        num_days = 7

    user_id = request.args.get("user_id")
    cfg = get_config()
    local_tz = get_local_tz(cfg)
    today = datetime.now(local_tz).date()
    series: list[dict] = []

    for offset in range(num_days - 1, -1, -1):
        d = today - timedelta(days=offset)
        start, end = day_range(d, cfg)
        events = base_query(start, end, user_id).all()
        buckets = _bucketize_per_user(events, cfg)
        summary = summarize_buckets(buckets)
        summary["date"] = d.isoformat()
        series.append(summary)

    return jsonify(series), 200


@public_bp.route("/cleanup", methods=["POST"])
def cleanup():
    """Manually trigger cleanup of old events."""
    cfg = get_config()
    data = request.get_json(silent=True)

    if data and "days" in data:
        try:
            override_days = int(data["days"])
            original = cfg.DATA_RETENTION_DAYS
            cfg.DATA_RETENTION_DAYS = override_days
            deleted = _run_cleanup(cfg)
            cfg.DATA_RETENTION_DAYS = original
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid 'days' value"}), 400
    else:
        deleted = _run_cleanup(cfg)

    log_action("admin", "manual_cleanup",
               detail=f"Deleted {deleted} events (retention={cfg.DATA_RETENTION_DAYS}d)")
    return jsonify({"deleted": deleted, "retention_days": cfg.DATA_RETENTION_DAYS}), 200


@public_bp.route("/db-stats", methods=["GET"])
def db_stats():
    """Database statistics: total events, date range, estimated size."""
    total = TelemetryEvent.query.count()
    oldest = TelemetryEvent.query.order_by(TelemetryEvent.timestamp.asc()).first()
    newest = TelemetryEvent.query.order_by(TelemetryEvent.timestamp.desc()).first()
    cfg = get_config()

    return jsonify({
        "total_events": total,
        "oldest_event": oldest.timestamp.isoformat() if oldest else None,
        "newest_event": newest.timestamp.isoformat() if newest else None,
        "retention_days": cfg.DATA_RETENTION_DAYS,
        "estimated_size_mb": round(total * 0.0002, 2),
    }), 200


@public_bp.route("/dashboard/<user_id>", methods=["GET"])
def user_dashboard(user_id: str):
    """Serve a self-contained HTML dashboard for a specific user."""
    log_action("visitor", "view_dashboard", target_user=user_id)
    return render_template("dashboard.html", user_id=user_id)


@public_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200
