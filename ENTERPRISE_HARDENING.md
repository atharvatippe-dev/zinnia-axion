# Enterprise Hardening v2 — Implementation Status

This document describes the security hardening applied to Zinnia Axion for enterprise deployments. All features listed here are **implemented** and verified by automated tests.

---

## Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │         Identity Provider            │
                    │    (Azure AD / Okta / OIDC IdP)      │
                    └────────────────┬────────────────────┘
                                     │ OIDC auth code flow
                    ┌────────────────▼────────────────────┐
                    │        Flask Backend (:5000)         │
                    │                                      │
                    │  Blueprints:                         │
                    │    admin_bp   — SSO + team dashboard │
                    │    tracker_bp — device-auth ingest   │
                    │    public_bp  — health, summaries    │
                    │                                      │
                    │  Middleware:                          │
                    │    request_context (UUID, RLS)       │
                    │    security_headers (HSTS, CSP)      │
                    │    CSRF (Flask-WTF)                  │
                    │    rate limiting (Flask-Limiter)      │
                    └───┬─────────────────────┬───────────┘
                        │                     │
            ┌───────────▼──────┐    ┌─────────▼──────────┐
            │   PostgreSQL     │    │  Tracker Agents     │
            │  (with RLS)      │    │  (desktop .exe)     │
            │                  │    │  Bearer token +     │
            │  users           │    │  X-LAN-ID header    │
            │  teams           │    └────────────────────┘
            │  memberships     │
            │  managers        │
            │  telemetry       │
            │  audit_log       │
            └──────────────────┘
```

---

## Section 1: Admin Authentication — OIDC SSO

**Status: IMPLEMENTED**

### What was done
- Added OIDC SSO login using **Authlib** (`backend/auth/oidc.py`).
- `GET /admin/login` starts the OIDC authorization code flow.
- `GET /admin/callback` handles code exchange, validates the id_token (issuer, audience, signature via JWKS, exp/nbf, nonce/state).
- On successful auth, resolves the manager's identity (email/UPN/sub), looks up the internal `User` record, verifies `role` is `manager` or `superadmin`, resolves `team_id` from the `Manager` table, and stores `user_id`, `team_id`, `role` in a server-side session.

### Files
- `backend/auth/oidc.py` — OIDC client config, discovery, nonce generation
- `backend/blueprints/admin.py` — `/admin/login`, `/admin/callback`, `/admin/logout`

### Config variables
| Variable | Purpose |
|----------|---------|
| `OIDC_ISSUER_URL` | IdP discovery URL (e.g., `https://login.microsoftonline.com/{tenant}/v2.0`) |
| `OIDC_CLIENT_ID` | OAuth client ID |
| `OIDC_CLIENT_SECRET` | OAuth client secret |
| `OIDC_REDIRECT_URI` | Callback URL (`http://localhost:5000/admin/callback`) |
| `OIDC_SCOPES` | Scopes (default: `openid profile email`) |

---

## Section 2: Team-Scoped Authorization

**Status: IMPLEMENTED**

### What was done
- `@admin_required` decorator — verifies session contains a valid manager/superadmin user.
- `@team_scoped` decorator — injects `g.current_team_id` from session, enforces URL team_id matches session.
- All admin endpoints derive `team_id` from the session. **Client-provided team_id is never trusted.**
- IDOR protection: accessing another team's user data returns 403 + audit log entry.

### Files
- `backend/auth/authz.py` — decorators and `get_current_manager()` helper
- `backend/blueprints/admin.py` — all routes decorated with `@admin_required` + `@team_scoped`
- `backend/services/admin_service.py` — every function requires `team_id` parameter

### Key behaviors
- Manager A cannot see Manager B's team users (leaderboard, user list, app breakdown).
- Manager A cannot delete telemetry for users in Manager B's team.
- URL manipulation (passing different user_id or team_id) is blocked server-side.
- All blocked attempts are audit-logged.

---

## Section 3: Team Membership Management

**Status: IMPLEMENTED**

### Data model
- **`users`** — `id`, `lan_id` (UNIQUE), `email`, `display_name`, `role`, `created_at`, `updated_at`
- **`teams`** — `id`, `name` (UNIQUE), `created_at`
- **`memberships`** — `id`, `user_id` FK, `team_id` FK, `active`, `start_at`, `end_at`
  - Partial unique index: only one active membership per user (Postgres)
- **`managers`** — `user_id` FK (PK), `team_id` FK — one team per manager

### Admin portal functionality
| Action | Endpoint | Behavior |
|--------|----------|----------|
| List team users | `GET /admin/users` | Returns only manager's team members |
| Assign user | `POST /admin/users/<id>/assign_to_my_team` | Direct if user has no team; creates transfer request if in another team |
| Remove user | `POST /admin/users/<id>/remove_from_my_team` | Deactivates membership, must be in manager's team |
| Request move | `POST /admin/users/<id>/request_move_to_my_team` | Creates pending `TeamChangeRequest` |
| Approve move | `POST /admin/team_change_requests/<id>/approve` | Only source team manager or superadmin can approve |

### Files
- `backend/models.py` — `User`, `Team`, `Membership`, `Manager`, `TeamChangeRequest`
- `backend/services/admin_service.py` — business logic

---

## Section 4: Tracker Device Authentication

**Status: IMPLEMENTED**

### What was done
- Tracker agents send `Authorization: Bearer <token>` + `X-LAN-ID: <lan_id>` headers.
- Server validates: token hash exists in `tracker_device_tokens`, not revoked, not expired; LAN ID exists in `users`; user has active team membership; token team matches user team.
- In `DEMO_MODE=true`, auth is skipped (backward compat).

### Token management endpoints
| Endpoint | Purpose |
|----------|---------|
| `POST /admin/device-tokens` | Create token (team-scoped, returns plaintext once) |
| `POST /admin/device-tokens/<id>/revoke` | Revoke a token |
| `POST /admin/device-tokens/<id>/rotate` | Revoke old + create new linked token |

### Files
- `backend/blueprints/tracker.py` — `_verify_tracker_auth()` middleware
- `backend/models.py` — `TrackerDeviceToken` model
- `tracker/agent.py` — sends `TRACKER_DEVICE_TOKEN` + `LAN_ID` headers

---

## Section 5: Audit Logging (Enhanced)

**Status: IMPLEMENTED**

### What was done
- Enhanced `AuditLog` model with v2 fields: `actor_user_id`, `actor_team_id`, `target_team_id`, `request_id`, `extra_data` (JSONB).
- `log_action()` auto-captures `request_id` from `g.request_id`, IP, User-Agent.
- All admin actions are logged: login/logout, view users, assign/remove, move requests, IDOR blocks, device token CRUD.

### Files
- `backend/models.py` — enhanced `AuditLog`
- `backend/audit.py` — `log_action()` with v2 fields

---

## Section 6: Security Controls

**Status: IMPLEMENTED**

### Session hardening
```
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = 30 minutes
SESSION_COOKIE_SECURE = True (when not demo mode)
```

### CSRF protection
- Flask-WTF `CSRFProtect` enabled globally.
- API endpoints using token auth are exempted.
- Admin form submissions include CSRF tokens.

### Security headers (production mode)
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'
```

### CORS
- Demo mode: open (backward compat).
- Production mode: restricted to `CORS_ALLOWED_ORIGINS` allowlist.

### Rate limiting
| Endpoint | Limit |
|----------|-------|
| `/admin/login` | 5/minute |
| `/track`, `/tracker/ingest` | 120/minute (per device) |

### Request context
- Every request gets a `X-Request-Id` UUID (generated or accepted from client).
- Stored in `g.request_id` and included in audit log entries.
- PostgreSQL RLS: `SET LOCAL app.user_team_id` on each request for row-level security policies.

### Files
- `backend/middleware/request_context.py`
- `backend/middleware/security_headers.py`
- `backend/app.py` — CSRF init, rate limiter, CORS config, session config

---

## Section 7: Data Minimization (Previously Implemented)

**Status: PREVIOUSLY IMPLEMENTED — preserved**

- `WINDOW_TITLE_MODE=redacted` (default) — only classification keywords stored.
- Regex scrubbing of emails, long numbers, internal IDs.
- `DROP_TITLES=true` — server-side enforcement to discard all titles.
- No regressions to these features.

---

## Section 8: Demo Mode

**Status: IMPLEMENTED**

- `DEMO_MODE=true` (default): all security features bypassed for development/demos.
- `DEMO_MODE=false`: all security features enforced; startup checks verify required config.
- Startup check verifies: `SECRET_KEY` set, `OIDC_ISSUER_URL` or `ADMIN_PASSWORD` set, `DATABASE_URI` is PostgreSQL.

---

## Database Migrations

Managed by **Alembic** (`migrations/` directory).

### Commands
```bash
# Apply migrations
python -m alembic upgrade head

# Generate a new migration after model changes
python -m alembic revision --autogenerate -m "description"

# Rollback one migration
python -m alembic downgrade -1
```

### Backfill script
```bash
# Populate User/Team/Membership from existing telemetry data
python -m scripts.backfill_teams
```

---

## Testing

35 automated tests covering:
- Admin authentication (login redirect, session management, role enforcement)
- Team isolation (IDOR prevention, cross-team query blocking)
- Tracker auth (token validation, revocation, team mismatch)
- OIDC flow (login/callback behavior, demo mode fallback)

### Commands
```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_team_isolation.py -v

# Run with strict deprecation warnings
python -m pytest tests/ -v -W error::DeprecationWarning
```

---

## Security Checklist

- [x] Admin login via OIDC SSO only (no password login by default)
- [x] Manager session derives team_id server-side; never from client input
- [x] All admin queries include team_id filter
- [x] URL-based team_id params validated against session; 403 + audit on mismatch
- [x] IDOR protection on user-specific endpoints
- [x] Tracker endpoints require valid device token + LAN-ID (when not demo mode)
- [x] LAN-ID not trusted without a valid device token
- [x] Session cookies: Secure, HttpOnly, SameSite=Lax, 30-min lifetime
- [x] CSRF protection on admin mutation endpoints
- [x] Rate limiting on login, tracker ingest
- [x] Security headers (HSTS, CSP, X-Frame-Options, etc.)
- [x] CORS restricted to explicit allowlist
- [x] All admin actions audit-logged with request_id correlation
- [x] No secrets in repo; all via env vars; `.env.example` has placeholders only
- [x] Automated tests verify cross-team access blocked, IDOR fails, invalid tokens rejected
- [x] Alembic migrations for all schema changes
- [x] Backfill script for existing data

---

## New Files Summary

| File | Purpose |
|------|---------|
| `backend/auth/__init__.py` | Auth package |
| `backend/auth/oidc.py` | OIDC client config + login + callback |
| `backend/auth/authz.py` | `@admin_required`, `@team_scoped` decorators |
| `backend/blueprints/__init__.py` | Blueprints package |
| `backend/blueprints/admin.py` | Admin blueprint (SSO + team dashboard + management) |
| `backend/blueprints/tracker.py` | Tracker ingest blueprint (device auth) |
| `backend/blueprints/public.py` | Public endpoints (health, summary, apps) |
| `backend/services/__init__.py` | Services package |
| `backend/services/admin_service.py` | Team-scoped admin business logic |
| `backend/middleware/__init__.py` | Middleware package |
| `backend/middleware/request_context.py` | Request ID, RLS context |
| `backend/middleware/security_headers.py` | HSTS, CSP, X-Frame-Options |
| `backend/utils.py` | Shared utility functions |
| `backend/templates/admin/base.html` | Admin portal base template |
| `backend/templates/admin/login.html` | SSO login page |
| `backend/templates/admin/dashboard.html` | Team-scoped dashboard |
| `migrations/` | Alembic migration directory |
| `scripts/backfill_teams.py` | Data migration script |
| `tests/conftest.py` | Test fixtures (2 teams, 2 managers, 4 users) |
| `tests/test_admin_authz.py` | Auth/authz tests |
| `tests/test_team_isolation.py` | Team isolation + IDOR tests |
| `tests/test_tracker_auth.py` | Device token auth tests |
| `tests/test_oidc_flow.py` | OIDC flow + public endpoint tests |

---

## Modified Files Summary

| File | Changes |
|------|---------|
| `backend/models.py` | Added User, Team, Membership, Manager, TrackerDeviceToken, TeamChangeRequest; enhanced AuditLog |
| `backend/app.py` | Refactored to blueprint architecture; added CSRF, session hardening, OIDC init, middleware |
| `backend/audit.py` | Enhanced `log_action()` with v2 fields (actor_user_id, team_id, request_id, metadata) |
| `backend/config.py` | Added OIDC, CORS, session, rate limiting, break-glass config vars |
| `tracker/agent.py` | Sends device token + LAN-ID headers when configured |
| `requirements.txt` | Added authlib, flask-session, flask-wtf, marshmallow, alembic, pytest |
| `.env.example` | Documented all new config variables |
