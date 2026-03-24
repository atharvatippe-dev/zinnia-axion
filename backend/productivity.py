"""
Productivity inference engine v2 — confidence-scored 60-second buckets.

Converts raw telemetry events into labelled time-buckets with:
  - productivity state:  productive | non_productive
  - confidence score:    [0.0 … 1.0]
  - reason:              which rule triggered the classification

Decision tree (evaluated top-to-bottom, first match wins)
---------------------------------------------------------
1. Meeting app dominant (≥50% of samples) → ALWAYS productive
   Meetings are real work — talking, listening, presenting.

2. Non-productive app dominant (≥66.67% of samples) → ALWAYS non_productive
   Two-thirds supermajority on YouTube/Netflix/Reddit = not working.
   Checked BEFORE productive apps to catch slacking behavior first.

3. Productive app dominant (≥70% of samples) → productive
   Known productive apps (IDEs, design tools, etc.) = working.
   Higher threshold (70% vs 50% non-prod) ensures genuine productive work.
   Confidence boosted to 0.75.

4. Anti-cheat: suspicious bot pattern detected → non_productive
   Metronomic input with no natural pauses = auto-clicker/key repeater.

5. Confidence ≥ 0.60 → productive
   The confidence score (density, presence, coverage, idle_penalty)
   minus modifiers (distraction, non-prod mix, anti-cheat) is high
   enough to classify as working.

6. Confidence < 0.60 → non_productive
   Insufficient activity signals.

Confidence formula
------------------
  base = 0.35×density + 0.20×presence + 0.25×coverage + 0.20×idle_penalty

  Modifiers (multiplicative):
    × distraction_mult   (0.70 if distraction_ratio ≥ 30%)
    × non_prod_penalty   (1.0 - 0.5 × non_prod_ratio, when < 66.67%)
    × anti_cheat_mult    (0.30 if suspicious pattern)

  final_confidence = clamp(base × modifiers, 0.0, 1.0)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Sequence

from backend.config import Config
from backend.models import TelemetryEvent


STATES = (
    "productive",
    "non_productive",
)


@dataclass
class Bucket:
    """One time-bucket of aggregated telemetry."""

    start: datetime
    end: datetime
    state: str = "non_productive"
    confidence: float = 0.0
    reason: str = ""
    total_keystrokes: int = 0
    total_clicks: int = 0
    total_mouse_distance: float = 0.0
    max_idle: float = 0.0
    dominant_app: str = "unknown"
    dominant_title: str = ""
    event_count: int = 0
    productive_ratio: float = 0.0
    non_prod_ratio: float = 0.0
    meeting_ratio: float = 0.0
    distraction_ratio: float = 0.0
    app_samples: dict = None  # {(app_name, window_title): count}

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "state": self.state,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "total_keystrokes": self.total_keystrokes,
            "total_clicks": self.total_clicks,
            "total_mouse_distance": round(self.total_mouse_distance, 1),
            "max_idle": round(self.max_idle, 1),
            "dominant_app": self.dominant_app,
            "dominant_title": self.dominant_title,
            "event_count": self.event_count,
            "non_prod_ratio": round(self.non_prod_ratio, 3),
            "meeting_ratio": round(self.meeting_ratio, 3),
            "distraction_ratio": round(self.distraction_ratio, 3),
        }


# ── Helpers ─────────────────────────────────────────────────────────

def _is_productive_event(app_name: str, window_title: str, cfg: Config) -> bool:
    """Check if event is from a known productive app (IDE, design tool, etc.)."""
    combined = f"{app_name} {window_title}".lower()
    for pattern in cfg.PRODUCTIVE_APPS:
        if pattern in combined:
            return True
    return False


def _is_non_productive_event(app_name: str, window_title: str, cfg: Config) -> bool:
    combined = f"{app_name} {window_title}".lower()
    for pattern in cfg.NON_PRODUCTIVE_APPS:
        if pattern in combined:
            return True
    return False


def _is_meeting_event(app_name: str, window_title: str, cfg: Config) -> bool:
    combined = f"{app_name} {window_title}".lower()
    for pattern in cfg.MEETING_APPS:
        if pattern in combined:
            return True
    return False


def _dominant(events: Sequence[TelemetryEvent]) -> tuple[str, str]:
    """Return the most-frequent (app_name, window_title) pair."""
    from collections import Counter
    counts: Counter[tuple[str, str]] = Counter()
    for e in events:
        counts[(e.app_name, e.window_title)] += 1
    if not counts:
        return ("unknown", "")
    (app, title), _ = counts.most_common(1)[0]
    return app, title


def _is_suspicious_pattern(
    events: Sequence[TelemetryEvent],
    cfg: Config,
) -> bool:
    """
    Return True if the interaction pattern looks like an auto-clicker or
    key repeater.  Both signals must be suspicious simultaneously.
    """
    if len(events) < 10:
        return False

    per_sample = [e.keystroke_count + e.mouse_clicks for e in events]

    zero_count = sum(1 for v in per_sample if v == 0)
    zero_ratio = zero_count / len(per_sample)
    low_zeros = zero_ratio < cfg.MIN_ZERO_SAMPLE_RATIO

    distinct = len(set(per_sample))
    low_variety = distinct < cfg.MIN_DISTINCT_VALUES

    return low_zeros and low_variety


def _compute_ratios(
    events: Sequence[TelemetryEvent], cfg: Config,
) -> tuple[float, float, float, float]:
    """Return (productive_ratio, non_prod_ratio, meeting_ratio, distraction_ratio)."""
    n = len(events)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0

    productive = sum(
        1 for e in events
        if _is_productive_event(e.app_name, e.window_title, cfg)
    )
    non_prod = sum(
        1 for e in events
        if _is_non_productive_event(e.app_name, e.window_title, cfg)
    )
    meeting = sum(
        1 for e in events
        if _is_meeting_event(e.app_name, e.window_title, cfg)
    )
    distraction = sum(
        1 for e in events
        if getattr(e, "distraction_visible", False)
    )
    return productive / n, non_prod / n, meeting / n, distraction / n


def _confidence(
    total_keystrokes: int,
    total_clicks: int,
    total_mouse_distance: float,
    max_idle: float,
    event_count: int,
    bucket_size: int,
    cfg: Config,
    non_prod_ratio: float = 0.0,
    distraction_ratio: float = 0.0,
    suspicious: bool = False,
) -> float:
    """
    Compute confidence ∈ [0, 1].

    base = 0.35×density + 0.20×presence + 0.25×coverage + 0.20×idle_penalty

    Modifiers (multiplicative):
      × distraction_mult  (0.70 if distraction_ratio ≥ DISTRACTION_MIN_RATIO)
      × non_prod_penalty  (1.0 - NON_PROD_MIX_WEIGHT × non_prod_ratio)
      × anti_cheat_mult   (ANTI_CHEAT_CONFIDENCE_MULT if suspicious)
    """
    if event_count == 0:
        return 0.0

    interaction = total_keystrokes + total_clicks
    threshold = max(cfg.PRODUCTIVE_INTERACTION_THRESHOLD, 1)
    movement_thresh = max(cfg.MOUSE_MOVEMENT_THRESHOLD, 1)

    density = min(interaction / threshold, 1.0)
    presence = min(total_mouse_distance / movement_thresh, 1.0)
    coverage = min(event_count / max(bucket_size, 1), 1.0)
    idle_penalty = 1.0 - min(max_idle / max(bucket_size, 1), 1.0)

    base = 0.35 * density + 0.20 * presence + 0.25 * coverage + 0.20 * idle_penalty

    # Distraction modifier
    if distraction_ratio >= cfg.DISTRACTION_MIN_RATIO:
        base *= cfg.DISTRACTION_CONFIDENCE_MULT

    # Non-productive mix modifier (only when below hard-block threshold)
    if 0 < non_prod_ratio < cfg.NON_PROD_DOMINANT_RATIO:
        base *= (1.0 - cfg.NON_PROD_MIX_WEIGHT * non_prod_ratio)

    # Anti-cheat modifier
    if suspicious:
        base *= cfg.ANTI_CHEAT_CONFIDENCE_MULT

    return max(0.0, min(base, 1.0))


# ── Main engine ─────────────────────────────────────────────────────

def bucketize(
    events: Sequence[TelemetryEvent],
    cfg: Config | None = None,
) -> list[Bucket]:
    """
    Slice *events* into fixed-width time buckets and classify productivity
    using the v2 confidence-scored decision tree.

    Parameters
    ----------
    events : sequence of TelemetryEvent, assumed sorted by timestamp ASC.
    cfg    : Config instance (defaults to global Config()).

    Returns
    -------
    List of Bucket objects, one per time-window that contains ≥ 1 event.
    """
    if cfg is None:
        cfg = Config()

    if not events:
        return []

    bucket_size = cfg.BUCKET_SIZE_SEC

    # ── Group events into clock-aligned time-windows ─────────────
    # Buckets are anchored to fixed clock boundaries (e.g. 12:00:00,
    # 12:01:00, 12:02:00 for 60-second buckets) so adding new events
    # never shifts existing bucket boundaries or re-classifies old data.
    # Timestamps in the DB are naive local time, so we use a naive epoch
    # and naive datetime.now() to keep everything consistent.
    _epoch = datetime(1970, 1, 1)

    def _strip_tz(ts: datetime) -> datetime:
        return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts

    buckets_map: dict[int, list[TelemetryEvent]] = {}
    for e in events:
        epoch_sec = (_strip_tz(e.timestamp) - _epoch).total_seconds()
        idx = int(epoch_sec // bucket_size)
        buckets_map.setdefault(idx, []).append(e)

    # Exclude the current open bucket (still accumulating events) so
    # classifications are final and never flip on the next refresh.
    now_epoch = (datetime.now() - _epoch).total_seconds()
    current_idx = int(now_epoch // bucket_size)

    result: list[Bucket] = []

    for idx in sorted(buckets_map):
        if idx >= current_idx:
            continue
        evts = buckets_map[idx]
        b_start = _epoch + timedelta(seconds=idx * bucket_size)
        b_end = b_start + timedelta(seconds=bucket_size)

        total_keystrokes = sum(e.keystroke_count for e in evts)
        total_clicks = sum(e.mouse_clicks for e in evts)
        total_mouse_distance = sum(e.mouse_distance for e in evts)
        max_idle = max(
            (min(e.idle_seconds, bucket_size) for e in evts),
            default=0.0,
        )
        dom_app, dom_title = _dominant(evts)
        app_sample_counts = {}
        for e in evts:
            key = (e.app_name, e.window_title)
            app_sample_counts[key] = app_sample_counts.get(key, 0) + 1

        productive_ratio, non_prod_ratio, meeting_ratio, distraction_ratio = _compute_ratios(evts, cfg)
        suspicious = _is_suspicious_pattern(evts, cfg)

        conf = _confidence(
            total_keystrokes, total_clicks, total_mouse_distance,
            max_idle, len(evts), bucket_size, cfg,
            non_prod_ratio=non_prod_ratio,
            distraction_ratio=distraction_ratio,
            suspicious=suspicious,
        )

        # ── Decision tree v2 (updated with productive apps) ────────
        # Rule 1: Meeting apps are ALWAYS productive (highest priority)
        if meeting_ratio >= cfg.MEETING_DOMINANT_RATIO:
            state = "productive"
            conf = max(conf, 0.85)
            reason = "meeting_detected"

        # Rule 2: Non-productive apps dominant (≥66.67%) → non-productive
        # Check slacking BEFORE giving credit for productive apps
        elif non_prod_ratio >= cfg.NON_PROD_DOMINANT_RATIO:
            state = "non_productive"
            conf = min(conf, 0.40)
            reason = "non_productive_app_dominant"

        # Rule 3: Productive apps dominant (≥70%) → productive
        # Higher threshold (70% vs 50%) to ensure genuine productive work
        elif productive_ratio >= cfg.PRODUCTIVE_DOMINANT_RATIO:
            state = "productive"
            conf = max(conf, 0.75)  # Boost confidence for known productive apps
            reason = "productive_app_dominant"

        # Rule 4: Anti-cheat — bot-like input pattern
        elif suspicious:
            state = "non_productive"
            conf = min(conf, 0.20)
            reason = "bot_like_input_pattern"

        # Rule 5: Confidence above threshold → productive
        elif conf >= cfg.CONFIDENCE_THRESHOLD:
            state = "productive"
            reason = "confidence_above_threshold"

        # Rule 6: Fallthrough — insufficient activity
        else:
            state = "non_productive"
            reason = "insufficient_activity_signals"

        result.append(
            Bucket(
                start=b_start,
                end=b_end,
                state=state,
                confidence=conf,
                reason=reason,
                total_keystrokes=total_keystrokes,
                total_clicks=total_clicks,
                total_mouse_distance=total_mouse_distance,
                max_idle=max_idle,
                dominant_app=dom_app,
                dominant_title=dom_title,
                event_count=len(evts),
                productive_ratio=productive_ratio,
                non_prod_ratio=non_prod_ratio,
                meeting_ratio=meeting_ratio,
                distraction_ratio=distraction_ratio,
                app_samples=app_sample_counts,
            )
        )

    return result


def summarize_buckets(buckets: list[Bucket]) -> dict:
    """
    Aggregate bucket list into a summary dict:
      { productive: <sec>, non_productive: <sec>,
        total_seconds: <sec>, total_buckets: <int> }
    """
    summary: dict[str, float] = {s: 0.0 for s in STATES}
    for b in buckets:
        duration = (b.end - b.start).total_seconds()
        summary[b.state] = summary.get(b.state, 0.0) + duration

    total = sum(summary.values())
    return {
        **{k: int(v) for k, v in summary.items()},
        "total_seconds": int(total),
        "total_buckets": len(buckets),
    }


def _is_browser(app_name: str, cfg: Config) -> bool:
    """Return True if the app is a web browser (per BROWSER_APPS config).

    Short patterns (< 4 chars, e.g. "arc") require exact match to avoid
    false positives like "searchhost" containing "arc".  Longer patterns use
    bidirectional substring matching so both the full display name
    ("Google Chrome") and the short process name ("chrome") are recognized.
    """
    name_lower = app_name.lower()
    for b in cfg.BROWSER_APPS:
        if len(b) < 4:
            if name_lower == b:
                return True
        elif b in name_lower or name_lower in b:
            return True
    return False


def _extract_site_label(window_title: str, cfg: Config) -> str:
    """
    Extract a human-readable site/service name from a browser window title.

    Strategy (first match wins):
      1. Check against NON_PRODUCTIVE_APPS patterns → return the matched keyword
      2. Check against MEETING_APPS patterns → return the matched keyword
      3. Fallback: split on common title delimiters and take the last segment
      4. Last resort: truncate to 40 chars
    """
    if not window_title or not window_title.strip():
        return "Other"

    title_lower = window_title.lower()

    for pattern in cfg.NON_PRODUCTIVE_APPS:
        if pattern in title_lower:
            return pattern.capitalize()

    for pattern in cfg.MEETING_APPS:
        if pattern in title_lower:
            return pattern.title()

    for delimiter in [" - ", " — ", " | ", " · "]:
        if delimiter in window_title:
            segment = window_title.rsplit(delimiter, 1)[-1].strip()
            if segment:
                return segment[:40]

    return window_title[:40] if len(window_title) > 40 else window_title


def app_breakdown(buckets: list[Bucket], cfg: Config | None = None) -> list[dict]:
    """
    Per-app breakdown with proportional time splitting.

    Instead of assigning the entire bucket duration to the dominant app,
    each bucket's time is split across all apps proportionally based on
    the number of samples each app had in that bucket.

    For browser apps, entries are split by website using the window title.
    """
    if cfg is None:
        cfg = Config()

    from collections import defaultdict

    apps: dict[str, dict] = defaultdict(lambda: {s: 0.0 for s in STATES})
    for b in buckets:
        duration = (b.end - b.start).total_seconds()

        if b.app_samples and b.event_count > 0:
            for (app_name, title), count in b.app_samples.items():
                share = duration * (count / b.event_count)
                if _is_browser(app_name, cfg):
                    site = _extract_site_label(title, cfg)
                    key = f"{app_name} — {site}"
                else:
                    key = app_name
                apps[key][b.state] += share
        else:
            if _is_browser(b.dominant_app, cfg):
                site = _extract_site_label(b.dominant_title, cfg)
                key = f"{b.dominant_app} — {site}"
            else:
                key = b.dominant_app
            apps[key][b.state] += duration

    result = []
    for app_name, states in sorted(apps.items(), key=lambda x: -sum(x[1].values())):
        total = sum(states.values())
        productive_time = states.get("productive", 0)
        category = "productive" if productive_time > total / 2 else "non_productive"
        result.append({
            "app_name": app_name,
            "category": category,
            "total_seconds": int(total),
            "states": {k: int(v) for k, v in states.items()},
        })
    return result
