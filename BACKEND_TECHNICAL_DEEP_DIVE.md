# Zinnia Axion — Backend Technical Deep Dive

**Audience:** Technology Head / Engineering Leadership
**Prepared:** March 2026

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Language** | Python | 3.10+ | Core backend language |
| **Web Framework** | Flask | 3.0+ | REST API framework |
| **ORM** | Flask-SQLAlchemy | 3.1+ | Database abstraction |
| **Database** | PostgreSQL (prod) / SQLite (dev) | 15+ / 3.x | Persistent storage |
| **Authentication** | Authlib | 1.3+ | OIDC SSO client (Azure AD, Okta) |
| **CORS** | Flask-CORS | 4.0+ | Cross-origin request control |
| **Rate Limiting** | Flask-Limiter | 3.5+ | Per-endpoint rate throttling |
| **CSRF Protection** | Flask-WTF | 1.2+ | Cross-site request forgery prevention |
| **Migrations** | Alembic | 1.13+ | Schema version management |
| **Validation** | Marshmallow | 3.20+ | Schema validation (available) |
| **Session** | Flask built-in (server-side) | — | Secure session management |
| **Environment** | python-dotenv | 1.0+ | `.env` configuration loading |

---

## Folder Structure

```
backend/
├── app.py                        # Application factory — the entry point
├── config.py                     # Central configuration (50+ env vars)
├── models.py                     # 9 SQLAlchemy models (DB schema)
├── productivity.py               # Classification engine (Decision Tree V2)
├── audit.py                      # Audit logging helper
├── utils.py                      # Shared utility functions
│
├── auth/                         # Authentication & Authorization
│   ├── __init__.py
│   ├── oidc.py                   # OIDC SSO client (Authlib)
│   ├── authz.py                  # Decorators: @admin_required, @team_scoped
│   └── team_hierarchy.py         # Recursive subtree computation
│
├── blueprints/                   # Route handlers (Flask Blueprints)
│   ├── __init__.py
│   ├── admin.py                  # 22 admin endpoints (SSO-protected)
│   ├── public.py                 # 7 public read-only endpoints
│   └── tracker.py                # 2 telemetry ingest endpoints
│
├── middleware/                    # Request/response processing
│   ├── __init__.py
│   ├── request_context.py        # request_id generation, RLS injection
│   └── security_headers.py       # HSTS, CSP, X-Frame-Options, etc.
│
├── services/                     # Business logic (decoupled from routes)
│   ├── __init__.py
│   └── admin_service.py          # Team-scoped leaderboard, user management
│
└── templates/                    # Server-rendered HTML
    ├── dashboard.html            # Self-contained user dashboard
    └── admin/
        ├── base.html             # Admin layout template
        ├── dashboard.html        # Admin dashboard (Flask-rendered)
        └── login.html            # SSO login page
```

---

## File-by-File Deep Dive

---

### 1. `backend/app.py` — Application Factory

**Pattern:** Flask Application Factory — creates and configures the app instance. This is the single entry point for the entire backend.

**Technology:** Flask, Flask-CORS, Flask-Limiter, Flask-WTF (CSRFProtect), SQLAlchemy

**What it does on startup (in order):**

```
1. Load Config from .env
2. Check demo vs production mode
3. If production: validate SECRET_KEY, OIDC, and DB settings (or exit)
4. Configure session hardening (Secure, HttpOnly, SameSite, lifetime)
5. Initialize CORS (strict origins in prod, open in demo)
6. Initialize database (SQLAlchemy)
7. Initialize CSRF protection
8. Initialize rate limiter (keyed by X-Device-Id or IP)
9. Initialize OIDC SSO client (Authlib)
10. Register middleware (request_context, security_headers)
11. Register 3 blueprints (admin, tracker, public)
12. Apply rate limits to specific endpoints
13. Register error handlers (413, 429)
14. Create database tables (if not exist)
15. Run inline migrations (add missing columns)
16. Seed demo hierarchy (if demo mode)
17. Auto-cleanup old events (DATA_RETENTION_DAYS)
```

**Functions:**

| Function | Lines | What It Does |
|----------|-------|-------------|
| `create_app(config)` | 177–366 | The factory — orchestrates all initialization above. Returns the configured Flask app. |
| `_check_production_config(config)` | 49–83 | Validates production settings. **Exits the process** if SECRET_KEY is missing, no auth method is configured, or SQLite is used in prod. Provides specific fix instructions in the error message. |
| `_seed_demo_hierarchy(database)` | 86–174 | Creates a 4-team hierarchy (Engineering > Lifecad > Axion, Fast) with 4 managers (Nikhil, Wasim, Atharva, Punit) and 3 tracked users. Uses idempotent `_ensure_*` helpers — safe to run on every startup. |
| `_ensure_team(name, parent)` | 98–107 | Creates team if not exists, updates parent link if changed. |
| `_ensure_user(lan_id, email, display_name, role)` | 110–122 | Creates user if not exists, updates fields if changed. |
| `_ensure_manager(user, team)` | 125–131 | Links user to team as manager. |
| `_ensure_membership(user, team)` | 134–138 | Creates active membership for user in team. |
| `too_large(e)` | 282–290 | Error handler for 413 — logs to audit, returns JSON error. |
| `rate_limited(e)` | 292–300 | Error handler for 429 — logs to audit, returns JSON with retry info. |

**Design decisions:**
- **Why Application Factory?** Enables testing with different configs, avoids circular imports, follows Flask best practices.
- **Why inline migrations?** For schema changes that need to happen before any query runs — Alembic handles major migrations, inline handles backward-compatible column additions.
- **Why CSRF exempt on blueprints?** Admin APIs are called from Streamlit (Python HTTP client), not browser forms. The logout form has a manual CSRF token for defense-in-depth.

---

### 2. `backend/config.py` — Central Configuration

**Pattern:** Single Config class reads all 50+ settings from `.env` via `python-dotenv`. Every value has a sensible default for development.

**Technology:** python-dotenv, os.getenv

**Configuration categories:**

| Category | Variables | Example |
|----------|----------|---------|
| **Flask/DB** | `FLASK_HOST`, `FLASK_PORT`, `DATABASE_URI` | `postgresql://user:pass@localhost/db` |
| **Productivity Engine** | `BUCKET_SIZE_SEC`, `CONFIDENCE_THRESHOLD`, interaction/mouse thresholds | `60`, `0.60`, `12` |
| **Decision Tree V2** | `NON_PROD_DOMINANT_RATIO`, `MEETING_DOMINANT_RATIO`, confidence multipliers | `0.6667`, `0.50`, `0.70` |
| **Anti-Cheat** | `MIN_ZERO_SAMPLE_RATIO`, `MIN_DISTINCT_VALUES` | `0.25`, `3` |
| **App Classification** | `NON_PRODUCTIVE_APPS`, `MEETING_APPS`, `BROWSER_APPS` | Comma-separated pattern lists |
| **OIDC SSO** | `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` | Azure AD tenant URL |
| **Session Security** | `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `PERMANENT_SESSION_LIFETIME_MINUTES` | `true`, `Lax`, `30` |
| **Rate Limiting** | `RATE_LIMIT_PER_DEVICE`, `RATE_LIMIT_ADMIN_LOGIN`, `RATE_LIMIT_ADMIN_MUTATION` | `120/minute`, `5/minute`, `30/minute` |
| **CORS** | `CORS_ALLOWED_ORIGINS` | `http://localhost:8501,http://localhost:8502` |
| **Security** | `DEMO_MODE`, `SECRET_KEY`, `ADMIN_BREAK_GLASS`, `ADMIN_BREAK_GLASS_IPS` | `false`, 64-char hex, `false`, `127.0.0.1` |
| **Data Governance** | `DATA_RETENTION_DAYS`, `DROP_TITLES`, `MAX_REQUEST_SIZE_KB` | `14`, `false`, `512` |

**Key design:** `SESSION_COOKIE_SECURE` automatically defaults to `true` when `DEMO_MODE=false` — no manual configuration needed for production hardening.

---

### 3. `backend/models.py` — Database Schema (9 Models)

**Technology:** Flask-SQLAlchemy, SQLAlchemy ORM

**Entity-Relationship Overview:**

```
┌──────────┐    ┌────────────┐    ┌──────────┐
│   User   │◄───│ Membership │───▶│   Team   │
│          │    │ (active)   │    │          │
│ lan_id   │    └────────────┘    │ parent ──┼──┐ (self-referential)
│ email    │                      │          │  │
│ role     │◄───┐                 │          │◄─┘
└──────────┘    │                 └──────────┘
    ▲           │                      ▲
    │      ┌────────┐                  │
    │      │Manager │──────────────────┘
    │      └────────┘
    │
    │      ┌──────────────────┐    ┌──────────────────┐
    │      │TrackerDeviceToken│    │ TeamChangeRequest │
    │      │ token_hash       │    │ from → to team    │
    │      │ expires_at       │    │ pending/approved  │
    │      │ revoked          │    └──────────────────┘
    │      └──────────────────┘
    │
┌───┴──────────────┐    ┌─────────────┐
│ TelemetryEvent   │    │  AuditLog   │
│ (raw 1s samples) │    │ (immutable) │
│ user_id (FK→lan) │    │ actor       │
│ app_name         │    │ action      │
│ keystroke_count   │    │ request_id  │
│ mouse_clicks     │    │ ip_address  │
│ idle_seconds     │    │ user_agent  │
└──────────────────┘    └─────────────┘
```

**Models detail:**

| Model | Table | Fields | Key Relationships |
|-------|-------|--------|-------------------|
| `User` | `users` | `id`, `lan_id` (unique, indexed), `email` (indexed), `display_name`, `role` (user/manager/superadmin), `created_at`, `updated_at` | → Membership (1:many), → Manager (1:1 optional) |
| `Team` | `teams` | `id`, `name` (unique), `parent_team_id` (self-FK, indexed), `created_at` | → parent Team (self-referential), → children (backref), → Membership, → Manager |
| `Membership` | `memberships` | `id`, `user_id` (FK), `team_id` (FK), `active` (boolean), `start_at`, `end_at` | → User, → Team. **Partial unique index:** only one active membership per user (PostgreSQL `WHERE active=true`) |
| `Manager` | `managers` | `user_id` (PK, FK), `team_id` (FK) | → User, → Team. One-to-one with User. |
| `TrackerDeviceToken` | `tracker_device_tokens` | `id`, `token_hash` (SHA-256, indexed), `user_id` (FK), `team_id` (FK), `description`, `expires_at`, `revoked`, `created_at`, `rotated_from_id` (self-FK) | `is_valid()` checks revoked + expiry |
| `TeamChangeRequest` | `team_change_requests` | `id`, `user_id`, `from_team_id`, `to_team_id`, `requested_by`, `approved_by`, `status` (pending/approved/rejected), `created_at`, `resolved_at` | Tracks cross-team transfer workflow |
| `TelemetryEvent` | `telemetry_events` | `id`, `user_id` (indexed), `timestamp` (indexed), `app_name`, `window_title`, `keystroke_count`, `mouse_clicks`, `mouse_distance`, `idle_seconds`, `distraction_visible` | Raw 1-second samples. `user_id` is a string matching `User.lan_id` |
| `AuditLog` | `audit_log` | `id`, `timestamp` (indexed), `actor`, `action` (indexed), `target_user`, `ip_address`, `user_agent`, `detail`, `actor_user_id`, `actor_team_id`, `target_team_id`, `request_id` (indexed), `extra_data` (JSON Text) | Immutable. Never updated or deleted. |

---

### 4. `backend/productivity.py` — Classification Engine (Decision Tree V2)

**This is the algorithmic core of the system.** It transforms raw 1-second telemetry events into classified productivity buckets.

**Technology:** Pure Python (dataclasses, collections.Counter, datetime arithmetic). No ML libraries — deterministic rules.

**Data flow:**

```
Raw Events (1s each)
    │
    ▼
bucketize(events, cfg)
    │
    ├── Group into 60s clock-aligned buckets
    │     (anchor = epoch + idx * 60s)
    │
    ├── For each bucket:
    │     ├── Compute aggregates (keystrokes, clicks, mouse, idle)
    │     ├── Find dominant app (Counter.most_common)
    │     ├── Compute ratios (non_prod, meeting, distraction)
    │     ├── Check anti-cheat (suspicious pattern)
    │     ├── Calculate confidence score (4 params + modifiers)
    │     └── Apply 5-rule decision tree
    │
    ├── Exclude current open bucket (prevents flip-flopping)
    │
    └── Return list[Bucket]
           │
           ▼
    summarize_buckets() → totals
    app_breakdown()     → per-app time (proportional)
```

**Functions:**

| Function | Purpose | Algorithm |
|----------|---------|-----------|
| `Bucket` (dataclass) | One 60-second classified time block | Fields: `start`, `end`, `state`, `confidence`, `reason`, `total_keystrokes`, `total_clicks`, `total_mouse_distance`, `max_idle`, `dominant_app`, `dominant_title`, `event_count`, `non_prod_ratio`, `meeting_ratio`, `distraction_ratio`, `app_samples` |
| `bucketize(events, cfg)` | **Main classification function.** Groups events into clock-aligned 60s buckets and classifies each. | 1. Strip timezone from timestamps (SQLite stores naive). 2. Compute bucket index: `(ts - epoch) // bucket_size`. 3. Group events by index. 4. Skip current open bucket. 5. For each closed bucket: compute aggregates → confidence → decision tree. |
| `_confidence(keystrokes, clicks, mouse_dist, max_idle, event_count, bucket_size, cfg, ...)` | Computes confidence score [0.0 – 1.0] | `density` = (keys + clicks) / threshold, `coverage` = mouse_dist / threshold, `presence` = low-idle samples / total, `idle_penalty` = 1 - (max_idle / bucket_size). Base = avg of 4 params, capped at 1.0. Modifiers: distraction × 0.70, non-prod mix × (1 - 0.50 × ratio), suspicious × 0.30. |
| `_compute_ratios(events, cfg)` | Returns (non_prod_ratio, meeting_ratio, distraction_ratio) | Iterates events, checks each against `NON_PRODUCTIVE_APPS` and `MEETING_APPS` patterns, counts distraction flags. Returns fractions. |
| `_dominant(events)` | Returns most-frequent (app_name, window_title) pair | `Counter` on (app, title) tuples → `most_common(1)` |
| `_is_suspicious_pattern(events, cfg)` | Detects auto-clicker / key repeater bots | Checks: (1) fraction of zero-interaction samples < `MIN_ZERO_SAMPLE_RATIO` (real typing has pauses), AND (2) distinct interaction values < `MIN_DISTINCT_VALUES` (bots repeat same values). Both must trigger. |
| `_is_non_productive_event(app, title, cfg)` | True if app/title matches any `NON_PRODUCTIVE_APPS` pattern | Substring match on `(app + " " + title).lower()` |
| `_is_meeting_event(app, title, cfg)` | True if app/title matches any `MEETING_APPS` pattern | Same approach |
| `summarize_buckets(buckets)` | Returns `{productive_seconds, non_productive_seconds, total_seconds, bucket_count}` | Counts buckets by state, multiplies by `BUCKET_SIZE_SEC` |
| `app_breakdown(buckets, cfg)` | Per-app time with **proportional splitting** | For each bucket, distributes duration across all apps proportionally by sample count. Splits browser apps by website via `_extract_site_label`. Returns sorted list with productive/non-productive time per app. |
| `_is_browser(app_name, cfg)` | True if app is a web browser | Pattern match against `BROWSER_APPS` list. Short patterns (< 4 chars like "arc") require exact match to avoid false positives. |
| `_extract_site_label(window_title, cfg)` | Extracts website name from browser title | Priority: (1) match against `NON_PRODUCTIVE_APPS` → return keyword, (2) match against `MEETING_APPS` → return keyword, (3) split on delimiter (" - ", " | ") → take last segment, (4) truncate to 40 chars, (5) fallback "Other". |

**Clock-aligned bucketing (critical for data stability):**

```python
_epoch = datetime(1970, 1, 1)
idx = int((event_timestamp - _epoch).total_seconds()) // bucket_size
```

This ensures bucket boundaries are fixed to wall-clock minutes (e.g., 12:15:00–12:16:00), not relative to the first event. Once a minute has passed, its classification is **permanent** — new events arriving later cannot change it.

---

### 5. `backend/audit.py` — Audit Logging

**Technology:** SQLAlchemy (direct model insert), Flask's `request` context

| Function | Purpose |
|----------|---------|
| `log_action(actor, action, target_user=None, detail=None, actor_user_id=None, actor_team_id=None, metadata=None)` | Writes one immutable row to `audit_log`. Automatically captures: `request.remote_addr` (IP), `request.user_agent` (browser/client), `g.request_id` (UUID correlation), and serializes `metadata` to JSON. Works outside request context (for system-level actions like cleanup). |

**Actions logged:** `login`, `logout`, `delete_user`, `assign_user`, `remove_user`, `request_move`, `approve_move`, `create_token`, `revoke_token`, `idor_user_blocked`, `idor_team_blocked`, `retention_cleanup`, `request_too_large`, `rate_limited`

---

### 6. `backend/utils.py` — Shared Helpers

**Technology:** Flask, SQLAlchemy, datetime, zoneinfo

| Function | Purpose | Used By |
|----------|---------|---------|
| `get_config()` | Returns `app.tracker_config` from `current_app` | All blueprints |
| `get_local_tz(config)` | Returns `ZoneInfo` for configured timezone | Time range functions |
| `today_range(config)` | Returns `(start_of_today_utc, start_of_tomorrow_utc)` using configured timezone | Summary, leaderboard |
| `day_range(date_obj, config)` | Returns UTC range for any `date` object | Date filter in dashboards |
| `resolve_range(config)` | Parses `?date=YYYY-MM-DD` from `request.args`, defaults to today | All date-filtered endpoints |
| `base_query(start, end, user_id)` | Builds `TelemetryEvent.query.filter(timestamp >= start, timestamp < end)` with optional `user_id` filter, ordered by timestamp | All data-reading endpoints |
| `validate_event(raw)` | Validates a single telemetry event dict: type checks on all fields, range checks (≥ 0) on numeric fields, ISO 8601 on timestamp. Returns error string or `None`. | Tracker ingest |

---

### 7. `backend/auth/oidc.py` — OIDC SSO Client

**Technology:** Authlib (OAuth 2.0 / OpenID Connect library)

| Function | Purpose |
|----------|---------|
| `init_oidc(app)` | Registers the OIDC provider with Authlib's `OAuth` client. Configures: `server_metadata_url` (`.well-known/openid-configuration`), `client_id`, `client_secret`, `client_kwargs` (scopes), `redirect_uri`. Only activates if `OIDC_ISSUER_URL` is set. |
| `is_oidc_configured()` | Returns `True` if the OIDC provider was registered (i.e., `OIDC_ISSUER_URL` was non-empty at startup). Used by login page to decide between SSO redirect and local login. |
| `generate_nonce()` | Returns `secrets.token_urlsafe(32)` — a 32-byte cryptographic random nonce for OIDC `nonce` parameter. Prevents token replay attacks. |

**OIDC flow (handled in `admin.py`):**
1. `/admin/login` → generates `state` + `nonce`, stores in session, redirects to IdP
2. IdP authenticates user → redirects to `/admin/callback` with authorization code
3. Backend exchanges code for tokens → validates ID token (signature, issuer, audience, expiry, nonce)
4. Extracts `email` claim → looks up `User` → finds `Manager` record → creates session

---

### 8. `backend/auth/authz.py` — Authorization Decorators

**Technology:** Flask decorators, `flask.g`, `functools.wraps`

**This is the security enforcement layer.** Every admin endpoint is wrapped with these decorators.

| Function/Decorator | Purpose | What It Sets |
|-------------------|---------|-------------|
| `@admin_required` | **Authentication gate.** Checks session has valid manager identity. In demo mode: resolves from session/header/first Manager. In production: requires SSO session. Sets identity on `flask.g`. Aborts 401/403 if unauthorized. | `g.current_user_id`, `g.current_team_id`, `g.current_role` |
| `@team_scoped` | **Authorization gate.** Must follow `@admin_required`. Calls `get_allowed_team_ids(g.current_team_id)` to compute the full subtree. Sets allowed scope. | `g.allowed_team_ids` (set of team IDs) |
| `assert_team_in_scope(team_id)` | **IDOR guard for teams.** Checks if `team_id` is in `g.allowed_team_ids`. If not: aborts 403, writes `idor_team_blocked` audit log with actor, target, IP, User-Agent. | — |
| `assert_user_in_scope(user_id)` | **IDOR guard for users.** Looks up user's active team, checks if it's in `g.allowed_team_ids`. If not: aborts 403, writes `idor_user_blocked` audit log. | — |
| `get_current_manager()` | Returns `(user_id, team_id, role)` tuple from session. Used by `@admin_required`. | — |
| `_resolve_demo_manager()` | Demo mode only: resolves manager from session (`manager_user_id`), header (`X-Manager-User-Id`), or first Manager in DB. | — |

**Example usage in a route:**
```python
@admin_bp.route("/admin/user/<uid>", methods=["DELETE"])
@admin_required      # Step 1: Verify identity
@team_scoped         # Step 2: Compute allowed teams
def admin_delete_user(uid):
    assert_user_in_scope(uid)  # Step 3: Verify target user is in scope
    # ... delete logic ...
```

---

### 9. `backend/auth/team_hierarchy.py` — Subtree Computation

**Technology:** SQLAlchemy (recursive CTE for PostgreSQL), BFS in Python (for SQLite)

| Function | Purpose | Complexity |
|----------|---------|-----------|
| `get_allowed_team_ids(manager_team_id)` | Returns the set of all team IDs the manager can access: their own team + all descendant teams. Result is cached on `flask.g` for the duration of the request. | O(n) where n = number of teams in subtree |
| `_subtree_cte(root_id)` | **PostgreSQL path:** Uses `WITH RECURSIVE` CTE to compute the full subtree in a single SQL query. | O(1) round trip to DB |
| `_subtree_python(root_id)` | **SQLite fallback:** Loads all teams, builds adjacency list, performs BFS from root. | O(N) where N = total teams |
| `_is_postgres()` | Checks `SQLALCHEMY_DATABASE_URI` for `postgresql` prefix. | — |

**Recursive CTE (PostgreSQL):**
```sql
WITH RECURSIVE subtree AS (
    SELECT id FROM teams WHERE id = :root_id
    UNION ALL
    SELECT t.id FROM teams t JOIN subtree s ON t.parent_team_id = s.id
)
SELECT id FROM subtree;
```

---

### 10. `backend/blueprints/admin.py` — 22 Admin Endpoints

**Technology:** Flask Blueprint, SQLAlchemy, Jinja2 templates

**All endpoints are protected by `@admin_required` + `@team_scoped`.** Every mutation is audit-logged.

| Endpoint | Method | Function | Purpose |
|----------|--------|----------|---------|
| `/admin/me` | GET | `admin_me()` | Returns current manager's identity, team name, hierarchy depth, allowed team count |
| `/admin/login` | GET | `admin_login()` | In demo mode: sets session from picker. In production: redirects to IdP. |
| `/admin/callback` | GET | `admin_callback()` | OIDC callback — exchanges code, validates ID token, resolves User+Manager, creates session |
| `/admin/logout` | GET | `admin_logout()` | Clears session, audit-logs, redirects to login |
| `/admin/dashboard` | GET | `admin_dashboard()` | Renders Flask HTML dashboard with team-scoped leaderboard |
| `/admin/teams` | GET | `admin_teams()` | Returns team tree (JSON) for manager's subtree |
| `/admin/users` | GET | `admin_users()` | Lists users with active membership in allowed teams |
| `/admin/leaderboard` | GET | `admin_leaderboard()` | JSON leaderboard: per-user productive/non-productive seconds, percentages, online status |
| `/admin/user/<uid>/apps` | GET | `admin_user_app_breakdown(uid)` | Full app breakdown for user. Calls `assert_user_in_scope(uid)`. |
| `/admin/user/<uid>/non-productive-apps` | GET | `admin_user_non_productive_apps(uid)` | Non-productive app breakdown. Calls `assert_user_in_scope(uid)`. |
| `/admin/user/<uid>` | DELETE | `admin_delete_user(uid)` | Deletes all telemetry events for user. Audit-logged. |
| `/admin/tracker-status` | GET | `admin_tracker_status()` | Returns online/offline status based on last event timestamp |
| `/admin/audit-log` | GET | `admin_audit_log()` | Returns recent audit log entries |
| `/admin/users/<uid>/assign_to_my_team` | POST | `assign_user(uid)` | Assigns user to manager's team (or creates transfer request if cross-team) |
| `/admin/users/<uid>/remove_from_my_team` | POST | `remove_user(uid)` | Deactivates user's membership |
| `/admin/users/<uid>/request_move_to_my_team` | POST | `request_move(uid)` | Creates pending TeamChangeRequest |
| `/admin/team_change_requests/<id>/approve` | POST | `approve_change_request(id)` | Approves cross-team transfer |
| `/admin/device-tokens` | POST | `create_device_token()` | Creates new device token (returns plaintext once, stores SHA-256 hash) |
| `/admin/device-tokens/<id>/revoke` | POST | `revoke_device_token(id)` | Revokes device token immediately |
| `/admin/device-tokens/<id>/rotate` | POST | `rotate_device_token(id)` | Revokes old + creates new token atomically |

**Helper:**
| Function | Purpose |
|----------|---------|
| `_get_scoped_user_ids()` | Returns list of user LAN IDs that belong to `g.allowed_team_ids`. Used by leaderboard and tracker-status to filter queries. |

---

### 11. `backend/blueprints/public.py` — 7 Public Endpoints

**Technology:** Flask Blueprint, SQLAlchemy

These endpoints are **unauthenticated** — designed for Streamlit dashboards and self-service access.

| Endpoint | Method | Function | Purpose |
|----------|--------|----------|---------|
| `/summary/today` | GET | `summary_today()` | Returns `{productive_seconds, non_productive_seconds, total_seconds}` for today or `?date=`. Supports `?user_id=` filter. |
| `/apps` | GET | `apps()` | Per-app breakdown with proportional time splitting. |
| `/daily` | GET | `daily()` | Daily time-series for 7-day trend. Returns array of `{date, productive, non_productive}`. |
| `/cleanup` | POST | `cleanup()` | Manually triggers deletion of events older than retention period. |
| `/db-stats` | GET | `db_stats()` | Returns event count, date range, database size. |
| `/dashboard/<uid>` | GET | `user_dashboard(uid)` | Serves self-contained HTML dashboard. |
| `/health` | GET | `health()` | Returns `{"status": "ok"}` — used for uptime monitoring. |

**Key function:**
| Function | Purpose |
|----------|---------|
| `_bucketize_per_user(events, cfg)` | Groups events by `user_id`, runs `bucketize()` independently per user, then merges results. **Critical fix:** prevents cross-user event mixing that would inflate confidence scores. |
| `_run_cleanup(config)` | Deletes events older than `DATA_RETENTION_DAYS`. Called on startup and via `/cleanup`. Audit-logged. |

---

### 12. `backend/blueprints/tracker.py` — 2 Ingest Endpoints

**Technology:** Flask Blueprint, SQLAlchemy

| Endpoint | Method | Function | Purpose |
|----------|--------|----------|---------|
| `/track` | POST | `track()` | Legacy ingest — receives `{"events": [...]}` batch |
| `/tracker/ingest` | POST | `tracker_ingest()` | Canonical ingest — same logic, newer URL |

**Internal functions:**
| Function | Purpose |
|----------|---------|
| `_verify_tracker_auth()` | Validates `Authorization: Bearer <token>` header (SHA-256 hash lookup → check valid + not expired + not revoked) and `X-LAN-ID` header (lookup User → verify active Membership in token's team). Returns `(lan_id, None)` on success or `(None, error_response)` on failure. **Skipped in demo mode.** |
| `_ingest_events()` | Shared ingest logic: validate each event via `validate_event()`, create `TelemetryEvent` records, commit. Returns `{"ingested": count}`. Rejects invalid events individually (partial success). |

---

### 13. `backend/middleware/request_context.py` — Request Context

**Technology:** Flask `before_request` / `after_request` hooks

| Function | Purpose |
|----------|---------|
| `init_request_context(app)` | Registers hooks on the app. |
| `_set_request_context()` | **Before request:** generates `g.request_id` (UUID4), initializes `g.current_user_id`, `g.current_team_id`, `g.current_role` to None. |
| `_add_request_id(response)` | **After request:** adds `X-Request-Id` header to response for correlation. |
| `_set_rls_context(app, team_id)` | **PostgreSQL only:** executes `SET LOCAL app.user_team_id = :team_id` — enables Row-Level Security policies. |

---

### 14. `backend/middleware/security_headers.py` — Security Headers

**Technology:** Flask `after_request` hook

| Function | Purpose |
|----------|---------|
| `init_security_headers(app)` | Registers the `after_request` hook. |
| `_set_security_headers(response)` | Adds to **every response**: `Strict-Transport-Security` (HSTS, 1 year), `Content-Security-Policy` (default-src 'self'), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`. |

---

### 15. `backend/services/admin_service.py` — Business Logic

**Technology:** SQLAlchemy, backend models

**Decouples business logic from route handlers.** The admin blueprint calls these functions.

| Function | Purpose |
|----------|---------|
| `_lan_ids_for_teams(team_ids)` | Returns set of user LAN IDs with active membership in given teams. |
| `get_team_info(team_id, allowed_team_ids)` | Returns team metadata (name, parent, member count). |
| `get_team_tree(allowed_team_ids)` | Returns hierarchical team tree for the manager's subtree. |
| `list_team_users(allowed_team_ids)` | Returns list of User dicts with active membership in allowed teams. |
| `get_team_leaderboard(allowed_team_ids, config)` | **Main leaderboard function.** For each user in allowed teams: queries today's events, runs `bucketize()`, computes productive/non-productive seconds and percentages, checks online status. Returns sorted list. |
| `assign_user_to_team(user_id, team_id, actor_id)` | Assigns user to team. If user already has active membership in a different team: creates `TeamChangeRequest` instead (requires approval from the other team's manager). |
| `remove_user_from_team(user_id, team_id, actor_id)` | Sets `active=False` on membership, sets `end_at`. |
| `request_move_to_team(user_id, to_team_id, actor_id)` | Creates pending `TeamChangeRequest`. |
| `approve_team_change(request_id, approver_id, approver_allowed_team_ids)` | Approves request: deactivates old membership, creates new active membership in target team. Validates approver has scope over both teams. |

---

## Request Lifecycle (End-to-End)

```
Client Request
    │
    ▼
[1] Flask receives request
    │
    ▼
[2] request_context middleware
    ├── Generate g.request_id (UUID4)
    ├── Initialize g.current_user_id = None
    └── Set RLS context (PostgreSQL)
    │
    ▼
[3] Route matched to blueprint endpoint
    │
    ▼
[4] @admin_required decorator (admin endpoints only)
    ├── Check session for manager identity
    ├── Set g.current_user_id, g.current_team_id, g.current_role
    └── Abort 401/403 if unauthorized
    │
    ▼
[5] @team_scoped decorator (admin endpoints only)
    ├── Call get_allowed_team_ids(g.current_team_id)
    │     ├── PostgreSQL: WITH RECURSIVE CTE
    │     └── SQLite: BFS traversal
    └── Set g.allowed_team_ids
    │
    ▼
[6] Route handler executes
    ├── assert_user_in_scope() / assert_team_in_scope() on data access
    ├── Business logic (services/admin_service.py)
    ├── Database queries (models.py + SQLAlchemy)
    └── Audit logging (audit.py)
    │
    ▼
[7] security_headers middleware
    ├── Add HSTS, CSP, X-Frame-Options, etc.
    └── Add X-Request-Id header
    │
    ▼
Response sent to client
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Read-time classification** (not write-time) | Raw events stored as-is. Classification rules can be updated without reprocessing historical data. Enables A/B testing of new thresholds. |
| **Clock-aligned buckets** (not relative to first event) | Ensures bucket boundaries are fixed to wall-clock minutes. Once a minute passes, its classification is permanent — new events can't change it. |
| **Proportional app splitting** (not dominant-app-takes-all) | If 38s of YouTube and 22s of ChatGPT occur in one bucket, each app gets proportional credit. More accurate app breakdown. |
| **Per-user bucketing** (not combined) | Events from multiple users are classified independently, then merged. Prevents one user's activity from inflating another's confidence score. |
| **Exclude current open bucket** | The in-progress 60-second window is excluded from results. Prevents classification from flip-flopping as new events arrive. |
| **Hierarchical team isolation** | Managers only see their team + descendants. Prevents lateral/upward data access. Computed via recursive CTE (Postgres) or BFS (SQLite). |
| **Audit everything** | Every admin action, IDOR attempt, rate limit violation, and system cleanup is recorded with actor identity, IP, and correlation ID. |
| **Demo/Production mode gate** | `DEMO_MODE=true` disables all auth — makes development easy. `DEMO_MODE=false` enforces every security control and validates config on startup. |

---

*For the full classification engine specification, see [DECISION_TREE_V2.md](DECISION_TREE_V2.md).*
*For security controls, see [ENTERPRISE_HARDENING.md](ENTERPRISE_HARDENING.md).*
*For SSO setup, see [SSO_LOGIN_SETUP.md](SSO_LOGIN_SETUP.md).*
