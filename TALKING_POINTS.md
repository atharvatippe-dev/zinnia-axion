# Zinnia Axion — Presentation Talking Points

**For:** Technology Head, Security Officials, Leadership
**Duration guidance:** 30–45 minutes with Q&A

---

## Opening — What Is Zinnia Axion?

- Zinnia Axion is an **enterprise productivity intelligence platform** built entirely in-house.
- It silently tracks how employees use their computers and classifies time as productive or non-productive using a **confidence-scored decision tree** — not simple app blacklists.
- It runs on **macOS, Windows, and Linux** — deploying as a standalone executable with zero dependencies on the employee's machine.
- **Privacy is a core design principle:** We never capture what people type, never take screenshots, never read files, never record URLs. Only interaction counts and app names.

---

## The Problem We're Solving

- Traditional time-tracking tools either rely on self-reporting (inaccurate) or invasive monitoring (screenshots, keystroke logging — privacy nightmare).
- We needed a tool that:
  - Gives **real, data-driven visibility** into how work time is spent across teams
  - Is **privacy-respecting** enough to pass security review
  - Works in **enterprise VDI/Citrix environments** where most tools break
  - Supports **hierarchical team structures** where managers only see their own teams
  - Cannot be **gamed** with auto-clickers or mouse jigglers

---

## Architecture — How It Works (3-Minute Version)

1. **Tracker Agent** sits on the employee's machine. Every 1 second, it records: which app is in the foreground, how many keystrokes (count only), how many mouse clicks, how far the mouse moved, and how long the user has been idle.

2. Every **10 seconds**, these samples are batched and sent over HTTPS to our **Flask backend**.

3. The backend **stores raw 1-second events** in PostgreSQL. It never pre-classifies anything at write time.

4. When a dashboard loads, the backend groups events into **60-second clock-aligned buckets** and runs each through a **5-rule decision tree** with a confidence score. This is the key innovation — classification happens at read time, so we can update rules without reprocessing history.

5. **Dashboards** (Streamlit) show managers their team leaderboard, per-user drill-downs, app breakdowns, and 7-day trends. Access is controlled via **OIDC SSO** with hierarchical team isolation.

---

## The Classification Engine — Our Differentiator

### Why Not Just Use App Blacklists?

- Simple approach: "YouTube = non-productive, VS Code = productive."
- Problem: Someone could have VS Code open for 8 hours without touching the keyboard. That's not productive — that's leaving a window open.
- Our approach: We compute a **confidence score** from 4 real signals, then apply rules.

### The 4-Parameter Confidence Score

- **Density** — how much are they typing and clicking relative to a threshold? High density = actively working.
- **Coverage** — is the mouse moving? Low coverage = screen is open but nobody's using it.
- **Presence** — what fraction of the 60-second window had the user physically present (low idle time)?
- **Idle penalty** — how long was the longest idle gap? If someone was idle for 45 of 60 seconds, confidence drops sharply.

These four values are averaged into a base confidence score (0 to 1), then multiplied by penalty factors:
- **Distraction visible** on another monitor? Confidence × 0.70
- **Non-productive app mixed in** the bucket? Confidence penalized proportionally
- **Bot-like input detected** (auto-clicker)? Confidence × 0.30

### The 5-Rule Decision Tree (Priority Order)

1. **Meeting apps** (Zoom, Teams, Meet) → always productive. Meetings are work.
2. **Non-productive apps dominant** (≥67% of the bucket is YouTube/Netflix/Reddit) → non-productive. Even if you're clicking a lot on YouTube, it's not work.
3. **Anti-cheat** — bot-like input pattern detected → non-productive. Auto-clickers and key repeaters are caught.
4. **High confidence** (≥ 0.60) → productive. Genuine human activity on a non-blacklisted app.
5. **Everything else** → non-productive. If we can't prove you were working, we don't count it.

### Why 60-Second Buckets?

- Old model used 10-second buckets. Too noisy — switching apps for 3 seconds would flip an entire bucket.
- 60 seconds gives enough signal to compute meaningful confidence. A full minute of behavior tells you a lot more than 10 seconds.
- We scale all thresholds proportionally (e.g., 2 keystrokes per 10s → 12 per 60s).

### Proportional App Time Splitting

- If someone uses VS Code for 38 seconds and ChatGPT for 22 seconds in one minute, we don't give the full 60 seconds to VS Code.
- Each app gets credit for exactly the seconds it was in the foreground.
- This makes the app breakdown charts significantly more accurate.

---

## Security Architecture — Enterprise Grade

### Authentication (Who Are You?)

- **Managers:** OIDC SSO only (Azure AD, Okta). Authorization Code Flow with PKCE. No local passwords. MFA enforced by the identity provider.
- **Tracker agents:** Two-factor device authentication — Bearer token (SHA-256 hashed, with expiry and revocation) plus X-LAN-ID header. The backend validates both.
- **Sessions:** Server-side, 8-hour lifetime, cookies marked Secure + HttpOnly + SameSite=Lax.

### Authorization (What Can You See?)

- **Role-based:** `user`, `manager`, `superadmin`.
- **Hierarchical team isolation:** A manager at Lifecad sees Lifecad and its child team Axion — but never the parent Engineering team or sibling Fast team.
- **Every data access** passes through `assert_user_in_scope()` — the user's team must be within the manager's computed subtree.
- **team_id is never accepted from the client.** It's always derived from the authenticated session. This prevents parameter tampering.

### IDOR Prevention

- Every attempt to access data outside your scope returns **HTTP 403** and is **automatically logged** in the audit table with your identity, IP address, and User-Agent.
- We have 20+ automated tests specifically for cross-team data isolation.

### Defense in Depth — Layered Security

| Layer | Control |
|-------|---------|
| Transport | HTTPS/TLS (ngrok or reverse proxy) |
| Authentication | OIDC SSO + device tokens |
| Authorization | RBAC + hierarchical team scoping |
| Data isolation | PostgreSQL Row-Level Security + service-layer guards |
| Input validation | Schema validation on every telemetry event |
| Rate limiting | 120/min ingest, 5/min login, 30/min mutations |
| CSRF | Flask-WTF on all mutations |
| Security headers | HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy |
| Audit | Immutable log with request_id correlation |
| Anti-cheat | Bot-like input detection, multi-monitor distraction scanning |

---

## Privacy — How We Protect Employee Data

### What We Collect

- App name (e.g., "Cursor", "Google Chrome")
- Keystroke **count** (never content — we literally cannot tell you what someone typed)
- Mouse click **count** (never coordinates or targets)
- Mouse distance in pixels
- Idle time
- Whether a non-productive app was visible on another monitor

### What We Never Collect

- Keystroke content
- Screenshots or screen recordings
- Clipboard contents
- File names or document contents
- Browser URLs
- Chat messages or email content

### Window Title Privacy

- Default mode is **"redacted"** — the title "RE: Salary Review - Gmail" is stored as just `"gmail"`. Only the classification keyword is kept.
- In "off" mode, titles are completely stripped.
- Even in "full" mode, emails, long numbers, and ID patterns are automatically scrubbed.

### Data Retention

- Events are automatically purged after 14 days (configurable).
- Audit logs are retained indefinitely for compliance.

---

## Anti-Cheat — Catching Gaming Attempts

### Auto-Clicker / Mouse Jiggler Detection

- Real typing is **bursty** — fast bursts of keystrokes, then pauses while reading or thinking.
- Auto-clickers produce **constant, uniform input** with no gaps.
- We check two things: (1) is there a natural ratio of zero-interaction samples? (2) are the keystroke counts varied or repetitive?
- Both must fail simultaneously to flag — reduces false positives.
- When flagged: confidence drops to 0.30 × original, and Rule 3 classifies as non-productive.

### Multi-Monitor Distraction Detection

- The tracker doesn't just check the focused app — it enumerates **every visible window** on all monitors.
- If YouTube is playing on Monitor 2 while VS Code is focused on Monitor 1, we know.
- Same for macOS Split View and Picture-in-Picture.
- When detected: confidence is multiplied by 0.70.

### VDI/Citrix/RDP Support

- Most productivity tools break in VDI because `GetAsyncKeyState` is silently blocked by the remote desktop protocol.
- Our Windows collector **auto-detects VDI** in the first 5 seconds by calibrating whether `GetAsyncKeyState` returns anything.
- If it doesn't, it switches to **idle-delta estimation** — monitoring `GetLastInputInfo` changes to infer when the user interacts.
- Fully automatic — no configuration needed.

---

## Team Hierarchy — Real Enterprise Structure

### The Problem

- In a flat model, one admin sees everyone. That doesn't work for 200-person organizations.
- We need: "Wasim manages Lifecad. He should see Lifecad and its sub-team Axion, but NOT the Engineering team above him or the Fast team beside him."

### Our Solution

- `Team` table has a `parent_team_id` (self-referential foreign key).
- On every admin request, we compute the manager's **subtree** — their team plus all descendants.
- PostgreSQL: single recursive CTE query. SQLite: BFS in Python.
- Result is cached per-request on `flask.g`.

### Example Hierarchy

```
Engineering (Nikhil — VP, sees ALL 4 teams)
  ├── Lifecad (Wasim — Manager, sees Lifecad + Axion)
  │     └── Axion (Atharva — Lead, sees Axion only)
  └── Fast (Punit — Manager, sees Fast only)
```

- Nikhil can see everyone. Wasim can see his team + Atharva's. Atharva only sees his own team. Punit only sees Fast.
- Cross-team access is blocked and audit-logged.

---

## Audit Trail — Complete Accountability

Every security-relevant action is recorded in an immutable audit log:

- **Who** did it (actor identity, user ID, team ID)
- **What** they did (action type: login, delete, assign, IDOR attempt, etc.)
- **Who** was affected (target user)
- **When** (UTC timestamp)
- **Where** from (IP address, User-Agent)
- **Correlation** (request_id — UUID linking all logs for one request)

### 14 Action Types Tracked

Login, logout, delete user data, assign user, remove user, request team transfer, approve transfer, create device token, revoke token, IDOR user blocked, IDOR team blocked, retention cleanup, payload too large, rate limited.

---

## Testing — What's Covered

- **43+ automated security tests** in the `tests/` directory
- Tests cover: authentication enforcement, hierarchical team isolation, IDOR prevention, device token validation, OIDC flow
- Every cross-team access pattern is tested — "Can Atharva see Wasim's data? → 403."
- Run with: `pytest tests/ -v`

---

## Deployment Options

| Option | For | How |
|--------|-----|-----|
| **Standalone .app / .exe** | End users (no Python needed) | PyInstaller build → distribute via MDM (Intune, JAMF) |
| **GitHub Actions** | CI/CD builds | Trigger workflow → download artifact |
| **Manual** | Developers | Clone repo → pip install → run |

The tracker auto-starts on login (LaunchAgent on macOS, Task Scheduler on Windows) and runs silently.

---

## Dashboards — What Managers See

### Admin Dashboard (SSO-Protected)

- **Team leaderboard** — all users ranked by non-productive percentage, color-coded rows
- **Online/offline status** — green dot = tracker sending data, red dot = last seen X minutes ago
- **Per-user drill-down** — click "View" to see app breakdown chart, productivity summary
- **Delete** — removes user's telemetry with confirmation prompt and audit log
- **AI Executive Summary** — OpenAI-generated team report with heuristic fallback
- **Date filter** — view any day's data, preserved across views

### User Dashboard (Self-Service)

- Personal productivity metrics
- App breakdown chart with proportional time per app
- 7-day trend line chart

---

## What Makes This Different From Commercial Tools

| Feature | Commercial Tools (Hubstaff, Time Doctor) | Zinnia Axion |
|---------|----------------------------------------|--------------|
| Screenshots | Yes (invasive) | **Never** |
| Keystroke content | Some capture it | **Never — counts only** |
| Classification | App blacklists | **Confidence-scored decision tree** |
| Anti-cheat | Basic or none | **Bot detection + multi-monitor scan** |
| VDI support | Usually broken | **Auto-detecting VDI fallback** |
| Team hierarchy | Flat or basic | **Recursive subtree isolation** |
| Data residency | Cloud (their servers) | **Self-hosted — your infrastructure** |
| SSO | Some | **OIDC native (Azure AD, Okta)** |
| Audit trail | Limited | **14 action types, immutable, correlated** |
| Cost | $7-15/user/month | **Zero — built in-house** |

---

## Current Status & Gaps

### What's Production-Ready

- Full classification engine with confidence scoring
- Hierarchical team isolation with IDOR prevention
- OIDC SSO integration
- Device token authentication for trackers
- Immutable audit logging
- macOS and Windows tracker agents (including VDI)
- Admin and user dashboards
- Automated security test suite (43+ tests)

### Known Gaps (Transparent)

| Gap | Status | Remediation |
|-----|--------|-------------|
| Code signing for executables | Not yet | Sign with Apple/Microsoft certificates before deployment |
| Auto-update mechanism | Not yet | Use MDM for controlled rollout |
| SAST/DAST scanning | Not yet | Run Bandit, pip-audit before production |
| Real-time alerting for IDOR | Not yet | Audit log is SIEM-ready; create alert rules |
| User dashboard authentication | Not yet | Public endpoints — add token auth if needed |

---

## Closing — Key Takeaways

1. **Privacy-first:** We prove productivity without invading privacy. No screenshots, no keystroke content, no URLs.
2. **Intelligence, not surveillance:** A confidence-scored decision tree is fundamentally different from "is YouTube open? → bad."
3. **Enterprise-hardened:** OIDC SSO, hierarchical RBAC, IDOR prevention, immutable audit log, anti-cheat detection.
4. **Self-hosted:** All data stays within our infrastructure. No third-party cloud dependency.
5. **Works everywhere:** macOS, Windows, Linux, VDI/Citrix/RDP — auto-detecting and adapting.
6. **Built for scale:** Recursive CTE for team hierarchy, per-user bucketing, clock-aligned classification, 14-day auto-retention.

---

## Anticipated Q&A

**Q: Can we see what employees type?**
A: No. Technically impossible. The tracker only records keystroke counts — the `pynput` listener counts key-press events but never inspects which key was pressed (on macOS). On Windows, `GetAsyncKeyState` polls key states but we only increment a counter — no key mapping.

**Q: What if someone leaves their laptop open with VS Code and goes home?**
A: Confidence score handles this. With zero keystrokes, zero clicks, increasing idle time — all four confidence parameters drop to near zero. Rule 5 classifies it as non-productive. The app name doesn't matter.

**Q: Can a manager see another manager's team data?**
A: Only if they're higher in the hierarchy. Wasim (Lifecad) can see Atharva's team (Axion, child of Lifecad) but cannot see Punit's team (Fast, sibling). Every cross-scope attempt returns 403 and is audit-logged.

**Q: What if the backend goes down?**
A: The tracker buffers events locally in `buffer.json`. When the backend comes back and the tracker is restarted, it flushes the buffer in 100-event chunks. No data is lost.

**Q: What about GDPR / data subject access requests?**
A: The admin dashboard has per-user delete functionality. All telemetry for a specific user can be wiped with one click (with confirmation). The action is audit-logged. Data auto-purges after 14 days regardless.

**Q: How do we know the classification is accurate?**
A: We can inspect any bucket. The system stores the confidence score, which rule fired, the dominant app, all ratios, and the raw event count. We demonstrated live: a bucket with confidence 0.757 where YouTube was mixed with ChatGPT — correctly identified as a mixed-activity minute rather than pure YouTube.

**Q: Can employees game the system?**
A: Auto-clickers and mouse jigglers are detected by the anti-cheat module (statistical analysis of input patterns). Multi-monitor distractions (YouTube on Monitor 2) are detected by window enumeration. The confidence score catches "app open but nobody home" scenarios. No system is ungameable, but ours raises the bar significantly.
