# Zinnia Axion — System Design, Development, Testing & Deployment Document

**Version:** 1.0
**Date:** March 2026
**Classification:** Internal — Confidential
**Audience:** Engineering, Architecture Review Board, DevOps, QA, Security, Management

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context & Objectives](#2-business-context--objectives)
3. [System Architecture](#3-system-architecture)
4. [Component Design](#4-component-design)
5. [Data Model & Schema](#5-data-model--schema)
6. [Productivity Classification Engine](#6-productivity-classification-engine)
7. [Security Design](#7-security-design)
8. [Development](#8-development)
9. [Testing Strategy](#9-testing-strategy)
10. [Deployment Architecture — AWS ECS](#10-deployment-architecture--aws-ecs)
11. [Scaling Plan (10 → 50 → 100 Users)](#11-scaling-plan-10--50--100-users)
12. [Monitoring & Observability](#12-monitoring--observability)
13. [Disaster Recovery & Business Continuity](#13-disaster-recovery--business-continuity)
14. [Operational Runbook](#14-operational-runbook)
15. [Risk Register](#15-risk-register)
16. [Future Roadmap](#16-future-roadmap)
17. [Appendices](#17-appendices)

---

## 1. Executive Summary

Zinnia Axion is an enterprise workforce activity insights platform that provides managers with aggregated productivity visibility across their teams. The system consists of three components:

1. **Tracker Agent** — a lightweight desktop application (Windows/macOS/Linux) that collects activity metadata (app names, interaction counts, idle time) every 1 second and batches it to the backend every 10 seconds.
2. **Flask Backend** — a REST API server that ingests, validates, stores, and classifies telemetry data using a confidence-scored decision tree (Decision Tree V2).
3. **Streamlit Dashboards** — two web dashboards (admin + user) that display team leaderboards, app breakdowns, and 7-day trends.

**Privacy-first design:** The system never captures keystroke content, screenshots, clipboard data, URLs, or personal messages. Only interaction counts and app names are recorded.

**Deployment plan:** Backend will be deployed to **AWS ECS (Fargate)** with **RDS PostgreSQL**, scaling through three phases: 10 users (pilot), 50 users (department rollout), and 100 users (enterprise rollout).

---

## 2. Business Context & Objectives

### 2.1 Problem Statement

Traditional employee monitoring tools are either self-reported (inaccurate) or invasive (screenshots, keystroke logging). The organization needs:
- Data-driven visibility into work patterns without privacy invasion
- Support for hierarchical team structures (managers see only their teams)
- Anti-gaming capabilities (auto-clicker/jiggler detection)
- Enterprise-grade security (SSO, audit logging, RBAC)

### 2.2 Success Criteria

| Metric | Target |
|--------|--------|
| Classification accuracy | > 90% agreement with manual review |
| Data latency (tracker to dashboard) | < 90 seconds |
| System uptime | 99.5% during business hours |
| Privacy compliance | Zero content capture violations |
| Dashboard load time | < 3 seconds for team of 50 |
| Scaling | Support 100 concurrent tracked users |

### 2.3 Stakeholders

| Role | Interest |
|------|----------|
| Engineering Leadership | Architecture review, technical feasibility |
| Security Team | Auth, encryption, audit, data handling |
| Legal & Compliance | Privacy, data minimization, retention |
| HR | Employee communication, policy alignment |
| IT Operations | Deployment, monitoring, support |
| Team Managers | Dashboard usability, actionable insights |

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EMPLOYEE DEVICES                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                           │
│  │  Windows PC   │  │  macOS Mac   │  │  Linux WS    │                           │
│  │  tracker.exe  │  │  tracker.app │  │  tracker.py  │                           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                           │
│         │ 1s poll          │ 1s poll          │ 1s poll                           │
│         │ 10s batch        │ 10s batch        │ 10s batch                        │
└─────────┼──────────────────┼──────────────────┼─────────────────────────────────┘
          │                  │                  │
          │    HTTPS + Bearer Token + X-LAN-ID  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   AWS ALB       │  Application Load Balancer
                    │   (HTTPS/TLS)   │  SSL termination
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │       AWS ECS (Fargate)      │
              │  ┌────────────────────────┐  │
              │  │   Flask Backend API    │  │
              │  │   - /track (ingest)    │  │
              │  │   - /admin/* (SSO)     │  │
              │  │   - /summary/* (read)  │  │
              │  │   - /apps (breakdown)  │  │
              │  └───────────┬────────────┘  │
              │              │               │
              └──────────────┼───────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     AWS RDS PostgreSQL       │
              │     (Multi-AZ for prod)      │
              │  - telemetry_events          │
              │  - users, teams, managers    │
              │  - audit_log                 │
              │  - tracker_device_tokens     │
              └─────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   Streamlit Dashboards       │
              │   (ECS or EC2)               │
              │  - Admin (port 8501)         │
              │  - User  (port 8502)         │
              └─────────────────────────────┘
```

### 3.2 Technology Stack

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| **Language** | Python | 3.10+ | Team expertise, rapid development, rich ecosystem |
| **Web Framework** | Flask | 3.0+ | Lightweight, extensible, well-understood |
| **ORM** | Flask-SQLAlchemy | 3.1+ | Mature, supports PostgreSQL and SQLite |
| **Database** | PostgreSQL | 15+ | ACID, RLS, recursive CTEs, enterprise-grade |
| **Auth** | Authlib | 1.3+ | OIDC/OAuth2 client (Azure AD, Okta) |
| **Rate Limiting** | Flask-Limiter | 3.5+ | Per-endpoint rate throttling |
| **CSRF** | Flask-WTF | 1.2+ | Token-based CSRF protection |
| **Migrations** | Alembic | 1.13+ | Schema version control |
| **Dashboard** | Streamlit | 1.30+ | Rapid UI development, Python-native |
| **Charts** | Plotly | 5.18+ | Interactive, publication-quality visualizations |
| **Tracker (macOS)** | pyobjc | 10.0+ | Native Cocoa/Quartz APIs |
| **Tracker (Windows)** | pywin32 | 306+ | Win32 API access |
| **Packaging** | PyInstaller | 6.0+ | Standalone executables |
| **Container** | Docker + ECS Fargate | Latest | Serverless containers, no EC2 management |
| **Load Balancer** | AWS ALB | — | Path-based routing, SSL termination |
| **Database** | AWS RDS PostgreSQL | 15+ | Managed, Multi-AZ, automated backups |
| **Secrets** | AWS Secrets Manager | — | Rotation, IAM-based access |
| **Monitoring** | CloudWatch | — | Logs, metrics, alarms |

### 3.3 Network Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  VPC: 10.0.0.0/16                                    │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Public Subnets (10.0.1.0/24, 10.0.2.0/24)     │ │
│  │  ┌──────────────────────────────────────┐       │ │
│  │  │  Application Load Balancer (ALB)     │       │ │
│  │  │  - HTTPS:443 → Target Group :5000    │       │ │
│  │  │  - HTTPS:8501 → Target Group :8501   │       │ │
│  │  │  - HTTPS:8502 → Target Group :8502   │       │ │
│  │  └──────────────────────────────────────┘       │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Private Subnets (10.0.10.0/24, 10.0.20.0/24)  │ │
│  │                                                   │ │
│  │  ┌────────────────┐  ┌────────────────────────┐ │ │
│  │  │ ECS Fargate    │  │  RDS PostgreSQL        │ │ │
│  │  │ - Backend      │  │  - Multi-AZ (prod)     │ │ │
│  │  │ - Admin Dash   │  │  - Encrypted storage   │ │ │
│  │  │ - User Dash    │  │  - Automated backups   │ │ │
│  │  └────────────────┘  └────────────────────────┘ │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 3.4 Data Flow

```
1. Tracker polls OS every 1 second
   → Records: app_name, keystroke_count, mouse_clicks, mouse_distance, idle_seconds

2. Every 10 seconds, batch of 10 samples is sent:
   → POST /track (HTTPS)
   → Headers: Authorization: Bearer <token>, X-LAN-ID: <lan_id>

3. Backend receives and validates each event:
   → Type checks, range checks, timestamp validation
   → Stores raw 1-second events in telemetry_events table

4. Dashboard requests trigger read-time classification:
   → GET /summary/today, GET /apps, GET /admin/leaderboard
   → Backend groups events into 60-second clock-aligned buckets
   → Each bucket: compute confidence score → apply 5-rule decision tree
   → Return aggregated results (never raw events)

5. Audit log captures all admin actions:
   → login, logout, delete, assign, IDOR attempts, rate limits
```

---

## 4. Component Design

### 4.1 Tracker Agent (`tracker/`)

**Responsibility:** Collect activity metadata from employee devices and send to backend.

**Platform Support:**

| Platform | Collector Module | Active Window | Keystrokes | Mouse | Idle |
|----------|-----------------|---------------|------------|-------|------|
| macOS | `platform/macos.py` | NSWorkspace | pynput (counts only) | pynput | CGEventSourceSecondsSinceLastEventType |
| Windows | `platform/windows.py` | GetForegroundWindow | GetAsyncKeyState | GetCursorPos | GetLastInputInfo |
| Linux | `platform/linux.py` | xdotool | pynput | pynput | xprintidle |

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| 1-second polling | Fine-grained data for accurate confidence scoring |
| 10-second batching | Reduces network overhead while keeping latency acceptable |
| Local buffer (buffer.json) | Resilience against network failures; flushes on restart |
| VDI auto-detection (Windows) | GetAsyncKeyState fails silently in VDI; auto-switches to idle-delta |
| Ghost app filtering | Ignores loginwindow, ScreenSaver, etc. to avoid false idle classification |
| Window title redaction | Default mode strips titles to classification keywords only |

**Configuration (Environment Variables):**

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:5000` | Backend API endpoint |
| `POLL_INTERVAL_SEC` | `1` | OS polling frequency |
| `BATCH_INTERVAL_SEC` | `10` | Backend push frequency |
| `BUFFER_FILE` | `tracker/buffer.json` | Local failure buffer |
| `USER_ID` | `default` | User identifier |
| `TRACKER_DEVICE_TOKEN` | *(empty)* | Bearer token for auth |
| `LAN_ID` | Auto-detected from OS | Employee LAN username |
| `WINDOW_TITLE_MODE` | `redacted` | `full`, `redacted`, or `off` |
| `GHOST_APPS` | System apps | Apps to ignore (lock screen, etc.) |

**Deployment:** Packaged as standalone executable via PyInstaller. Distributed through enterprise MDM (Intune, JAMF). Auto-starts on login via LaunchAgent (macOS) or Task Scheduler (Windows).

### 4.2 Flask Backend (`backend/`)

**Responsibility:** Ingest, validate, store, classify, and serve telemetry data. Enforce authentication and authorization.

**Module Structure:**

| Module | Files | Responsibility |
|--------|-------|---------------|
| `app.py` | Application factory | Initialization, middleware, extensions, demo seeding |
| `config.py` | Configuration | 50+ env vars with sensible defaults |
| `models.py` | Database schema | 9 SQLAlchemy models |
| `productivity.py` | Classification engine | Decision Tree V2, confidence scoring, proportional splitting |
| `audit.py` | Audit logging | Immutable action recording |
| `utils.py` | Shared helpers | Date ranges, validation, timezone handling |
| `auth/oidc.py` | OIDC SSO client | Authlib integration for Azure AD/Okta |
| `auth/authz.py` | Authorization decorators | @admin_required, @team_scoped, IDOR guards |
| `auth/team_hierarchy.py` | Team subtree computation | Recursive CTE (PostgreSQL) / BFS (SQLite) |
| `blueprints/admin.py` | Admin API | 22 SSO-protected endpoints |
| `blueprints/public.py` | Public API | 7 read-only endpoints |
| `blueprints/tracker.py` | Ingest API | 2 telemetry endpoints |
| `middleware/request_context.py` | Request middleware | request_id, RLS context |
| `middleware/security_headers.py` | Response middleware | HSTS, CSP, X-Frame-Options |
| `services/admin_service.py` | Business logic | Leaderboard, team management, transfers |

**API Endpoints Summary:**

| Blueprint | Count | Auth | Purpose |
|-----------|-------|------|---------|
| `/admin/*` | 22 | SSO + team_scoped | Dashboard, leaderboard, user management, tokens |
| `/track`, `/tracker/ingest` | 2 | Bearer token + LAN-ID | Telemetry ingestion |
| `/summary/*`, `/apps`, `/daily` | 7 | None (demo) / Token (prod) | Dashboard data |

### 4.3 Streamlit Dashboards (`frontend/`)

**Admin Dashboard (`admin_dashboard.py`):**
- SSO login page with manager picker (demo mode)
- Team leaderboard with color-coded productivity percentages
- Per-user drill-down: app breakdown, date filter
- Delete user data with native confirmation dialog
- AI executive summary (OpenAI with heuristic fallback)
- 60-second auto-refresh

**User Dashboard (`dashboard.py`):**
- Personal productivity summary (today + selected date)
- App breakdown chart with proportional time splitting
- 7-day trend line chart
- 60-second auto-refresh

---

## 5. Data Model & Schema

### 5.1 Entity-Relationship Diagram

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
┌───┴──────────────┐    ┌──────────────────┐    ┌─────────────┐
│ TelemetryEvent   │    │TrackerDeviceToken│    │  AuditLog   │
│ (raw 1s samples) │    │ token_hash       │    │ (immutable) │
│ user_id          │    │ expires_at       │    │ actor       │
│ app_name         │    │ revoked          │    │ action      │
│ keystroke_count  │    └──────────────────┘    │ request_id  │
│ mouse_clicks     │                            └─────────────┘
│ mouse_distance   │    ┌──────────────────┐
│ idle_seconds     │    │TeamChangeRequest │
└──────────────────┘    │ from → to team   │
                        └──────────────────┘
```

### 5.2 Table Details

| Table | Est. Row Growth (100 users) | Indexes | Notes |
|-------|----------------------------|---------|-------|
| `telemetry_events` | ~2.88M rows/day (100 users × 8 hrs × 3600 samples) | `user_id`, `timestamp` | Primary data volume |
| `users` | ~150 rows (static) | `lan_id` (unique), `email` | Slowly growing |
| `teams` | ~20-50 rows (static) | `name` (unique), `parent_team_id` | Rarely changes |
| `memberships` | ~150 rows | `user_id + active` (partial unique) | One active per user |
| `managers` | ~20-50 rows | `user_id` (PK) | One-to-one with User |
| `audit_log` | ~1000 rows/day | `timestamp`, `action`, `request_id` | Immutable, no deletes |
| `tracker_device_tokens` | ~100-200 rows | `token_hash` | Low volume |

### 5.3 Storage Estimates

| Phase | Users | Events/Day | Storage/Day | 14-Day Retention |
|-------|-------|------------|-------------|------------------|
| Pilot (10) | 10 | 288,000 | ~50 MB | ~700 MB |
| Dept (50) | 50 | 1,440,000 | ~250 MB | ~3.5 GB |
| Enterprise (100) | 100 | 2,880,000 | ~500 MB | ~7 GB |

*Calculation: 100 users x 8 hours x 3600 events/hour = 2,880,000 events/day. Each event row ~180 bytes.*

### 5.4 Migrations

Schema changes are managed by **Alembic**:

```bash
# Current migrations
migrations/versions/
  c784b459e1d4_add_enterprise_tables.py   # Creates teams, users, managers, memberships,
                                           # team_change_requests, tracker_device_tokens,
                                           # extends audit_log

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

Additionally, `app.py` performs **inline migrations** on startup for backward-compatible column additions (e.g., adding `parent_team_id` to teams if missing). This handles minor schema changes without requiring a full Alembic migration.

---

## 6. Productivity Classification Engine

### 6.1 Decision Tree V2 Overview

Raw 1-second telemetry events are classified at **read time** (when dashboards request data) into 60-second clock-aligned buckets.

```
Raw Events (1s each)
    │
    ▼
Group into 60-second clock-aligned buckets
    │ anchor = epoch (1970-01-01) + idx × 60s
    │ idx = floor(seconds_since_epoch / 60)
    │
    ▼
For each closed bucket (current minute excluded):
    │
    ├── Compute aggregates (keystrokes, clicks, mouse, idle)
    ├── Find dominant app (Counter.most_common)
    ├── Compute ratios (non_prod, meeting, distraction)
    ├── Check anti-cheat (suspicious pattern)
    ├── Calculate confidence score (4 params + modifiers)
    └── Apply 5-rule decision tree
         │
         ├── Rule 1: Meeting app dominant → PRODUCTIVE
         ├── Rule 2: Non-prod ratio ≥ 0.6667 → NON-PRODUCTIVE
         ├── Rule 3: Anti-cheat triggered → NON-PRODUCTIVE
         ├── Rule 4: Confidence ≥ 0.60 → PRODUCTIVE
         └── Rule 5: Everything else → NON-PRODUCTIVE
```

### 6.2 Confidence Score Formula

```
Base Parameters:
  density  = min(1.0, (keystrokes + clicks) / INTERACTION_THRESHOLD)
  coverage = min(1.0, mouse_distance / MOUSE_THRESHOLD)
  presence = (samples with idle < threshold) / total_samples
  idle_pen = 1.0 - (max_idle / bucket_size)

base_score = average(density, coverage, presence, idle_pen)  [capped at 1.0]

Multiplicative Modifiers:
  if distraction_visible:    score *= 0.70   (DISTRACTION_CONFIDENCE_MULT)
  if non_prod apps mixed:    score *= (1.0 - 0.50 × non_prod_ratio)
  if suspicious_pattern:     score *= 0.30   (ANTI_CHEAT_CONFIDENCE_MULT)
```

### 6.3 Key Thresholds (Scaled for 60s)

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `BUCKET_SIZE_SEC` | 60 | Classification window |
| `CONFIDENCE_THRESHOLD` | 0.60 | Productive if ≥ this |
| `NON_PROD_DOMINANT_RATIO` | 0.6667 | Non-productive if ≥ 67% of bucket |
| `PRODUCTIVE_INTERACTION_THRESHOLD` | 12 | Expected interactions per 60s |
| `PRODUCTIVE_KEYSTROKE_THRESHOLD` | 6 | Expected keystrokes per 60s |
| `MOUSE_MOVEMENT_THRESHOLD` | 48 | Expected mouse pixels per 60s |

### 6.4 Clock-Aligned Bucketing (Stability)

Bucket boundaries are anchored to the Unix epoch, ensuring:
- Boundaries are fixed to wall-clock minutes (e.g., 14:32:00-14:33:00)
- Adding new events never shifts existing bucket boundaries
- Once a minute has passed, its classification is **permanent**
- The currently open (in-progress) bucket is excluded from results

### 6.5 Proportional App Time Splitting

Within each 60-second bucket, time is distributed proportionally:
- If 38 samples are VS Code and 22 samples are ChatGPT
- VS Code gets 38/60 × 60s = 38s credit
- ChatGPT gets 22/60 × 60s = 22s credit
- More accurate than dominant-app-takes-all

---

## 7. Security Design

### 7.1 Authentication

| Channel | Method | Details |
|---------|--------|---------|
| Admin Dashboard | OIDC SSO | Authorization Code Flow + PKCE. Azure AD / Okta. |
| Tracker Agent | Bearer Token + LAN-ID | SHA-256 hashed token with expiry and revocation. LAN-ID verified against membership. |
| User Dashboard | Public (demo) / Token (prod) | To be hardened in production. |

### 7.2 Authorization

- **RBAC:** `user`, `manager`, `superadmin` roles
- **Hierarchical Team Isolation:** Manager sees their team + all descendant teams
- **Subtree Computation:** PostgreSQL recursive CTE or Python BFS
- **IDOR Prevention:** `assert_user_in_scope()`, `assert_team_in_scope()` on every data access
- **Server-side enforcement:** `team_id` is never accepted from the client

### 7.3 Security Controls

| Control | Implementation |
|---------|---------------|
| Transport encryption | TLS/HTTPS via ALB |
| Session security | Server-side, Secure + HttpOnly + SameSite=Lax, 8hr lifetime |
| CSRF | Flask-WTF token on all mutations |
| Rate limiting | 120/min ingest, 5/min login, 30/min mutations |
| Security headers | HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy |
| Input validation | Schema validation on every telemetry event |
| Audit logging | 14 action types, immutable, request_id correlation |
| Anti-cheat | Bot-like input detection + multi-monitor distraction scanning |
| Data retention | Auto-purge after configurable period (default 14 days) |
| Secrets management | AWS Secrets Manager (production) |
| Row-Level Security | PostgreSQL RLS via `SET LOCAL app.user_team_id` |

### 7.4 Secret Key Management (Production)

```
Production requirement:
  - SECRET_KEY must be set (app refuses to start without it)
  - Generate: python -c "import secrets; print(secrets.token_hex(32))"
  - Store in AWS Secrets Manager, inject via ECS task definition
  - Rotate quarterly

  - OIDC_CLIENT_SECRET from Azure AD app registration
  - Store in AWS Secrets Manager
  - Never commit to version control
```

---

## 8. Development

### 8.1 Project Structure

```
zinnia-axion/
├── backend/                          # Flask API server
│   ├── app.py                        # Application factory (entry point)
│   ├── config.py                     # 50+ env vars with defaults
│   ├── models.py                     # 9 SQLAlchemy models
│   ├── productivity.py               # Decision Tree V2 engine
│   ├── audit.py                      # Immutable audit logging
│   ├── utils.py                      # Date ranges, validation
│   ├── auth/
│   │   ├── oidc.py                   # OIDC SSO client (Authlib)
│   │   ├── authz.py                  # @admin_required, @team_scoped
│   │   └── team_hierarchy.py         # Recursive CTE / BFS
│   ├── blueprints/
│   │   ├── admin.py                  # 22 SSO-protected endpoints
│   │   ├── public.py                 # 7 read-only endpoints
│   │   └── tracker.py               # 2 ingest endpoints
│   ├── middleware/
│   │   ├── request_context.py        # request_id, RLS injection
│   │   └── security_headers.py       # HSTS, CSP, X-Frame-Options
│   ├── services/
│   │   └── admin_service.py          # Business logic (leaderboard, etc.)
│   └── templates/                    # Flask-rendered HTML
├── frontend/
│   ├── admin_dashboard.py            # Streamlit admin dashboard
│   ├── dashboard.py                  # Streamlit user dashboard
│   └── ai_summary.py                # OpenAI executive summary
├── tracker/
│   ├── agent.py                      # Main agent loop
│   └── platform/                     # OS-specific collectors
│       ├── base.py                   # Abstract base class
│       ├── windows.py                # Win32 API collector
│       ├── macos.py                  # Cocoa/Quartz collector
│       └── linux.py                  # X11/xdotool collector
├── installer/
│   ├── windows/                      # PyInstaller + setup GUI
│   └── mac/                          # PyInstaller + LaunchAgent
├── migrations/                       # Alembic schema migrations
├── tests/                            # Pytest test suite
├── scripts/
│   ├── backfill_teams.py             # Populate team hierarchy
│   └── migrate_sqlite_to_pg.py       # SQLite → PostgreSQL migration
├── .github/workflows/
│   └── build-windows.yml             # GitHub Actions: build .exe
├── requirements.txt                  # Core Python dependencies
├── requirements-windows.txt          # Windows-specific deps
├── requirements-macos.txt            # macOS-specific deps
├── requirements-linux.txt            # Linux-specific deps
├── alembic.ini                       # Alembic configuration
└── .env.example                      # All config variables with docs
```

### 8.2 Dependencies

**Core (all platforms):**

| Package | Version | Purpose |
|---------|---------|---------|
| flask | >= 3.0 | REST API framework |
| flask-cors | >= 4.0 | CORS handling |
| flask-sqlalchemy | >= 3.1 | ORM |
| flask-limiter | >= 3.5 | Rate limiting |
| flask-wtf | >= 1.2 | CSRF protection |
| flask-session | >= 0.8 | Server-side sessions |
| psycopg2-binary | >= 2.9 | PostgreSQL driver |
| python-dotenv | >= 1.0 | .env loading |
| authlib | >= 1.3 | OIDC SSO client |
| marshmallow | >= 3.20 | Schema validation |
| alembic | >= 1.13 | Database migrations |
| requests | >= 2.31 | HTTP client (tracker) |
| pynput | >= 1.7 | Keyboard/mouse monitoring |
| streamlit | >= 1.30 | Dashboard framework |
| plotly | >= 5.18 | Chart rendering |
| pandas | >= 2.1 | Data manipulation |
| pytest | >= 8.0 | Testing framework |
| pytest-flask | >= 1.3 | Flask test utilities |

### 8.3 Local Development Setup

```bash
# Clone repository
git clone https://github.com/<org>/zinnia-axion.git
cd zinnia-axion

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-macos.txt    # or requirements-windows.txt

# Copy environment file
cp .env.example .env
# Edit .env: set DEMO_MODE=true for local development

# Start backend
python -m flask --app backend.app run --port 5000

# Start dashboards (separate terminals)
python3 -m streamlit run frontend/admin_dashboard.py --server.port 8501
python3 -m streamlit run frontend/dashboard.py --server.port 8502

# Start tracker (separate terminal)
python3 -m tracker.agent
```

### 8.4 Development Workflow

```
1. Feature branch from main
2. Implement changes
3. Write/update tests
4. Run pytest locally: pytest tests/ -v
5. Run linter: flake8 backend/ tracker/ frontend/
6. Create pull request
7. Code review (minimum 1 reviewer)
8. Merge to main
9. GitHub Actions builds tracker executables
10. Deploy to ECS (manual trigger or CD pipeline)
```

### 8.5 Configuration Management

All configuration is environment-variable-based (`python-dotenv`):

- **Development:** `.env` file with `DEMO_MODE=true`
- **Production:** AWS Secrets Manager + ECS task definition environment variables
- **Testing:** Overridden in `tests/conftest.py` (`DEMO_MODE=false`, in-memory SQLite)

Production startup validation (`_check_production_config`):
1. `SECRET_KEY` must be set (fatal if missing)
2. OIDC or admin password must be configured (fatal if neither)
3. Database must be PostgreSQL (fatal if SQLite)
4. Clear error messages with fix instructions

---

## 9. Testing Strategy

### 9.1 Test Architecture

```
tests/
├── conftest.py                  # Fixtures: app, client, db, seed hierarchy
├── test_admin_authz.py          # Admin authentication + authorization
├── test_tracker_auth.py         # Device token validation
├── test_team_isolation.py       # Cross-team data isolation
├── test_hierarchy.py            # Recursive subtree computation
└── test_oidc_flow.py            # OIDC SSO flow
```

### 9.2 Test Categories

| Category | Tests | What's Verified |
|----------|-------|----------------|
| **Authentication** | 8 | SSO flow, session creation, token validation, expired/revoked tokens |
| **Authorization** | 12 | @admin_required enforcement, @team_scoped, role checks |
| **Team Isolation** | 10 | Hierarchical data scoping, cross-team 403, IDOR prevention |
| **Hierarchy** | 5 | Recursive CTE, BFS fallback, subtree computation |
| **OIDC** | 8 | Login redirect, callback handling, nonce validation, user resolution |
| **Total** | **43+** | |

### 9.3 Test Configuration

```python
# tests/conftest.py (key settings)
SQLALCHEMY_DATABASE_URI = "sqlite://"     # In-memory SQLite
DEMO_MODE = False                          # Test production code paths
SECRET_KEY = "test-secret-key-for-pytest"
WTF_CSRF_ENABLED = False                   # Disable CSRF for test client
OIDC_ISSUER_URL = ""                       # Skip OIDC initialization
```

### 9.4 Test Hierarchy (Seed Data)

```
Engineering (team_n) — Manager: Nikhil Saxena
  ├── Lifecad (team_w) — Manager: Wasim Shaikh
  │     └── Axion (team_a) — Manager: Atharva Tippe
  └── Fast (team_f) — Manager: Punit Joshi
```

### 9.5 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_team_isolation.py -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html

# Run only auth tests
pytest tests/ -k "auth" -v
```

### 9.6 Test Plan for Each Scaling Phase

| Phase | Additional Testing |
|-------|-------------------|
| **10 users (pilot)** | Manual smoke tests on ECS. Verify tracker → backend → dashboard flow. Load test with 10 concurrent trackers. |
| **50 users (dept)** | Load test with 50 concurrent trackers (locust). Database query performance benchmarking. Dashboard response time under load. |
| **100 users (enterprise)** | Stress test: 100 trackers, sustained 8-hour workday simulation. RDS IOPS monitoring. ECS auto-scaling validation. Failover testing (kill tasks, verify recovery). |

---

## 10. Deployment Architecture — AWS ECS

### 10.1 Infrastructure Overview

| Component | AWS Service | Configuration |
|-----------|------------|---------------|
| **Container Orchestration** | ECS Fargate | Serverless containers, no EC2 management |
| **Load Balancer** | Application Load Balancer | SSL termination, path-based routing |
| **Database** | RDS PostgreSQL 15 | Private subnet, encrypted, automated backups |
| **Secrets** | Secrets Manager | SECRET_KEY, OIDC credentials, DB password |
| **DNS** | Route 53 | axion.company.com → ALB |
| **SSL** | ACM (Certificate Manager) | Free managed SSL certificate |
| **Logging** | CloudWatch Logs | Container logs, 30-day retention |
| **Monitoring** | CloudWatch Metrics + Alarms | CPU, memory, request count, 5xx errors |
| **Container Registry** | ECR | Private Docker image registry |

### 10.2 Dockerfile

```dockerfile
# ── Backend ──────────────────────────────────────────
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/
COPY tracker/ tracker/
COPY migrations/ migrations/
COPY wsgi.py .
COPY gunicorn_config.py .
COPY alembic.ini .
COPY .env.example .env

# Create logs directory
RUN mkdir -p logs

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Run Gunicorn
CMD ["gunicorn", "--config", "gunicorn_config.py", "wsgi:application"]
```

### 10.3 Production Server (Gunicorn)

Zinnia Axion uses **Gunicorn** (Green Unicorn) as the production WSGI server for enterprise-grade performance and reliability.

**Configuration for 1000 simultaneous users:**
- **Workers**: 8 (for 4-core ECS task)
- **Worker type**: `sync` (Flask-optimized, best for PostgreSQL I/O)
- **Max requests per worker**: 1000 (auto-restart to prevent memory leaks)
- **Timeout**: 30s (handles tracker batch uploads without timeouts)
- **Expected capacity**: 16.7 req/s × 8 workers = **133 req/s** (10x headroom)

**Key Features:**
- Multi-worker pre-fork model for concurrent request handling
- Automatic worker restarts on failures
- Graceful shutdowns and zero-downtime deployments
- Production-grade logging integrated with CloudWatch
- Configurable via environment variables (`GUNICORN_WORKERS`)

**Worker Sizing Guide:**

| User Count | ECS Task vCPUs | Workers | Expected Load | Headroom |
|------------|----------------|---------|---------------|----------|
| 100 users  | 2 vCPU         | 4       | 1.67 req/s    | 97% idle |
| 500 users  | 2 vCPU         | 4       | 8.3 req/s     | 88% idle |
| 1000 users | 4 vCPU         | 8       | 16.7 req/s    | 87% idle |
| 2000 users | 4 vCPU         | 8-12    | 33.3 req/s    | 75% idle |

With optimized tracker intervals (10s polling, 60s batching), the backend can easily handle 2000+ simultaneous users without requiring FastAPI migration.

---

**Multi-Stage Dockerfile (Optional):**

```dockerfile
# ── Admin Dashboard ──────────────────────────────────
FROM python:3.12-slim AS admin-dashboard

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ frontend/
COPY .streamlit/ .streamlit/

EXPOSE 8501
CMD ["streamlit", "run", "frontend/admin_dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]

# ── User Dashboard ───────────────────────────────────
FROM python:3.12-slim AS user-dashboard

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ frontend/
COPY .streamlit/ .streamlit/

EXPOSE 8502
CMD ["streamlit", "run", "frontend/dashboard.py", "--server.port=8502", "--server.address=0.0.0.0"]
```

### 10.4 ECS Task Definitions

**Backend Task:**

```json
{
  "family": "axion-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "backend",
    "image": "<account>.dkr.ecr.<region>.amazonaws.com/axion-backend:latest",
    "portMappings": [{"containerPort": 5000}],
    "environment": [
      {"name": "FLASK_HOST", "value": "0.0.0.0"},
      {"name": "FLASK_PORT", "value": "5000"},
      {"name": "DEMO_MODE", "value": "false"},
      {"name": "TIMEZONE", "value": "Asia/Kolkata"}
    ],
    "secrets": [
      {"name": "DATABASE_URI", "valueFrom": "arn:aws:secretsmanager:...:axion/database-uri"},
      {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:...:axion/secret-key"},
      {"name": "OIDC_CLIENT_ID", "valueFrom": "arn:aws:secretsmanager:...:axion/oidc-client-id"},
      {"name": "OIDC_CLIENT_SECRET", "valueFrom": "arn:aws:secretsmanager:...:axion/oidc-client-secret"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/axion-backend",
        "awslogs-region": "<region>",
        "awslogs-stream-prefix": "backend"
      }
    }
  }]
}
```

### 10.4 ALB Routing Rules

| Rule | Condition | Target Group | Port |
|------|-----------|-------------|------|
| 1 | Path: `/admin/*`, `/track`, `/tracker/*`, `/summary/*`, `/apps`, `/daily`, `/health` | backend-tg | 5000 |
| 2 | Path: `/admin-dashboard/*` or Host: `admin.axion.company.com` | admin-dash-tg | 8501 |
| 3 | Default | user-dash-tg | 8502 |

### 10.5 Deployment Steps

```bash
# 1. Build and push Docker images
docker build --target backend -t axion-backend .
docker tag axion-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/axion-backend:latest
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker push <account>.dkr.ecr.<region>.amazonaws.com/axion-backend:latest

# 2. Create/update ECS service
aws ecs update-service --cluster axion-cluster --service axion-backend --force-new-deployment

# 3. Run database migrations
aws ecs run-task --cluster axion-cluster --task-definition axion-migrate --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"

# 4. Verify health
curl https://axion.company.com/health
# Expected: {"status": "ok"}

# 5. Verify tracker connectivity
curl -X POST https://axion.company.com/track \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -H "X-LAN-ID: test-user" \
  -d '{"events": [{"timestamp": "2026-03-04T10:00:00Z", "app_name": "test", "keystroke_count": 0, "mouse_clicks": 0, "mouse_distance": 0, "idle_seconds": 0}]}'
```

---

## 11. Scaling Plan (10 → 50 → 100 Users)

### 11.1 Phase 1: Pilot (10 Users)

**Timeline:** Week 1-2
**Objective:** Validate end-to-end flow, gather feedback

| Component | Configuration | Est. Cost/Month |
|-----------|--------------|-----------------|
| ECS Backend | 1 task, 0.5 vCPU, 1 GB RAM | ~$15 |
| ECS Admin Dashboard | 1 task, 0.25 vCPU, 0.5 GB RAM | ~$8 |
| ECS User Dashboard | 1 task, 0.25 vCPU, 0.5 GB RAM | ~$8 |
| RDS PostgreSQL | db.t3.micro, 20 GB, Single-AZ | ~$15 |
| ALB | 1 ALB | ~$22 |
| ECR | 3 images | ~$1 |
| CloudWatch | Basic | ~$5 |
| **Total** | | **~$74/month** |

**Data volume:** ~288K events/day, ~50 MB/day, ~700 MB at 14-day retention

**Checklist:**
- [ ] Deploy backend to ECS Fargate
- [ ] Set up RDS PostgreSQL (single-AZ is fine for pilot)
- [ ] Configure ALB with SSL certificate
- [ ] Store secrets in Secrets Manager
- [ ] Deploy tracker to 10 pilot devices via MDM
- [ ] Configure OIDC SSO with Azure AD
- [ ] Set up CloudWatch log groups
- [ ] Verify classification accuracy with pilot users
- [ ] Collect feedback on dashboard usability

### 11.2 Phase 2: Department Rollout (50 Users)

**Timeline:** Week 3-6
**Objective:** Scale to full department, performance tuning

| Component | Configuration | Est. Cost/Month |
|-----------|--------------|-----------------|
| ECS Backend | 2 tasks, 0.5 vCPU, 1 GB RAM each | ~$30 |
| ECS Admin Dashboard | 1 task, 0.5 vCPU, 1 GB RAM | ~$15 |
| ECS User Dashboard | 1 task, 0.5 vCPU, 1 GB RAM | ~$15 |
| RDS PostgreSQL | db.t3.small, 50 GB, Single-AZ | ~$30 |
| ALB | 1 ALB | ~$25 |
| ECR | 3 images | ~$1 |
| CloudWatch | Enhanced | ~$10 |
| **Total** | | **~$126/month** |

**Data volume:** ~1.44M events/day, ~250 MB/day, ~3.5 GB at 14-day retention

**Changes from Phase 1:**
- [ ] Scale backend to 2 Fargate tasks (ALB distributes load)
- [ ] Upgrade RDS to db.t3.small (2 vCPU, 2 GB RAM)
- [ ] Add database connection pooling (SQLAlchemy pool_size=10)
- [ ] Add CloudWatch alarms: CPU > 80%, 5xx > 10/min, latency > 2s
- [ ] Optimize database indexes (EXPLAIN ANALYZE slow queries)
- [ ] Run load test: 50 concurrent trackers for 8 hours
- [ ] Verify dashboard loads in < 3 seconds
- [ ] Set up auto-scaling policy (target CPU 70%)

### 11.3 Phase 3: Enterprise Rollout (100 Users)

**Timeline:** Week 7-12
**Objective:** Full production with high availability

| Component | Configuration | Est. Cost/Month |
|-----------|--------------|-----------------|
| ECS Backend | 2-4 tasks (auto-scaling), 1 vCPU, 2 GB RAM each | ~$80 |
| ECS Admin Dashboard | 2 tasks, 0.5 vCPU, 1 GB RAM | ~$30 |
| ECS User Dashboard | 2 tasks, 0.5 vCPU, 1 GB RAM | ~$30 |
| RDS PostgreSQL | db.t3.medium, 100 GB, **Multi-AZ** | ~$90 |
| ALB | 1 ALB | ~$30 |
| ECR | 3 images | ~$2 |
| CloudWatch + SNS | Full monitoring + alerts | ~$20 |
| Secrets Manager | 5 secrets | ~$3 |
| **Total** | | **~$285/month** |

**Data volume:** ~2.88M events/day, ~500 MB/day, ~7 GB at 14-day retention

**Changes from Phase 2:**
- [ ] Enable RDS **Multi-AZ** for automatic failover
- [ ] Enable RDS **automated backups** (7-day retention)
- [ ] Scale backend auto-scaling: min=2, max=4, target CPU=70%
- [ ] Scale dashboard tasks to 2 each (HA)
- [ ] Enable RDS **Performance Insights** for query analysis
- [ ] Set up WAF on ALB (optional: IP whitelist for tracker endpoints)
- [ ] Run full stress test: 100 trackers, 8-hour simulation
- [ ] Document runbook for on-call team
- [ ] Set up SNS alerts → Slack/email for critical alarms
- [ ] Enable PostgreSQL RLS for defense-in-depth

### 11.4 Scaling Comparison Table

| Metric | 10 Users | 50 Users | 100 Users |
|--------|----------|----------|-----------|
| Backend tasks | 1 | 2 | 2-4 (auto) |
| Dashboard tasks | 2 (1 each) | 2 (1 each) | 4 (2 each) |
| RDS instance | db.t3.micro | db.t3.small | db.t3.medium |
| RDS Multi-AZ | No | No | **Yes** |
| Storage (14-day) | 700 MB | 3.5 GB | 7 GB |
| Events/day | 288K | 1.44M | 2.88M |
| Ingest req/sec (peak) | ~3 | ~14 | ~28 |
| Est. cost/month | $74 | $126 | $285 |
| Auto-scaling | No | Basic | Full |
| Monitoring | Basic | Enhanced | Full + alerts |

---

## 12. Monitoring & Observability

### 12.1 Health Check

```
GET /health → {"status": "ok"}

ALB health check: /health, interval 30s, threshold 3, timeout 5s
```

### 12.2 CloudWatch Metrics

| Metric | Source | Alarm Threshold |
|--------|--------|----------------|
| CPU utilization | ECS | > 80% for 5 min |
| Memory utilization | ECS | > 85% for 5 min |
| Running task count | ECS | < desired count for 2 min |
| ALB 5xx count | ALB | > 10 in 5 min |
| ALB target response time | ALB | > 2 seconds (p95) |
| RDS CPU | RDS | > 80% for 10 min |
| RDS free storage | RDS | < 2 GB |
| RDS connections | RDS | > 80% of max |
| RDS read IOPS | RDS | > 3000 for 10 min |

### 12.3 Application Logging

All Flask logs are sent to CloudWatch Logs via the `awslogs` driver:

```
Log Groups:
  /ecs/axion-backend         — Backend API logs
  /ecs/axion-admin-dashboard — Admin dashboard logs
  /ecs/axion-user-dashboard  — User dashboard logs

Key log events to monitor:
  - "PRODUCTION MODE STARTUP FAILED" → deployment config error
  - "idor_user_blocked" or "idor_team_blocked" → security event
  - "rate_limited" → potential abuse
  - "request_too_large" → payload issue
  - "retention_cleanup" → data purge completed
```

### 12.4 Audit Log Queries

```sql
-- Recent IDOR attempts (security incidents)
SELECT * FROM audit_log
WHERE action IN ('idor_user_blocked', 'idor_team_blocked')
ORDER BY timestamp DESC LIMIT 50;

-- Login activity for a specific manager
SELECT * FROM audit_log
WHERE actor = 'wasim' AND action IN ('login', 'logout')
ORDER BY timestamp DESC;

-- All actions in a specific request (correlation)
SELECT * FROM audit_log
WHERE request_id = 'abc123-def456'
ORDER BY timestamp;
```

---

## 13. Disaster Recovery & Business Continuity

### 13.1 Recovery Objectives

| Metric | Target |
|--------|--------|
| **RTO** (Recovery Time Objective) | 30 minutes |
| **RPO** (Recovery Point Objective) | 1 hour (automated backups) |

### 13.2 Failure Scenarios

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Single ECS task crash | Minimal (ALB routes to healthy tasks) | ECS auto-restarts task in ~60 seconds |
| All backend tasks down | Dashboard shows stale data; trackers buffer locally | ECS restarts tasks; trackers flush buffer on reconnect |
| RDS failure (single-AZ) | Full outage | Manual restore from snapshot (~15 min) |
| RDS failure (Multi-AZ) | Brief (< 2 min) outage | Automatic failover to standby |
| Region failure | Full outage | Restore from cross-region backup (manual) |
| Tracker agent crash | No data loss | Agent auto-restarts via LaunchAgent/TaskScheduler |
| Network failure (tracker) | Events buffer locally | buffer.json holds data; flushes on reconnect (100-event chunks) |

### 13.3 Backup Strategy

| Data | Backup Method | Retention | Frequency |
|------|--------------|-----------|-----------|
| RDS PostgreSQL | Automated snapshots | 7 days | Daily |
| RDS PostgreSQL | Point-in-time recovery | 7 days | Continuous (WAL) |
| Docker images | ECR image tags | Indefinite | Per deployment |
| Configuration | Git repository | Indefinite | Per change |
| Secrets | Secrets Manager (versioned) | 30 days | Per rotation |

---

## 14. Operational Runbook

### 14.1 Deploy New Version

```bash
# 1. Build and push new image
docker build --target backend -t axion-backend:v1.2.0 .
docker tag axion-backend:v1.2.0 <account>.dkr.ecr.<region>.amazonaws.com/axion-backend:v1.2.0
docker push <account>.dkr.ecr.<region>.amazonaws.com/axion-backend:v1.2.0

# 2. Update ECS service (rolling deployment)
aws ecs update-service --cluster axion-cluster --service axion-backend \
  --task-definition axion-backend:v1.2.0 --force-new-deployment

# 3. Monitor rollout
aws ecs describe-services --cluster axion-cluster --services axion-backend \
  --query 'services[0].deployments'

# 4. Verify
curl https://axion.company.com/health
```

### 14.2 Database Migration

```bash
# Run as one-off ECS task
aws ecs run-task --cluster axion-cluster --task-definition axion-migrate \
  --launch-type FARGATE \
  --overrides '{"containerOverrides":[{"name":"migrate","command":["alembic","upgrade","head"]}]}' \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}"
```

### 14.3 Rotate SECRET_KEY

```bash
# 1. Generate new key
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Update in Secrets Manager
aws secretsmanager update-secret --secret-id axion/secret-key --secret-string "<new-key>"

# 3. Force ECS redeployment (picks up new secret)
aws ecs update-service --cluster axion-cluster --service axion-backend --force-new-deployment

# Note: Active sessions will be invalidated. Managers will need to re-login.
```

### 14.4 Scale Up Manually

```bash
# Scale backend to 4 tasks
aws ecs update-service --cluster axion-cluster --service axion-backend --desired-count 4
```

### 14.5 View Logs

```bash
# Tail backend logs
aws logs tail /ecs/axion-backend --follow

# Search for errors
aws logs filter-log-events --log-group-name /ecs/axion-backend \
  --filter-pattern "ERROR" --start-time $(date -d '1 hour ago' +%s000)

# Search for IDOR attempts
aws logs filter-log-events --log-group-name /ecs/axion-backend \
  --filter-pattern "idor" --start-time $(date -d '24 hours ago' +%s000)
```

### 14.6 Emergency: Restore Database

```bash
# 1. Find latest snapshot
aws rds describe-db-snapshots --db-instance-identifier axion-db \
  --query 'DBSnapshots | sort_by(@, &SnapshotCreateTime) | [-1]'

# 2. Restore to new instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier axion-db-restored \
  --db-snapshot-identifier <snapshot-id> \
  --db-instance-class db.t3.medium

# 3. Update DATABASE_URI in Secrets Manager to point to restored instance
# 4. Force ECS redeployment
```

---

## 15. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|------------|
| R1 | Tracker causes performance issues on employee devices | Medium | High | Lightweight design (< 1% CPU). Monitor with employee feedback. Kill switch via MDM. |
| R2 | Database storage grows unexpectedly | Low | Medium | 14-day auto-retention. CloudWatch alarm on free storage. Increase retention delete frequency if needed. |
| R3 | Employee circumvents tracker | Medium | Low | Anti-cheat detection (bot patterns). Process presence verification. This is a deterrent, not a DRM system. |
| R4 | SSO provider outage (Azure AD) | Low | High | Break-glass admin login (disabled by default, IP-restricted). Cache last-known session for 30 min. |
| R5 | Data breach (unauthorized access) | Low | Critical | Encryption in transit + at rest. RLS. Audit logging. VPC private subnets. Secrets Manager. |
| R6 | False productivity classification | Medium | Medium | Confidence scoring reduces false positives. Manual review of borderline buckets. Threshold tuning. |
| R7 | Regulatory compliance issue | Low | High | Privacy-by-design. No content capture. Configurable retention. Right to deletion. Legal review before enterprise rollout. |
| R8 | ECS task instability | Low | Medium | Health checks. Auto-restart. Multi-task deployment. ALB distributes load. |
| R9 | Cost overrun | Low | Low | Start small (Phase 1: $74/month). Scale incrementally. Fargate = pay per use. |
| R10 | Key personnel dependency | Medium | Medium | Comprehensive documentation (this document). Code review practices. No single point of knowledge. |

---

## 16. Future Roadmap

### 16.1 Near-Term (Q2 2026)

- [ ] Dockerize all three services
- [ ] Deploy Phase 1 (10 users) to AWS ECS
- [ ] Set up CI/CD pipeline (GitHub Actions → ECR → ECS)
- [ ] Add SAST scanning (Bandit for Python)
- [ ] Code-sign tracker executables (Apple + Microsoft certificates)

### 16.2 Mid-Term (Q3 2026)

- [ ] Deploy Phase 2 (50 users)
- [ ] Add auto-scaling policies
- [ ] Implement real-time alerting (IDOR attempts → Slack)
- [ ] Add user dashboard authentication (token-based)
- [ ] Build CSV/PDF export for compliance reports
- [ ] Azure AD group sync for automatic team assignment

### 16.3 Long-Term (Q4 2026+)

- [ ] Deploy Phase 3 (100 users)
- [ ] Enable Multi-AZ RDS
- [ ] Add auto-update mechanism for tracker agents
- [ ] Build manager-facing mobile dashboard
- [ ] Implement anomaly detection (unusual work patterns)
- [ ] Add data anonymization option for aggregate-only reporting
- [ ] Evaluate migration to AWS Aurora for higher throughput
- [ ] Multi-region deployment for global teams

---

## 17. Appendices

### Appendix A: Environment Variables Reference

| Variable | Required | Default | Phase |
|----------|----------|---------|-------|
| `DATABASE_URI` | Yes (prod) | `sqlite:///telemetry.db` | All |
| `SECRET_KEY` | Yes (prod) | *(empty)* | All |
| `DEMO_MODE` | No | `true` | All |
| `FLASK_HOST` | No | `127.0.0.1` | All |
| `FLASK_PORT` | No | `5000` | All |
| `OIDC_ISSUER_URL` | Yes (prod) | *(empty)* | Phase 1+ |
| `OIDC_CLIENT_ID` | Yes (prod) | *(empty)* | Phase 1+ |
| `OIDC_CLIENT_SECRET` | Yes (prod) | *(empty)* | Phase 1+ |
| `OIDC_REDIRECT_URI` | Yes (prod) | `http://localhost:5000/admin/callback` | Phase 1+ |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost:8501,http://localhost:8502` | All |
| `TIMEZONE` | No | `UTC` | All |
| `BUCKET_SIZE_SEC` | No | `60` | All |
| `CONFIDENCE_THRESHOLD` | No | `0.60` | All |
| `DATA_RETENTION_DAYS` | No | `14` | All |
| `RATE_LIMIT_PER_DEVICE` | No | `120/minute` | All |
| `SESSION_COOKIE_SECURE` | Auto | `true` when `DEMO_MODE=false` | All |
| `ADMIN_BREAK_GLASS` | No | `false` | Phase 2+ |
| `ADMIN_BREAK_GLASS_IPS` | No | `127.0.0.1` | Phase 2+ |

### Appendix B: AWS Resource Naming Convention

```
Cluster:        axion-cluster
Services:       axion-backend, axion-admin-dashboard, axion-user-dashboard
Task Defs:      axion-backend, axion-admin-dashboard, axion-user-dashboard, axion-migrate
ECR Repos:      axion-backend, axion-admin-dashboard, axion-user-dashboard
RDS Instance:   axion-db
Secrets:        axion/database-uri, axion/secret-key, axion/oidc-client-id, axion/oidc-client-secret
ALB:            axion-alb
Target Groups:  axion-backend-tg, axion-admin-tg, axion-user-tg
Log Groups:     /ecs/axion-backend, /ecs/axion-admin-dashboard, /ecs/axion-user-dashboard
VPC:            axion-vpc
Subnets:        axion-public-1, axion-public-2, axion-private-1, axion-private-2
Security Groups: axion-alb-sg, axion-ecs-sg, axion-rds-sg
```

### Appendix C: Security Checklist (Pre-Production)

- [ ] `DEMO_MODE=false` in all production environments
- [ ] `SECRET_KEY` generated and stored in Secrets Manager
- [ ] OIDC SSO configured with Azure AD
- [ ] PostgreSQL (not SQLite) as database
- [ ] RDS in private subnet (no public access)
- [ ] ALB with SSL certificate (ACM)
- [ ] CORS restricted to dashboard origins only
- [ ] Rate limiting enabled on all endpoints
- [ ] Security headers verified (HSTS, CSP, X-Frame-Options)
- [ ] Audit logging verified (login, IDOR, admin actions)
- [ ] Data retention policy configured
- [ ] Tracker device tokens generated and distributed
- [ ] Break-glass admin reviewed and IP-restricted
- [ ] All 43+ security tests passing
- [ ] No secrets in version control (git history audit)
- [ ] Tracker executables code-signed

### Appendix D: Glossary

| Term | Definition |
|------|-----------|
| **ECS Fargate** | AWS serverless container platform; runs containers without managing EC2 instances |
| **ALB** | Application Load Balancer; distributes incoming traffic across multiple targets |
| **RDS** | Relational Database Service; managed PostgreSQL with automated backups |
| **Multi-AZ** | RDS deployment across two availability zones for automatic failover |
| **ECR** | Elastic Container Registry; private Docker image storage |
| **ACM** | AWS Certificate Manager; free managed SSL/TLS certificates |
| **OIDC** | OpenID Connect; industry standard for Single Sign-On |
| **RLS** | Row-Level Security; PostgreSQL feature restricting data visibility per connection |
| **IDOR** | Insecure Direct Object Reference; an access control vulnerability |
| **CTE** | Common Table Expression; SQL feature for recursive queries |
| **Gunicorn** | Production-grade Python WSGI HTTP server |
| **MDM** | Mobile Device Management; enterprise tool for deploying software (Intune, JAMF) |

---

*Document prepared: March 2026*
*Next review: Before each scaling phase transition*
*Owner: Engineering Team*
