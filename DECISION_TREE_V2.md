# Productivity Classification — Decision Tree v2

## Overview

This document describes the revised productivity classification engine.

**Key changes from v1:**
- Bucket size: 10 seconds → **60 seconds** (60 raw samples per bucket)
- Confidence score is now **central** to every classification decision
- Rules reduced from 5 independent checks to **5 confidence-aware rules**
- Every bucket stores a continuous confidence value (0.0–1.0) for auditability

---

## Data Flow

```
Tracker Agent (1 sample/sec)
  │
  │  Every 1 second, captures:
  │    app_name, window_title, keystroke_count, mouse_clicks,
  │    mouse_distance, idle_seconds, distraction_visible
  │
  │  Every 10 seconds, sends batch of 10 samples to backend
  │
  ▼
Backend (stores raw samples)
  │
  │  telemetry_events table: 1 row per sample
  │  No classification at write time
  │
  ▼
Dashboard Request (read time)
  │
  │  Groups 60 consecutive samples into one bucket
  │  Runs decision tree below
  │  Returns: state + confidence per bucket
  │
  ▼
Dashboard Display
  │
  │  Sums productive/non-productive buckets
  │  Shows total productive time, app breakdown, etc.
  │  Refreshes every 60 seconds
```

---

## Bucket Construction

For each 60-second window, collect up to 60 raw samples and compute:

| Field | Formula | Description |
|-------|---------|-------------|
| `total_keystrokes` | `sum(sample.keystroke_count)` | Total keys pressed in 60s |
| `total_clicks` | `sum(sample.mouse_clicks)` | Total mouse clicks in 60s |
| `total_mouse_dist` | `sum(sample.mouse_distance)` | Total mouse movement in 60s |
| `max_idle` | `max(sample.idle_seconds)` | Longest idle period in 60s |
| `event_count` | `count(samples)` | How many of 60 expected samples arrived |
| `dominant_app` | Most frequent `app_name` across samples | Primary app used |
| `non_prod_count` | Samples where `app_name` matches NON_PRODUCTIVE_APPS | Non-productive sample count |
| `non_prod_ratio` | `non_prod_count / event_count` | Fraction of time on non-productive apps |
| `meeting_count` | Samples where `app_name` matches MEETING_APPS | Meeting sample count |
| `meeting_ratio` | `meeting_count / event_count` | Fraction of time in meetings |
| `distraction_count` | Samples where `distraction_visible = true` | Distraction sample count |
| `distraction_ratio` | `distraction_count / event_count` | Fraction of time with distraction on second screen |
| `samples_with_movement` | Samples where `mouse_distance > 0` | How many samples had mouse activity |
| `zero_interaction_count` | Samples where `keystroke_count + mouse_clicks == 0` | Samples with no input |

---

## Confidence Score Calculation

Computed **before** the decision tree runs. Every bucket gets a confidence value.

### Step 1: Base Components

| Component | Weight | Formula | What it measures |
|-----------|--------|---------|-----------------|
| **Density** | 35% | `min((total_keystrokes + total_clicks) / INTERACTION_THRESHOLD_60S, 1.0)` | Was the user actively typing/clicking? |
| **Presence** | 20% | `min(total_mouse_dist / MOUSE_MOVEMENT_THRESHOLD_60S, 1.0)` | Was the user physically at the desk? (mouse movement = scrolling, tracking, reading) |
| **Coverage** | 25% | `event_count / 60` | Did the tracker send data for the full 60 seconds? Low coverage = network issue, sleep, or crash |
| **Idle Penalty** | 20% | `1.0 - min(max_idle / 60, 1.0)` | How long was the longest idle gap? High idle = user walked away |

```
base_score = 0.35 × density + 0.20 × presence + 0.25 × coverage + 0.20 × idle_penalty
```

### Step 2: Modifiers (applied multiplicatively)

| Modifier | Condition | Multiplier | Reason |
|----------|-----------|------------|--------|
| **Distraction penalty** | `distraction_ratio ≥ 0.30` | × 0.70 | Non-productive app visible on second monitor/split-screen/PiP |
| **Non-productive mix** | `non_prod_ratio > 0 AND < 0.6667` | × `(1.0 - 0.5 × non_prod_ratio)` | Some time spent on non-productive apps, but not dominant |
| **Anti-cheat** | Suspicious pattern detected | × 0.30 | Bot-like input (auto-clicker/key repeater) |

```
final_confidence = base_score × distraction_mult × non_prod_mult × anti_cheat_mult
```

### Step 3: Clamp

```
final_confidence = max(0.0, min(final_confidence, 1.0))
```

### Confidence Score Examples

| Scenario | Density | Presence | Coverage | Idle Pen | Modifiers | Final | Meaning |
|----------|---------|----------|----------|----------|-----------|-------|---------|
| Deep coding in VS Code | 0.95 | 0.80 | 1.00 | 0.95 | none | **0.93** | Clearly productive |
| Reading docs, no typing | 0.05 | 0.90 | 1.00 | 0.90 | none | **0.55** | Present but low interaction — passes 0.55 threshold |
| Coding with Slack on 2nd monitor | 0.90 | 0.75 | 1.00 | 0.90 | ×0.70 distraction | **0.63** | Productive but distracted — still passes 0.55 |
| Coding with YouTube on 2nd monitor | 0.90 | 0.75 | 1.00 | 0.90 | ×0.70 distraction | **0.63** | Same score, but Rule 2 may also apply |
| VS Code open, user walked away | 0.00 | 0.10 | 1.00 | 0.10 | none | **0.29** | App is productive but nobody is there |
| Zoom call, user listening | 0.02 | 0.30 | 1.00 | 0.70 | none | **0.39** | Low score — but Rule 1 always overrides to productive |
| Auto-clicker running | 0.99 | 0.50 | 1.00 | 0.95 | ×0.30 anti-cheat | **0.27** | High density but bot-like pattern detected |
| Laptop lid closed, woke up | 0.00 | 0.00 | 0.17 | 0.00 | none | **0.04** | Almost no data, clearly away |
| 40s YouTube + 20s VS Code | 0.30 | 0.50 | 1.00 | 0.85 | ×0.70 non-prod | **0.37** | Non-productive dominant — Rule 2 catches this |

---

## Decision Tree

```
60-SECOND BUCKET (up to 60 raw samples)
│
│  ┌─────────────────────────────────────────────┐
│  │  COMPUTE final_confidence (formula above)    │
│  └─────────────────────────────────────────────┘
│
│
▼
RULE 1: MEETING APP OVERRIDE
│
│  Condition: meeting_ratio ≥ 0.50
│  (30+ of 60 samples are Zoom, Teams, Meet, etc.)
│
├─ YES:
│   │
│   → STATE: PRODUCTIVE
│     confidence: max(final_confidence, 0.85)
│     reason: "meeting_detected"
│
│   WHY: Meetings are always productive — period.
│   Meetings have zero keystrokes and low mouse movement
│   by nature. A person listening to a standup, presenting
│   slides, or screen-sharing is working. The confidence
│   formula would unfairly penalize them without this
│   unconditional override.
│
│   This applies regardless of idle time. In meetings,
│   users listen, talk, and watch — none of which produce
│   keyboard/mouse signals. Penalizing idle during a
│   meeting would misclassify every call where the user
│   is paying attention but not touching the computer.
│
├─ NO: Continue to Rule 2
│
│
▼
RULE 2: NON-PRODUCTIVE APP DOMINANT
│
│  Condition: non_prod_ratio ≥ 0.6667
│  (40+ of 60 samples are YouTube, Netflix, Reddit, etc.)
│
├─ YES:
│   │
│   → STATE: NON_PRODUCTIVE
│     confidence: min(final_confidence, 0.40)
│     reason: "non_productive_app_dominant"
│
│   WHY: If the user spent two-thirds or more of the minute
│   on YouTube/Netflix/Reddit, the bucket is non-productive
│   regardless of what happened in the remaining time.
│   Confidence is capped at 0.40 — we are highly certain
│   this is not work.
│
│   The threshold is set at 66.67% (not 50%) to be fairer
│   to users who briefly check a non-productive site as
│   part of a work context (e.g., looking up a tutorial
│   on YouTube for 20 seconds). Only when non-productive
│   apps consume a clear supermajority of the bucket does
│   it hard-block.
│
│   NOTE: If non_prod_ratio > 0 but < 0.6667, the bucket
│   is NOT blocked here. Instead, the non_prod_penalty
│   modifier already reduced the confidence score
│   proportionally. A 15-second YouTube visit in 60s of
│   coding = moderate penalty, not a hard block.
│
├─ NO: Continue to Rule 3
│
│
▼
RULE 3: ANTI-CHEAT (BOT DETECTION)
│
│  Condition: suspicious_pattern == True
│
│  Detection (BOTH must be true simultaneously):
│
│  Signal A — Zero-sample ratio too low:
│    zero_interaction_count / event_count < MIN_ZERO_SAMPLE_RATIO (0.25)
│    Real humans have natural pauses (thinking, reading) where
│    interaction drops to zero. Bots produce input on every sample.
│
│  Signal B — Too few distinct values:
│    count(unique per-sample interaction values) < MIN_DISTINCT_VALUES (2)
│    Real typing produces varied counts (0, 1, 3, 7, 12...).
│    Auto-clickers produce the same value every sample (e.g., always 1).
│
│  Requires ≥ 10 samples to judge (short buckets skip this check).
│
├─ YES:
│   │
│   → STATE: NON_PRODUCTIVE
│     confidence: min(final_confidence, 0.20)
│     reason: "bot_like_input_pattern"
│
│   WHY: The interaction pattern is metronomic — no natural
│   pauses, no variation. This is an auto-clicker, key repeater,
│   or mouse jiggler. Even though density is high, it's not
│   human work.
│
├─ NO: Continue to Rule 4
│
│
▼
RULE 4: CONFIDENCE THRESHOLD
│
│  Condition: final_confidence ≥ 0.55
│
│  This is the main classification gate. If the bucket passed
│  Rules 1-3 without being overridden, the confidence score
│  makes the final call.
│
│  A confidence of 0.55+ means some meaningful combination of:
│    - User was typing/clicking (density)
│    - User was physically present (presence via mouse movement)
│    - Tracker data is complete (coverage)
│    - User wasn't idle for long (idle penalty)
│    - No significant distraction on other screens
│    - No non-productive apps consuming time
│    - No bot-like patterns
│
│  The threshold is set at 0.55 (not higher) to give fair
│  credit to reading-heavy work patterns (code review, docs,
│  PR review) where density is low but presence and coverage
│  are high — these are legitimate productive activities.
│
├─ YES:
│   │
│   → STATE: PRODUCTIVE
│     confidence: final_confidence
│     reason: "confidence_above_threshold"
│
│   EXAMPLES THAT PASS:
│   - Coding in VS Code with steady typing (density ~0.9, conf ~0.85)
│   - Coding with Slack on second monitor (conf ~0.63, above 0.55)
│   - Reviewing a PR with scrolling, occasional clicks (density ~0.3,
│     presence ~0.8, conf ~0.62)
│   - Reading docs, no typing, mouse scrolling (density ~0.05,
│     presence ~0.9, coverage 1.0, idle_pen ~0.9, conf ~0.55)
│   - Writing in Google Docs with some mouse usage (conf ~0.70)
│
│   EXAMPLES THAT FAIL:
│   - VS Code open but user on phone (density 0, presence 0.1, conf ~0.29)
│   - Reading docs with YouTube on second monitor (conf drops below 0.55
│     after distraction penalty)
│   - Laptop awake but user in kitchen (idle 50s, conf ~0.15)
│
├─ NO: Continue to Rule 5
│
│
▼
RULE 5: FALLTHROUGH — INSUFFICIENT ACTIVITY
│
│  Condition: final_confidence < 0.55
│
│  → STATE: NON_PRODUCTIVE
│    confidence: final_confidence
│    reason: "insufficient_activity_signals"
│
│  The bucket did not trigger any override (meeting, non-productive
│  app, or bot), AND the confidence score is too low for a productive
│  classification.
│
│  POSSIBLE CAUSES:
│  - Low density + low presence = user not interacting with computer
│  - High idle = user walked away from desk
│  - Low coverage = tracker missed samples (network, sleep, crash)
│  - Distraction visible = focus split with non-productive content
│  - Non-productive app mix = some time on YouTube/Reddit reduced score
│  - Any combination of mild issues across all 4 parameters
│
│  NOTE: The confidence value is stored, so a manager or employee
│  can see WHY a bucket was non-productive:
│    0.50 = borderline (almost productive, minor distraction)
│    0.30 = clearly disengaged
│    0.05 = computer was on but nobody was there
```

---

## Stored Output Per Bucket

Every classified bucket writes one record:

| Field | Type | Description |
|-------|------|-------------|
| `bucket_start` | datetime | Start of the 60-second window |
| `bucket_end` | datetime | End of the 60-second window |
| `state` | string | `"productive"` or `"non_productive"` |
| `confidence` | float | 0.00 to 1.00 — how certain the classification is |
| `reason` | string | Which rule triggered: `meeting_detected`, `non_productive_app_dominant`, `bot_like_input_pattern`, `confidence_above_threshold`, `insufficient_activity_signals` |
| `dominant_app` | string | Most frequent app in the bucket |
| `dominant_title` | string | Most frequent window title |
| `total_keystrokes` | int | Sum of keystrokes across 60 samples |
| `total_clicks` | int | Sum of clicks across 60 samples |
| `total_mouse_dist` | float | Sum of mouse distance across 60 samples |
| `max_idle` | float | Longest idle period in the bucket |
| `event_count` | int | Samples received (out of 60 expected) |
| `non_prod_ratio` | float | Fraction of samples on non-productive apps |
| `meeting_ratio` | float | Fraction of samples in meeting apps |
| `distraction_ratio` | float | Fraction of samples with distraction visible |

---

## Configuration (Tunable Per Deployment)

| Variable | Default | Description |
|----------|---------|-------------|
| `BUCKET_SIZE_SEC` | `60` | Bucket window size in seconds |
| `CONFIDENCE_THRESHOLD` | `0.55` | Minimum confidence to classify as productive |
| `INTERACTION_THRESHOLD_60S` | `12` | Keystrokes + clicks needed for density = 1.0 (scaled 6× from 10s value of 2) |
| `KEYSTROKE_THRESHOLD_60S` | `6` | Keystrokes alone for density = 1.0 (scaled 6× from 10s value of 1) |
| `MOUSE_THRESHOLD_60S` | `6` | Clicks alone for density = 1.0 (scaled 6× from 10s value of 1) |
| `MOUSE_MOVEMENT_THRESHOLD_60S` | `48` | Mouse distance for presence = 1.0 (scaled 6× from 10s value of 8) |
| `IDLE_AWAY_THRESHOLD` | `30` | Seconds of OS idle before considered "away" |
| `MOUSE_MOVEMENT_MIN_SAMPLES` | `18` | Minimum samples with mouse movement for sustained presence (scaled 6× from 10s value of 3) |
| `MIN_ZERO_SAMPLE_RATIO` | `0.25` | Anti-cheat: minimum fraction of zero-interaction samples expected |
| `MIN_DISTINCT_VALUES` | `3` | Anti-cheat: minimum unique per-sample interaction counts (raised from 2 for 60 samples) |
| `DISTRACTION_MIN_RATIO` | `0.30` | Fraction of samples with visible distraction to trigger penalty |
| `NON_PROD_DOMINANT_RATIO` | `0.6667` | Fraction of samples on non-productive apps to hard-block (two-thirds) |
| `MEETING_DOMINANT_RATIO` | `0.50` | Fraction of samples in meeting app to trigger meeting override (always productive) |
| `DISTRACTION_CONFIDENCE_MULT` | `0.70` | Confidence multiplier when distraction is visible |
| `NON_PROD_MIX_WEIGHT` | `0.50` | Weight applied to non_prod_ratio for the mix penalty |
| `ANTI_CHEAT_CONFIDENCE_MULT` | `0.30` | Confidence multiplier when bot pattern detected |

---

## Comparison: v1 (10s) vs v2 (60s + Confidence)

| Scenario | v1 Result | v2 Result | Better? |
|----------|-----------|-----------|---------|
| Coding with 3s Slack notification | FLIP: 7s productive, 3s non-productive depending on snapshot timing | PRODUCTIVE (conf 0.88 — density high, brief non-prod mix penalty) | v2 |
| VS Code open, user walked away | PRODUCTIVE (VS Code = productive app) | NON-PRODUCTIVE (conf 0.29 — no density, no presence, high idle) | v2 |
| Zoom call, user listening | PRODUCTIVE (Zoom = meeting app) | PRODUCTIVE (Rule 1 — meetings always productive, conf 0.85) | Same |
| Zoom left open after call ended | PRODUCTIVE (Zoom = meeting app) | PRODUCTIVE (Rule 1 — meetings always productive) | Same |
| Auto-clicker on VS Code | PRODUCTIVE or NON-PRODUCTIVE (binary anti-cheat) | NON-PRODUCTIVE (conf 0.27 — anti-cheat multiplier crushes score) | v2 |
| 40s YouTube + 20s VS Code in same minute | Two separate buckets: 4 non-prod + 2 prod | One bucket: NON-PRODUCTIVE (non_prod_ratio 0.67 ≥ 0.6667, Rule 2) | Same |
| Reading code, no typing, mouse scrolling | Depends on mouse threshold (binary pass/fail) | Productive if presence + coverage + idle are good enough (conf ~0.55, passes threshold) | v2 |
| Reading code with YouTube on 2nd monitor | NON-PRODUCTIVE (distraction blocks Rule 4 entirely) | Confidence penalized by ×0.70 — might still pass or fail depending on other signals | v2 (fairer) |
| 5s YouTube glance during 55s of coding | 1 bucket flips to non-prod (if snapshot lands on YouTube) | PRODUCTIVE (non_prod_ratio 0.08 → minor penalty, conf still ~0.80) | v2 |
| Employee disputes productivity score | "System says non-productive" — no detail | "Bucket confidence was 0.52 — borderline due to 30% idle and some Slack" — auditable | v2 |
| HR wants different threshold for support team | Change app list (blunt) | Change CONFIDENCE_THRESHOLD to 0.45 for support team | v2 |

---

## Dashboard Impact

- **Refresh interval**: 60 seconds (one new bucket per cycle)
- **Time increments**: Productive/non-productive time jumps by 60 seconds per bucket
- **Totals**: Sum of all productive buckets × 60 seconds = total productive time
- **Accuracy**: Higher — 60 samples per decision vs 10, plus confidence prevents false classifications
- **Auditability**: Every bucket has a confidence score and reason — managers can explain decisions

---

## Migration from v1

1. **No tracker changes** — Agent already polls every 1 second, sends every 10 seconds. No modification needed.
2. **No data loss** — Raw telemetry_events table is unchanged. v2 reads the same rows, just groups them into larger buckets.
3. **Backward compatible** — Set `BUCKET_SIZE_SEC=10` to revert to v1 behavior. The confidence score still computes but the threshold-based rules dominate with 10 samples.
4. **Re-classify historical data** — Since raw samples are preserved, switch to v2 and all past data is reclassified with the new engine. No re-collection needed.
5. **Config changes** — Scale interaction/movement thresholds by 6× for 60-second buckets (see Configuration table above).
