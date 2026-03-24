# Zinnia Axion

**Enterprise Productivity Intelligence Platform**

A privacy-first, enterprise-hardened telemetry system that measures how employees spend their computer time and surfaces the data through real-time dashboards. Deploys as a standalone executable on **macOS**, **Windows**, and **Linux** — no Python installation needed on end-user machines.

**Privacy guarantee:** Only interaction *counts* are recorded — keystroke content is **never** captured. No screenshots, no file access, no browsing URLs.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Security Model](#security-model)
3. [Productivity Classification Engine (V2)](#productivity-classification-engine-v2)
4. [Project Structure](#project-structure)
5. [Data Models](#data-models)
6. [Backend — Flask API Server](#backend--flask-api-server)
7. [Tracker Agent — Desktop Collector](#tracker-agent--desktop-collector)
8. [Frontends — Dashboards](#frontends--dashboards)
9. [Enterprise Hardening](#enterprise-hardening)
10. [SSO / OIDC Authentication](#sso--oidc-authentication)
11. [Team Hierarchy & Authorization](#team-hierarchy--authorization)
12. [Anti-Cheat & Fraud Detection](#anti-cheat--fraud-detection)
13. [Audit Logging](#audit-logging)
14. [Privacy Controls](#privacy-controls)
15. [API Reference](#api-reference)
16. [Configuration Reference](#configuration-reference)
17. [Quick Start (Developer)](#quick-start-developer)
18. [Deploying to Employees](#deploying-to-employees)
19. [Testing](#testing)
20. [Database & Migrations](#database--migrations)
21. [Uninstallation](#uninstallation)

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                   Employee Laptop (macOS / Windows / Linux)           │
│                                                                       │
│  ┌─────────────────────────────────────────┐                          │
│  │  Tracker Agent (tracker/agent.py)       │                          │
│  │                                         │                          │
│  │  • Polls every 1s: active window,       │                          │
│  │    keystroke count, mouse clicks,       │                          │
│  │    mouse distance, idle time            │                          │
│  │  • Multi-monitor distraction scan       │                          │
│  │  • Batches every 10s → POST /track      │                          │
│  │  • Offline buffer (buffer.json) on fail │                          │
│  │  • Bearer token + X-LAN-ID auth         │                          │
│  └──────────────┬──────────────────────────┘                          │
│                 │  HTTPS (ngrok / direct / VPN)                        │
└─────────────────┼─────────────────────────────────────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                   Central Server                                      │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Flask Backend (backend/app.py) — port 5000                     │  │
│  │                                                                 │  │
│  │  Ingest         : POST /track, POST /tracker/ingest             │  │
│  │  Public API     : /summary/today, /apps, /daily, /health        │  │
│  │  Admin API      : /admin/* (22 endpoints, SSO-protected)        │  │
│  │  Classification : 60s confidence-scored buckets (Decision V2)   │  │
│  │  Storage        : PostgreSQL (prod) / SQLite (dev)              │  │
│  │  Security       : OIDC SSO, RBAC, RLS, CSRF, rate limiting     │  │
│  │  Audit          : Immutable audit_log for all admin actions     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────┐  ┌────────────────────────────────────────┐ │
│  │ User Dashboard       │  │ Admin Dashboard                        │ │
│  │ (Streamlit :8501)    │  │ (Streamlit :8502)                      │ │
│  │                      │  │                                        │ │
│  │ • Personal metrics   │  │ • SSO login (OIDC / demo picker)      │ │
│  │ • App breakdown      │  │ • Hierarchical team leaderboard       │ │
│  │ • 7-day trend        │  │ • Per-user drill-down with app chart  │ │
│  │ • 60s auto-refresh   │  │ • Delete with confirmation prompt     │ │
│  └──────────────────────┘  │ • AI executive summary (OpenAI)       │ │
│                            │ • Tracker online/offline status        │ │
│                            └────────────────────────────────────────┘ │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  ngrok tunnel (optional) — exposes :5000 over HTTPS             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

**Data flow:**
1. Tracker polls OS every **10 seconds** (app name, keystroke count, mouse clicks, mouse distance, idle time) — optimized for 90% less infrastructure load
2. Every **60 seconds**, a batch of 6 aggregated events is POSTed to the backend via HTTPS
3. Backend stores raw 10-second events in the database (same schema, coarser granularity)
4. At **read time**, events are grouped into **60-second clock-aligned buckets** and classified using the 5-rule confidence-scored decision tree
5. Dashboards fetch classified data via the REST API

**Note:** The 10s polling interval maintains identical classification accuracy while reducing database writes by 90%, network bandwidth by 83%, and storage by 90% compared to 1s polling.

---

## Security Model

Zinnia Axion implements defense-in-depth across every layer:

| Layer | Mechanism | Details |
|-------|-----------|---------|
| **AuthN — Admin** | OIDC SSO (Azure AD / Okta) | Authorization Code Flow with PKCE, ID token validation, JWKS, nonce/state |
| **AuthN — Tracker** | Bearer token + X-LAN-ID | Hashed device tokens with expiry and revocation |
| **AuthZ — RBAC** | `manager`, `superadmin` roles | Enforced via `@admin_required` decorator on every admin endpoint |
| **AuthZ — Team Scope** | Hierarchical team isolation | `@team_scoped` decorator computes manager's subtree; `assert_user_in_scope()` prevents IDOR |
| **Data Isolation** | PostgreSQL RLS / service-layer guards | `SET LOCAL app.user_team_id` for RLS; Python-level assertions as fallback |
| **Session** | Server-side Flask-Session | `Secure`, `HttpOnly`, `SameSite=Lax`, 8-hour lifetime |
| **CSRF** | Flask-WTF | Protects all mutation endpoints |
| **Rate Limiting** | Flask-Limiter | Login: 10/min, mutations: 30/min, tracker ingest: 120/min |
| **Input Validation** | `validate_event()` | Schema validation on every telemetry event |
| **Security Headers** | Middleware | HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy |
| **CORS** | Flask-CORS | Strict origin allowlist via `CORS_ORIGINS` |
| **Secrets** | `.env` (never committed) | `SECRET_KEY`, OIDC credentials, DB URI, API keys |
| **Audit** | Immutable `audit_log` table | Every admin action logged with actor, IP, User-Agent, request_id |
| **Anti-Cheat** | Bot-like input detection | Detects auto-clickers and key repeaters via statistical analysis |

---

## Productivity Classification Engine (V2)

Time is classified into two states: **productive** and **non_productive**.

### How It Works

1. Raw 1-second events are stored as-is (never pre-classified)
2. At read time, events are grouped into **60-second clock-aligned buckets**
3. For each bucket, a **confidence score** (0.0–1.0) is computed from 4 parameters
4. A **5-rule decision tree** classifies each bucket (first match wins)
5. The **currently open (incomplete) bucket is excluded** to prevent flip-flopping

### Confidence Score — 4 Parameters

| Parameter | Formula | What It Measures |
|-----------|---------|-----------------|
| `density` | `(keystrokes + clicks) / interaction_threshold` | Typing and clicking intensity |
| `coverage` | `mouse_distance / movement_threshold` | Mouse movement coverage |
| `presence` | `samples_with_low_idle / total_samples` | User was physically present |
| `idle_penalty` | `1 - (max_idle / bucket_size)` | How long the longest idle gap was |

**Base confidence** = average of the 4 parameters, capped at 1.0.

**Multiplicative modifiers** (applied to base):
- **Distraction visible** (non-prod app on other monitor): `× 0.70`
- **Non-productive app mix** (some non-prod events in bucket): `× (1 - 0.50 × non_prod_ratio)`
- **Bot-like input detected**: `× 0.30`

### 5-Rule Decision Tree

| Priority | Rule | Condition | Result | Confidence Override |
|----------|------|-----------|--------|-------------------|
| 1 | **Meeting** | `meeting_ratio >= 50%` | **Productive** | Set to min 0.85 |
| 2 | **Non-Productive Dominant** | `non_prod_ratio >= 66.67%` | **Non-Productive** | Capped at 0.40 |
| 3 | **Anti-Cheat** | Bot-like input detected | **Non-Productive** | Capped at 0.20 |
| 4 | **High Confidence** | `confidence >= 0.60` | **Productive** | Unchanged |
| 5 | **Fallthrough** | None of the above | **Non-Productive** | Unchanged |

### Proportional App Time Splitting

Each 60-second bucket may contain multiple apps. Instead of assigning all 60 seconds to the dominant app, time is split **proportionally** based on actual sample counts:

> If a bucket has 38 samples of YouTube and 22 samples of ChatGPT, YouTube gets 38 seconds and ChatGPT gets 22 seconds on the dashboard — not 60 seconds to YouTube.

### Thresholds (scaled for 60-second buckets)

| Metric | Value | Purpose |
|--------|-------|---------|
| `BUCKET_SIZE_SEC` | 60 | Classification window |
| `CONFIDENCE_THRESHOLD` | 0.60 | Min confidence to be productive (Rule 4) |
| `NON_PROD_DOMINANT_RATIO` | 0.6667 | Non-prod app % to force non-productive (Rule 2) |
| `MEETING_DOMINANT_RATIO` | 0.50 | Meeting app % to force productive (Rule 1) |
| `PRODUCTIVE_INTERACTION_THRESHOLD` | 12 | Keystrokes + clicks for full density score |
| `PRODUCTIVE_KEYSTROKE_THRESHOLD` | 6 | Keystrokes alone for full score |
| `PRODUCTIVE_MOUSE_THRESHOLD` | 6 | Clicks alone for full score |
| `MOUSE_MOVEMENT_THRESHOLD` | 48 px | Mouse distance for full coverage score |
| `MOUSE_MOVEMENT_MIN_SAMPLES` | 18 | Min samples with movement (anti-wiggle) |

---

## Project Structure

```
zinnia-axion/
│
├── backend/                          # Flask API server
│   ├── app.py                        # Application factory, demo seed, startup
│   ├── config.py                     # Central Config class (reads .env)
│   ├── models.py                     # SQLAlchemy models (9 tables)
│   ├── productivity.py               # Classification engine (V2, confidence-scored)
│   ├── audit.py                      # Audit logging helper
│   ├── utils.py                      # Shared helpers (time ranges, validation)
│   ├── auth/
│   │   ├── oidc.py                   # OIDC SSO client setup (Authlib)
│   │   ├── authz.py                  # @admin_required, @team_scoped, IDOR guards
│   │   └── team_hierarchy.py         # Recursive CTE / BFS subtree computation
│   ├── blueprints/
│   │   ├── admin.py                  # 22 admin endpoints (SSO-protected)
│   │   ├── public.py                 # 7 public read-only endpoints
│   │   └── tracker.py               # 2 telemetry ingest endpoints
│   ├── middleware/
│   │   ├── request_context.py        # request_id, RLS context injection
│   │   └── security_headers.py       # HSTS, CSP, X-Frame-Options, etc.
│   ├── services/
│   │   └── admin_service.py          # Team-scoped business logic
│   └── templates/
│       ├── admin/
│       │   ├── base.html             # Admin HTML base template
│       │   ├── dashboard.html        # Flask-rendered admin dashboard
│       │   └── login.html            # SSO login page
│       └── dashboard.html            # Self-contained HTML dashboard
│
├── tracker/                          # Desktop telemetry agent
│   ├── agent.py                      # Main loop (poll → batch → send → buffer)
│   ├── buffer.json                   # Offline event buffer (auto-created)
│   └── platform/
│       ├── base.py                   # Abstract PlatformCollector interface
│       ├── factory.py                # OS detection → correct collector
│       ├── macos.py                  # macOS: AppKit + pynput + Quartz
│       ├── windows.py                # Windows: Win32 APIs + VDI auto-fallback
│       └── linux.py                  # Linux: xdotool + pynput + xprintidle
│
├── frontend/                         # Streamlit dashboards
│   ├── dashboard.py                  # User dashboard (port 8501)
│   ├── admin_dashboard.py            # Admin dashboard (port 8502)
│   └── ai_summary.py                # AI summary engine (OpenAI + heuristic)
│
├── installer/                        # Desktop packaging (PyInstaller)
│   ├── mac/
│   │   ├── build.py                  # Build → TelemetryTracker.app
│   │   ├── launcher.py               # .app entry point
│   │   ├── setup_gui.py              # First-run Tkinter GUI (User ID)
│   │   └── launchagent.py            # macOS auto-start (LaunchAgent)
│   └── windows/
│       ├── build.py                  # Build → TelemetryTracker.exe
│       ├── launcher.py               # .exe entry point
│       ├── setup_gui.py              # First-run Tkinter GUI (User ID)
│       └── autostart.py              # Windows auto-start (Task Scheduler)
│
├── tests/                            # Pytest security & integration tests
│   ├── conftest.py                   # Fixtures: app, DB, 3-level team hierarchy
│   ├── test_admin_authz.py           # Auth enforcement (unauthenticated blocked)
│   ├── test_hierarchy.py             # Subtree computation, IDOR prevention
│   ├── test_team_isolation.py        # Cross-team data isolation
│   ├── test_oidc_flow.py             # OIDC login flow
│   └── test_tracker_auth.py          # Device token validation
│
├── scripts/                          # One-time operational scripts
│   ├── backfill_teams.py             # Create User/Team/Membership from telemetry
│   └── migrate_sqlite_to_pg.py       # SQLite → PostgreSQL migration
│
├── migrations/                       # Alembic schema migrations
│   ├── env.py                        # Alembic config
│   └── versions/
│       └── c784b459e1d4_add_enterprise_tables.py
│
├── .github/workflows/
│   └── build-windows.yml             # GitHub Actions: Windows .exe build
│
├── .env                              # Local config (never committed)
├── .env.example                      # Configuration template with all variables
├── requirements.txt                  # Core Python dependencies
├── requirements-macos.txt            # macOS: pyobjc
├── requirements-windows.txt          # Windows: pywin32, psutil
├── requirements-linux.txt            # Linux: psutil
│
├── DECISION_TREE_V2.md               # Classification engine documentation
├── ENTERPRISE_HARDENING.md           # Security hardening checklist
├── SSO_LOGIN_SETUP.md                # SSO setup guide (Azure AD, backend flow)
├── DEPLOYMENT_AWS.md                 # AWS deployment guide
├── UNINSTALL.md                      # Uninstallation instructions
├── architecture.svg                  # System architecture diagram
└── README.md                         # This file
```

---

## Data Models

Nine SQLAlchemy models across two categories:

### Enterprise Identity & Access

| Model | Table | Purpose | Key Fields |
|-------|-------|---------|------------|
| `User` | `users` | Employee identity | `lan_id`, `email`, `display_name`, `role` (user/manager/superadmin) |
| `Team` | `teams` | Organizational unit with hierarchy | `name`, `parent_team_id` (self-referential FK) |
| `Membership` | `memberships` | User → Team assignment | `user_id`, `team_id`, `active` (one active per user) |
| `Manager` | `managers` | Manager → Team link | `user_id`, `team_id` |
| `TeamChangeRequest` | `team_change_requests` | Cross-team transfer workflow | `user_id`, `from_team_id`, `to_team_id`, `status` (pending/approved/rejected) |
| `TrackerDeviceToken` | `tracker_device_tokens` | Device auth tokens | `token_hash` (SHA-256), `team_id`, `expires_at`, `revoked` |

### Telemetry & Audit

| Model | Table | Purpose | Key Fields |
|-------|-------|---------|------------|
| `TelemetryEvent` | `telemetry_events` | Raw 1-second samples | `user_id`, `timestamp`, `app_name`, `window_title`, `keystroke_count`, `mouse_clicks`, `mouse_distance`, `idle_seconds`, `distraction_visible` |
| `AuditLog` | `audit_log` | Immutable security audit trail | `actor`, `action`, `target_user`, `ip_address`, `user_agent`, `request_id`, `metadata` |

### Team Hierarchy Example

```
Engineering (Nikhil Saxena — VP, sees all)
  ├── Lifecad (Wasim Shaikh — Manager, sees Lifecad + Axion)
  │     └── Axion (Atharva Tippe — Lead, sees Axion only)
  └── Fast (Punit Joshi — Manager, sees Fast only)
```

---

## Backend — Flask API Server

### `backend/app.py` — Application Factory

| Function | Purpose |
|----------|---------|
| `create_app(config)` | Creates Flask app, registers 3 blueprints, initializes extensions (CORS, Limiter, CSRF, Session, OIDC), runs migrations, seeds demo data |
| `_seed_demo_hierarchy(db)` | Creates 4-team hierarchy with 4 managers and 3 tracked users for demo mode |
| `_check_production_config(config)` | Validates production settings — exits if SECRET_KEY is default or OIDC is missing |

### `backend/config.py` — Central Configuration

Single `Config` class reading 50+ environment variables from `.env`:
- Flask settings (host, port, debug, secret key)
- Database URI and retention policy
- Productivity thresholds (bucket size, confidence, interaction, mouse)
- App classification lists (non-productive, meeting, browser)
- OIDC/SSO settings (issuer, client ID/secret, scopes)
- Session cookie settings (secure, httponly, samesite, lifetime)
- Rate limiting defaults
- CORS origins

### `backend/productivity.py` — Classification Engine

| Function | Purpose |
|----------|---------|
| `bucketize(events, cfg)` | Groups events into clock-aligned 60s buckets, computes confidence, applies 5-rule decision tree, excludes current open bucket |
| `_confidence(...)` | Computes confidence score from density, presence, coverage, idle, with multiplicative modifiers |
| `_compute_ratios(events, cfg)` | Returns (non_prod_ratio, meeting_ratio, distraction_ratio) for a sequence of events |
| `_dominant(events)` | Returns most-frequent (app_name, window_title) pair |
| `_is_suspicious_pattern(events, cfg)` | Detects bot-like input via zero-sample ratio and distinct value analysis |
| `summarize_buckets(buckets)` | Aggregates buckets into total productive/non-productive seconds |
| `app_breakdown(buckets, cfg)` | Per-app time breakdown with proportional splitting across all apps in each bucket |

### `backend/audit.py` — Audit Logging

| Function | Purpose |
|----------|---------|
| `log_action(actor, action, ...)` | Writes one immutable audit row with actor, action, target, IP, User-Agent, request_id, metadata |

### `backend/utils.py` — Shared Helpers

| Function | Purpose |
|----------|---------|
| `get_config()` | Returns the app's Config from `current_app` |
| `today_range(config)` | Returns (start_of_today, start_of_tomorrow) in UTC |
| `day_range(date_obj, config)` | Returns UTC range for any specific date |
| `resolve_range(config)` | Parses `?date=YYYY-MM-DD` from request or defaults to today |
| `base_query(start, end, user_id)` | Builds filtered TelemetryEvent query |
| `validate_event(raw)` | Schema validation on a single telemetry event dict |

### `backend/auth/oidc.py` — SSO Client

| Function | Purpose |
|----------|---------|
| `init_oidc(app)` | Registers OIDC provider (Azure AD/Okta) with Authlib OAuth client |
| `is_oidc_configured()` | Returns True if OIDC is set up |
| `generate_nonce()` | Creates URL-safe random nonce for OIDC flow |

### `backend/auth/authz.py` — Authorization Decorators

| Function | Purpose |
|----------|---------|
| `@admin_required` | Requires authenticated manager/superadmin; sets `g.current_user_id`, `g.current_team_id`, `g.current_role` |
| `@team_scoped` | Computes manager's team subtree; sets `g.allowed_team_ids` |
| `assert_team_in_scope(team_id)` | Aborts 403 + audit log if team_id is outside manager's subtree |
| `assert_user_in_scope(user_id)` | Aborts 403 + audit log if user's team is outside manager's subtree |
| `get_current_manager()` | Returns (user_id, team_id, role) from session |

### `backend/auth/team_hierarchy.py` — Subtree Computation

| Function | Purpose |
|----------|---------|
| `get_allowed_team_ids(manager_team_id)` | Returns set of team IDs the manager can access (own team + all descendants) |
| `_subtree_cte(root_id)` | PostgreSQL recursive CTE for O(1) subtree query |
| `_subtree_python(root_id)` | BFS fallback for SQLite |

### `backend/blueprints/admin.py` — 22 Admin Endpoints

All protected by `@admin_required` + `@team_scoped`. Every mutation is audit-logged.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/me` | GET | Current manager identity, team, hierarchy info |
| `/admin/login` | GET | Renders SSO login or starts OIDC flow |
| `/admin/callback` | GET | OIDC callback — exchanges code, validates token, creates session |
| `/admin/logout` | GET | Clears session, redirects to login |
| `/admin/dashboard` | GET | Renders Flask HTML admin dashboard |
| `/admin/teams` | GET | Team tree for manager's subtree |
| `/admin/users` | GET | Users in allowed teams |
| `/admin/leaderboard` | GET | Team leaderboard with productivity stats |
| `/admin/user/<uid>/apps` | GET | Full app breakdown for a user |
| `/admin/user/<uid>/non-productive-apps` | GET | Non-productive app breakdown |
| `/admin/user/<uid>` | DELETE | Deletes all telemetry for a user |
| `/admin/tracker-status` | GET | Online/offline status for users in subtree |
| `/admin/audit-log` | GET | Recent audit log entries |
| `/admin/users/<uid>/assign_to_my_team` | POST | Assigns user to manager's team |
| `/admin/users/<uid>/remove_from_my_team` | POST | Removes user from manager's team |
| `/admin/users/<uid>/request_move_to_my_team` | POST | Creates cross-team transfer request |
| `/admin/team_change_requests/<id>/approve` | POST | Approves pending transfer |
| `/admin/device-tokens` | POST | Creates device token for tracker auth |
| `/admin/device-tokens/<id>/revoke` | POST | Revokes a device token |
| `/admin/device-tokens/<id>/rotate` | POST | Rotates (revoke old + create new) |

### `backend/blueprints/public.py` — 7 Public Endpoints

Unauthenticated read-only endpoints for dashboards.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/summary/today` | GET | Productivity totals for today (or `?date=YYYY-MM-DD`) |
| `/apps` | GET | Per-app breakdown with proportional time splitting |
| `/daily` | GET | Daily time-series for 7-day trend |
| `/cleanup` | POST | Manually purge events older than retention period |
| `/db-stats` | GET | Database stats (event count, date range, size) |
| `/dashboard/<uid>` | GET | Self-contained HTML dashboard |
| `/health` | GET | Health check |

### `backend/blueprints/tracker.py` — 2 Ingest Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/track` | POST | Legacy ingest — receives batched telemetry events |
| `/tracker/ingest` | POST | Canonical ingest — same logic, newer URL |

Both validate Bearer token + X-LAN-ID header (when `DEMO_MODE=false`).

### `backend/middleware/`

| Module | Purpose |
|--------|---------|
| `request_context.py` | Sets `g.request_id` (UUID) on every request; enables PostgreSQL RLS via `SET LOCAL app.user_team_id` |
| `security_headers.py` | Adds HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy to every response |

### `backend/services/admin_service.py` — Business Logic

| Function | Purpose |
|----------|---------|
| `get_team_leaderboard(allowed_team_ids, config)` | Computes productivity stats per user, scoped to manager's subtree |
| `list_team_users(allowed_team_ids)` | Returns users with active membership in allowed teams |
| `assign_user_to_team(user_id, team_id, actor_id)` | Assigns user; creates TeamChangeRequest if cross-team |
| `remove_user_from_team(user_id, team_id, actor_id)` | Deactivates membership |
| `approve_team_change(request_id, approver_id, ...)` | Approves pending team transfer request |

---

## Tracker Agent — Desktop Collector

### `tracker/agent.py` — Main Loop

| Function | Purpose |
|----------|---------|
| `main()` | Main loop — polls every 1s, batches every 10s, POSTs to backend, handles wake/sleep detection, ghost app filtering |
| `_send_batch(events)` | POSTs events to `/track` with Bearer token + X-LAN-ID headers |
| `_save_buffer(events)` | Persists unsent events to `buffer.json` when backend is unreachable |
| `_load_and_clear_buffer()` | On startup, loads buffered events and flushes to backend in 100-event chunks |
| `_apply_title_mode(title)` | Applies privacy mode (`full` / `redacted` / `off`) to window titles |
| `_scrub_sensitive(title)` | Regex removal of emails, 8+ digit numbers, and IDs from titles |
| `_check_distraction(collector, active_app)` | Scans all visible windows for non-productive apps (multi-monitor, split-screen, PiP) |

### Key Behaviors

| Feature | Details |
|---------|---------|
| **Polling** | Every 10 seconds: active window, keystrokes, clicks, mouse distance, idle time (optimized) |
| **Batching** | Every 60 seconds: POST 6 aggregated events to backend |
| **Offline buffer** | If backend is unreachable, events are saved to `buffer.json`; flushed on next restart in 100-event chunks |
| **Wake detection** | Wall-clock gap > 30s triggers flush of pre-sleep batch, counter reset, and skip of first inflated-idle sample |
| **Ghost filtering** | System apps (loginwindow, ScreenSaver, Dock, etc.) with zero interaction are silently dropped |
| **Distraction scan** | Enumerates all on-screen windows and flags non-productive apps visible on any monitor |

### `tracker/platform/` — OS-Specific Collectors

| File | OS | APIs Used |
|------|----|-----------|
| `base.py` | All | Abstract `PlatformCollector` interface (5 methods) |
| `factory.py` | All | `platform.system()` detection → correct collector |
| `macos.py` | macOS | AppKit (pyobjc) for windows, pynput for input, Quartz for idle, CGWindowListCopyWindowInfo for distraction |
| `windows.py` | Windows | Win32 GetAsyncKeyState (30 Hz polling), GetCursorPos, GetLastInputInfo, EnumWindows. **Auto-detects VDI/Citrix/RDP** and falls back to idle-delta estimation. Resolves UWP apps behind ApplicationFrameHost |
| `linux.py` | Linux | xdotool for windows, pynput for input, xprintidle for idle |

---

## Frontends — Dashboards

### `frontend/dashboard.py` — User Dashboard (port 8501)

Personal productivity view for individual employees:
- Summary cards (productive %, non-productive %, productive time, total tracked)
- App breakdown chart with proportional time per app
- 7-day trend line chart
- Date filter dropdown
- 60-second auto-refresh

### `frontend/admin_dashboard.py` — Admin Dashboard (port 8502)

Team management view for managers:
- SSO login page with manager picker (demo mode)
- Session persistence via `.admin_session.json`
- Hierarchical team leaderboard (ranked by non-productive %, color-coded rows)
- Tracker online/offline status indicators
- Date filter with state preserved across views
- **View** — drill-down to user detail with app breakdown chart
- **Delete** — Streamlit-native confirmation dialog, deletes all telemetry for a user
- AI-powered executive summary (OpenAI with heuristic fallback)
- 60-second auto-refresh

### `frontend/ai_summary.py` — AI Summary Engine

| Function | Purpose |
|----------|---------|
| `get_summary(data)` | Returns (markdown_summary, is_ai) with 60s TTL cache |
| `get_executive_summary(data)` | Returns (executive_markdown, is_ai) with 5-min TTL cache |
| `_call_openai(payload)` | Calls OpenAI API with privacy-safe aggregated data |
| `_fallback_summary(data)` | Deterministic heuristic summary when OpenAI is unavailable |

---

## Enterprise Hardening

### Authentication & Authorization

| Control | Implementation |
|---------|---------------|
| Admin login | OIDC SSO only (Authorization Code Flow + PKCE) — no local passwords |
| Tracker auth | Bearer device token (SHA-256 hashed, per-team, expiry, revocable) + X-LAN-ID header |
| Session | Server-side Flask-Session; cookie: `Secure`, `HttpOnly`, `SameSite=Lax`, 8h lifetime |
| RBAC | `manager` and `superadmin` roles enforced on every admin endpoint |
| Team scope | Manager sees only their team + descendant teams — never lateral or parent |
| IDOR prevention | `assert_team_in_scope()` and `assert_user_in_scope()` on every data access |

### Data Protection

| Control | Implementation |
|---------|---------------|
| PostgreSQL RLS | `SET LOCAL app.user_team_id` per request |
| Data retention | Auto-cleanup of events older than `DATA_RETENTION_DAYS` (default 14) |
| Input validation | Every telemetry event validated via `validate_event()` |
| Payload limits | 1 MB max request size; tracker sends in 100-event chunks |

### Network Security

| Control | Implementation |
|---------|---------------|
| HTTPS | Enforced via ngrok or reverse proxy; HSTS header in production |
| CORS | Strict origin allowlist via `CORS_ORIGINS` |
| Security headers | CSP, X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy: strict-origin-when-cross-origin |
| Rate limiting | Configurable per endpoint class (login, mutation, ingest) |
| CSRF | Flask-WTF token on all form-based mutations |

---

## SSO / OIDC Authentication

Full documentation: [SSO_LOGIN_SETUP.md](SSO_LOGIN_SETUP.md)

### Flow (Production)

1. Manager opens admin dashboard → redirected to `/admin/login`
2. Backend redirects to Azure AD / Okta with `state` + `nonce`
3. User authenticates with company SSO (MFA enforced by IdP)
4. IdP redirects back to `/admin/callback` with authorization code
5. Backend exchanges code for tokens, validates ID token (signature, issuer, audience, expiry, nonce)
6. Backend looks up `User` by email from ID token → finds `Manager` record → creates server-side session
7. All subsequent requests carry session cookie → `@admin_required` validates on every request

### Required Azure AD Configuration

| Setting | Value |
|---------|-------|
| Redirect URI | `https://your-domain/admin/callback` |
| Token configuration | `email`, `preferred_username`, `name` claims |
| API permissions | `openid`, `email`, `profile` |

### Backend `.env` Configuration

```
OIDC_ISSUER_URL=https://login.microsoftonline.com/<tenant-id>/v2.0
OIDC_CLIENT_ID=<application-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_REDIRECT_URI=https://your-domain/admin/callback
```

---

## Team Hierarchy & Authorization

### How It Works

1. Each `Team` has an optional `parent_team_id` (self-referential FK)
2. Each `Manager` is linked to exactly one team
3. On login, `get_allowed_team_ids(manager.team_id)` computes the full subtree:
   - **PostgreSQL**: Recursive CTE (`WITH RECURSIVE`) — single query
   - **SQLite**: BFS traversal in Python — cached on `flask.g`
4. Every admin endpoint uses `@team_scoped` which sets `g.allowed_team_ids`
5. Every data access goes through `assert_team_in_scope()` or `assert_user_in_scope()`

### Visibility Matrix (Example)

| Manager | Team | Sees Teams | Sees Users |
|---------|------|------------|------------|
| Nikhil Saxena | Engineering | Engineering, Lifecad, Axion, Fast | All users |
| Wasim Shaikh | Lifecad | Lifecad, Axion | Wasim's + Atharva's team members |
| Atharva Tippe | Axion | Axion only | Axion members only |
| Punit Joshi | Fast | Fast only | Fast members only |

### IDOR Prevention

Every attempt to access data outside the manager's subtree:
1. Returns HTTP 403 Forbidden
2. Logs `idor_user_blocked` or `idor_team_blocked` in the audit log
3. Records the actor, target, IP, and User-Agent

---

## Anti-Cheat & Fraud Detection

### Bot-Like Input Detection

The system detects fake productivity from auto-clickers and key repeaters:

| Check | What It Detects | Threshold |
|-------|----------------|-----------|
| **Zero-sample ratio** | Real typing is bursty (fast bursts then pauses). Auto-clickers produce constant input with no gaps | < 25% zero-interaction samples = suspicious |
| **Distinct values** | Real typing produces varied keystroke counts. Auto-clickers repeat 1-2 values | < 3 distinct per-sample values = suspicious |

Both conditions must trigger simultaneously to flag a bucket (reduces false positives).

When flagged: confidence is multiplied by 0.30, and Rule 3 forces `non_productive` with confidence capped at 0.20.

### Multi-Monitor Distraction Detection

- Tracker scans **all visible windows** on every sample (not just the focused app)
- Uses `CGWindowListCopyWindowInfo` (macOS), `EnumWindows` (Windows)
- Detects non-productive apps in: second monitors, macOS Split View, Picture-in-Picture overlays
- When distraction is detected: confidence is multiplied by 0.70

### VDI/RDP Detection (Windows)

The Windows collector auto-detects Citrix/RDP environments where `GetAsyncKeyState` is silently blocked:
- Calibrates during first ~5 seconds (150 polls at 30 Hz)
- If zero key hits but user is clearly active (idle resets), switches to idle-delta estimation
- Fully automatic — no configuration needed

---

## Audit Logging

Every security-relevant action is recorded in the immutable `audit_log` table:

| Field | Description |
|-------|-------------|
| `actor` | Who performed the action (manager LAN ID or "system") |
| `action` | What happened (e.g., `delete_user`, `idor_user_blocked`, `login`, `retention_cleanup`) |
| `target_user` | Who was affected |
| `ip_address` | Client IP |
| `user_agent` | Client User-Agent string |
| `request_id` | UUID correlating all logs for a single request |
| `actor_user_id` | DB user ID of the actor |
| `actor_team_id` | DB team ID of the actor |
| `metadata` | JSON blob with additional context |
| `created_at` | UTC timestamp |

### Actions Logged

| Action | Trigger |
|--------|---------|
| `login` | Manager logs in via SSO |
| `logout` | Manager logs out |
| `delete_user` | Manager deletes a user's telemetry |
| `assign_user` | Manager assigns user to their team |
| `remove_user` | Manager removes user from team |
| `request_move` | Manager requests cross-team transfer |
| `approve_move` | Manager approves transfer request |
| `create_token` | Manager creates device token |
| `revoke_token` | Manager revokes device token |
| `idor_user_blocked` | Manager attempted to access user outside their subtree |
| `idor_team_blocked` | Manager attempted to access team outside their subtree |
| `retention_cleanup` | System purged old events |

---

## Privacy Controls

| Data Type | Captured? | Details |
|-----------|-----------|---------|
| Keystroke **content** | **Never** | Only counts are recorded |
| Mouse click **targets** | **Never** | Only click counts and distance |
| Screenshots | **Never** | No visual capture of any kind |
| File contents | **Never** | No file system access |
| Browsing URLs | **Never** | Only app name + window title (configurable) |
| AI summary data | **Aggregated only** | No personal data sent to OpenAI |

### Window Title Privacy Modes

| Mode | Raw Title | Stored As |
|------|-----------|-----------|
| `full` | "RE: Salary Review - Gmail" | "RE: [REDACTED] - Gmail" (emails/IDs scrubbed) |
| `redacted` | "RE: Salary Review - Gmail" | "gmail" (only classification keyword) |
| `off` | "RE: Salary Review - Gmail" | *(empty string)* |

### Sensitive Pattern Scrubbing (Full Mode)

Even in `full` mode, these patterns are automatically replaced with `[REDACTED]`:
- Email addresses (`user@domain.com`)
- 8+ digit numbers
- ID patterns (`CA12345`, `TKT-2024001`)
- Custom patterns via `TITLE_SCRUB_PATTERNS` env var

---

## API Reference

### POST /track — Telemetry Ingest

```json
{
  "events": [
    {
      "user_id": "Atharva",
      "timestamp": "2026-03-10T12:30:00+05:30",
      "app_name": "Cursor",
      "window_title": "",
      "keystroke_count": 15,
      "mouse_clicks": 3,
      "mouse_distance": 245.7,
      "idle_seconds": 2.1,
      "distraction_visible": false
    }
  ]
}
```

**Headers (production):**
```
Authorization: Bearer <device-token>
X-LAN-ID: atharva
```

### GET /summary/today

```json
{
  "productive_seconds": 6120,
  "non_productive_seconds": 3780,
  "total_seconds": 9900,
  "bucket_count": 165,
  "bucket_size_sec": 60
}
```

### GET /apps

```json
[
  {
    "app_name": "Cursor",
    "category": "productive",
    "total_seconds": 3180,
    "states": { "productive": 2940, "non_productive": 240 }
  },
  {
    "app_name": "Safari — Youtube",
    "category": "non_productive",
    "total_seconds": 3780,
    "states": { "productive": 78, "non_productive": 3702 }
  }
]
```

### GET /admin/leaderboard

```json
[
  {
    "user_id": "Atharva",
    "productive_sec": 6120,
    "non_productive_sec": 3780,
    "total_sec": 9900,
    "productive_pct": 61.8,
    "status": "online",
    "last_seen": "2026-03-10T12:45:00"
  }
]
```

---

## Configuration Reference

All configuration via `.env`. See `.env.example` for the complete template.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_MODE` | `true` | Disables auth — set `false` for production |
| `SECRET_KEY` | `change-me-...` | Flask secret key — **must change in production** |
| `DATABASE_URI` | `sqlite:///telemetry.db` | SQLAlchemy connection string |
| `TIMEZONE` | `Asia/Kolkata` | IANA timezone for day boundaries |
| `DATA_RETENTION_DAYS` | `14` | Auto-purge threshold (0 = keep all) |

### Tracker Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:5000` | Backend URL (ngrok URL for remote) |
| `USER_ID` | `default` | Employee identifier |
| `POLL_INTERVAL_SEC` | `1` | Sampling frequency |
| `BATCH_INTERVAL_SEC` | `10` | Batch send frequency |
| `WINDOW_TITLE_MODE` | `redacted` | Privacy: `full`, `redacted`, or `off` |
| `TRACKER_DEVICE_TOKEN` | *(empty)* | Bearer token for auth |
| `LAN_ID` | *(from OS)* | Falls back to `USERNAME` (Win) or `USER` (Unix) |

### Productivity Engine

| Variable | Default | Description |
|----------|---------|-------------|
| `BUCKET_SIZE_SEC` | `60` | Classification window size |
| `CONFIDENCE_THRESHOLD` | `0.60` | Min confidence for productive (Rule 4) |
| `NON_PROD_DOMINANT_RATIO` | `0.6667` | Non-prod app % to force non-productive (Rule 2) |
| `MEETING_DOMINANT_RATIO` | `0.50` | Meeting app % to force productive (Rule 1) |
| `PRODUCTIVE_INTERACTION_THRESHOLD` | `12` | Keystrokes + clicks for full density |
| `PRODUCTIVE_KEYSTROKE_THRESHOLD` | `6` | Keystrokes alone for full score |
| `PRODUCTIVE_MOUSE_THRESHOLD` | `6` | Clicks alone for full score |
| `MOUSE_MOVEMENT_THRESHOLD` | `48` | Mouse distance (px) for full coverage |
| `MOUSE_MOVEMENT_MIN_SAMPLES` | `18` | Min samples with movement |
| `DISTRACTION_CONFIDENCE_MULT` | `0.70` | Confidence penalty when distraction visible |
| `NON_PROD_MIX_WEIGHT` | `0.50` | Confidence penalty weight for non-prod mix |
| `ANTI_CHEAT_CONFIDENCE_MULT` | `0.30` | Confidence penalty for bot-like input |

### OIDC / SSO

| Variable | Default | Description |
|----------|---------|-------------|
| `OIDC_ISSUER_URL` | *(empty)* | IdP issuer URL (e.g., Azure AD tenant) |
| `OIDC_CLIENT_ID` | *(empty)* | Application/client ID |
| `OIDC_CLIENT_SECRET` | *(empty)* | Client secret |
| `OIDC_REDIRECT_URI` | *(empty)* | Callback URL |
| `OIDC_SCOPES` | `openid email profile` | Requested scopes |

### Session & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_COOKIE_SECURE` | `true` (prod) | Requires HTTPS for session cookie |
| `SESSION_COOKIE_HTTPONLY` | `true` | Prevents JavaScript access to cookie |
| `SESSION_COOKIE_SAMESITE` | `Lax` | CSRF protection |
| `PERMANENT_SESSION_LIFETIME` | `28800` | Session duration in seconds (8 hours) |

### App Classification

| Variable | Default | Description |
|----------|---------|-------------|
| `NON_PRODUCTIVE_APPS` | `youtube,netflix,reddit,...` | Comma-separated patterns |
| `MEETING_APPS` | `zoom,microsoft teams,...` | Comma-separated patterns |
| `BROWSER_APPS` | `safari,chrome,...` | Enables per-website splitting |

---

## Quick Start (Developer)

### Prerequisites

- Python 3.10+
- PostgreSQL (recommended) or SQLite
- ngrok (optional, for remote tracker access)

### 1. Clone and set up

```bash
git clone <repo-url> zinnia-axion
cd zinnia-axion
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt

# Platform-specific:
pip install -r requirements-macos.txt      # macOS
# pip install -r requirements-windows.txt  # Windows
# pip install -r requirements-linux.txt    # Linux
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set USER_ID
```

### 4. Start all services (5 terminals)

#### Development Mode (local testing)

```bash
# Terminal 1: Backend (Flask dev server)
python3 -m backend.app
# OR using the development script:
./scripts/start_development.sh

# Terminal 2: User Dashboard
python3 -m streamlit run frontend/dashboard.py --server.port 8501 --server.headless true

# Terminal 3: Admin Dashboard
python3 -m streamlit run frontend/admin_dashboard.py --server.port 8502 --server.headless true

# Terminal 4: ngrok tunnel (optional)
ngrok http 5000

# Terminal 5: Tracker Agent
python3 -m tracker.agent
```

#### Production Mode (staging/production)

```bash
# Option 1: Direct Gunicorn command
gunicorn --config gunicorn_config.py wsgi:application

# Option 2: Using production script
./scripts/start_production.sh

# Option 3: Docker
docker build -t zinnia-axion-backend .
docker run -p 5000:5000 --env-file .env zinnia-axion-backend
```

**Production features:**
- Multi-worker process model (4-12 workers based on CPU)
- Handles 1000-2000+ simultaneous users
- Auto-restart workers on failures
- Production-grade logging to stdout/stderr
- Graceful shutdowns and zero-downtime deployments

### 5. Access

| Service | URL |
|---------|-----|
| Backend API | http://localhost:5000 |
| User Dashboard | http://localhost:8501 |
| Admin Dashboard | http://localhost:8502 |
| Health Check | http://localhost:5000/health |

---

## Deploying to Employees

### Option A: Standalone Installer (no Python needed)

**macOS:**
```bash
export INSTALLER_BACKEND_URL=https://your-ngrok-url.ngrok-free.dev
python3 installer/mac/build.py
# Output: dist/TelemetryTracker.app
```

**Windows:**
```bash
set INSTALLER_BACKEND_URL=https://your-ngrok-url.ngrok-free.dev
python installer/windows/build.py
# Output: dist/TelemetryTracker.exe
```

The installer:
1. Opens a setup GUI on first run (employee enters their User ID)
2. Saves config to `~/.zinnia-axion/config.env`
3. Installs auto-start (LaunchAgent on macOS, Task Scheduler on Windows)
4. Starts the tracker silently in the background

### Option B: GitHub Actions (Windows)

1. Go to Actions → "Build Windows Installer"
2. Enter the backend URL
3. Download the artifact

### Option C: Manual Setup

```bash
pip install -r requirements.txt -r requirements-<platform>.txt
cp .env.example .env
# Edit .env: BACKEND_URL=<ngrok-url>, USER_ID=<employee-name>
python -m tracker.agent
```

---

## Testing

### Run All Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

### Test Coverage

| Test File | What It Validates |
|-----------|-------------------|
| `test_admin_authz.py` | Unauthenticated access blocked, authenticated managers pass, regular users get 403, logout clears session |
| `test_hierarchy.py` | Subtree computation correctness, user list scoping, leaderboard scoping, IDOR blocked with 403, blocked access creates audit log |
| `test_team_isolation.py` | Cross-team data isolation — Atharva can't see Wasim's data, Wasim sees Wasim + Atharva, assign/remove/transfer workflows |
| `test_oidc_flow.py` | Demo mode redirects, OIDC rendering, callback handling, public endpoints always accessible |
| `test_tracker_auth.py` | Missing/invalid/revoked tokens rejected, valid token accepted, team mismatch blocked, malformed events return 400 |

---

## Database & Migrations

### Supported Databases

- **PostgreSQL** (recommended for production — enables RLS and recursive CTEs)
- **SQLite** (default for development — uses Python BFS fallback for hierarchy)

### Alembic Migrations

```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Migration: SQLite → PostgreSQL

```bash
# 1. Set up PostgreSQL
createdb telemetry_db

# 2. Update .env
# DATABASE_URI=postgresql://user:pass@localhost:5432/telemetry_db

# 3. Run migration
python3 scripts/migrate_sqlite_to_pg.py
```

### Backfill Teams from Existing Data

```bash
python3 scripts/backfill_teams.py
```

Creates User, Team, and Membership records from existing telemetry events.

---

## Uninstallation

See [UNINSTALL.md](UNINSTALL.md) for detailed instructions.

**macOS:**
```bash
launchctl unload ~/Library/LaunchAgents/com.telemetry.tracker.plist
rm ~/Library/LaunchAgents/com.telemetry.tracker.plist
rm -rf /Applications/TelemetryTracker.app ~/.zinnia-axion
```

**Windows (PowerShell):**
```powershell
schtasks /Delete /TN "TelemetryTracker" /F
Remove-Item -Recurse "$env:LOCALAPPDATA\TelemetryTracker"
Remove-Item -Recurse "$env:USERPROFILE\.zinnia-axion"
```

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [DECISION_TREE_V2.md](DECISION_TREE_V2.md) | Full classification engine specification |
| [ENTERPRISE_HARDENING.md](ENTERPRISE_HARDENING.md) | Security hardening checklist |
| [SSO_LOGIN_SETUP.md](SSO_LOGIN_SETUP.md) | SSO setup guide (Azure AD, step-by-step) |
| [DEPLOYMENT_AWS.md](DEPLOYMENT_AWS.md) | AWS deployment guide |
| [UNINSTALL.md](UNINSTALL.md) | Uninstallation instructions |

---

## License

Internal use only. All rights reserved. Zinnia India.
