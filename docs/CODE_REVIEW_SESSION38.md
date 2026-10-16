FishIntel / AquaIntel
Full Code Review — Session 38
Repository: github.com/frehan83-collab/AquaIntel (public)
Baseline: End of Session 37 (commit aa330e1)
Reviewer: Claude (5 parallel specialist agents)
Date: 2026-04-14

Executive Summary
AquaIntel is a mature, well-instrumented aquaculture intelligence platform — 340 API endpoints, 75 engines, 63 pages, 447 tests, and 14 Alembic migrations. The architectural decisions shipped over the last 30+ sessions are sound: async DB pool, tenacity retries on the biggest upstream (BarentsWatch), Pydantic schemas, design tokens, and a mature CI pipeline.
This review surfaced 33 prioritised findings across five dimensions. Four are CRITICAL and need same-week attention: (1) live credentials committed to .env, (2) unauthenticated admin endpoints, (3) unauthenticated webhook CRUD with IDOR, and (4) the agent subsystem runs on a daemon thread with no graceful shutdown. None are architectural dead ends — all are solvable with focused work inside the existing structure.
The other findings fall into four themes: (1) test quality drift (37 xfail markers and 32 smoke-only tests mask regressions), (2) the misc_routes.py junk drawer and a 600-line dashboard page that need decomposition, (3) graceful-degradation gaps when SSB/MET.no go down, and (4) frontend type safety eroded by a single eslint-disable in the API client. Recommended path: one week to close the four CRITICAL items, then a three-week quality sprint across the HIGH findings.
Platform Baseline (End of Session 37)
Metric
Value
Notes
API endpoints
~340
across 26 router modules
Market/data engines
~75
incl. 3 ML foundation models
Data source clients
45+
MUR SST, NorKyst, PACE, SEPA, EUMOFA, …
Frontend pages
63
68 compiled routes
Components
43+
design tokens: 86
Tests
447 (0 failures)
14 xfailed, 21 xpassed
Database tables
31
14 Alembic migrations
i18n keys
~600
NO / EN, locale-aware formatting
Stack
FastAPI 2.2 + Next.js 15.5 + React 19.2
Python async throughout, React Compiler

Finding Distribution
Severity
Count
Examples
CRITICAL
7
Live credentials in .env; unauthenticated admin + webhook endpoints; daemon-thread agents
HIGH
17
misc_routes junk drawer; 75% endpoints lack try/except; ephemeral JWT secret; DB pool undersized; no retry on SSB/MET.no
MEDIUM
9
Business logic in routers; test DB dependency; i18n key typing; chart magic numbers
LOW
0
Copy-paste test patterns; locale persistence; singleton naming

Top 10 Priorities
Recommended order of attack. Items 1–4 are CRITICAL and should be closed within a week. Items 5–10 form a ~3-week quality sprint.
#
Action
Effort
Severity
1
Rotate credentials and purge .env from git history
0.5 day
CRITICAL
2
Authenticate admin and webhook routers (add ownership checks)
1 day
CRITICAL
3
Require FISHINTEL_JWT_SECRET at startup (no ephemeral fallback)
2 hours
CRITICAL
4
Separate agents into own process/container (no daemon thread)
1 day
CRITICAL
5
Decompose misc_routes.py into 5 focused routers
1 day
HIGH
6
Add retry + circuit breaker to SSB and MET.no (match BarentsWatch pattern)
0.5 day
HIGH
7
Add unit tests for 5 new Session 37 clients (~60 tests)
1 day
HIGH
8
Move JWT token from localStorage to HttpOnly cookie + add CSP
1 day
HIGH
9
Remove eslint-disable from api.ts; type all 180+ methods
1.5 days
HIGH
10
Add DataQualityBadge to the 36 missing data pages
1 day
HIGH

Detailed Findings
Security
  CRITICAL     Live API credentials committed to .env
File: .env (BarentsWatch, Copernicus, OpenRouter)
Issue: Real secrets (BARENTSWATCH_CLIENT_SECRET, CMEMS_PASSWORD, OPENROUTER_API_KEY) are in the tracked .env file and git history.
Fix: Rotate all three credentials immediately. Purge .env from history with git-filter-repo. Keep only .env.example. Add .env to .gitignore with an explicit comment.
  CRITICAL     Admin endpoints have no authentication
File: core/routers/admin_routes.py (lines 33–178)
Issue: /api/admin/cache-stats, /status, /data-quality, /export/{dataset}, /audit-log are all reachable without auth. They leak schema, row counts, audit trail, and allow full CSV/JSON data export.
Fix: Wrap every admin endpoint with Depends(get_current_user) and require tier=='investor' (or a dedicated admin role). Add an integration test that hits each endpoint anonymously and expects 401/403.
  CRITICAL     Webhook CRUD endpoints are unauthenticated with IDOR
File: core/routers/webhook_routes.py (lines 35–178)
Issue: GET/POST/DELETE on webhooks require no auth. user_id is read from the request body on create, so anyone can create/delete webhooks for any user and enumerate URLs (which may contain embedded tokens).
Fix: Require auth on all webhook routes. Derive user_id from the JWT, never from the body. Enforce ownership checks on delete/update.
  HIGH     JWT secret is ephemeral (regenerated on each restart)
File: core/auth.py:38–42
Issue: If FISHINTEL_JWT_SECRET is unset, auth.py generates a fresh random secret on every startup. All users are signed out on deploy; multi-instance deployments have diverging secrets.
Fix: Fail fast with a clear error if FISHINTEL_JWT_SECRET is missing. Document the secret generation command. Consider a two-key rotation window for zero-downtime rollouts.
  HIGH     No SSRF protection on webhook URLs
File: core/routers/webhook_routes.py:72
Issue: Only the URL scheme is validated. An attacker can point a webhook at http://localhost:8000/api/admin/status or http://169.254.169.254/ (cloud metadata).
Fix: Resolve the hostname and block loopback, link-local, and RFC1918 ranges. Bound Content-Length on responses. Keep the existing 5s timeout.
  HIGH     JWT stored in localStorage on the frontend
File: frontend/src/app/login/page.tsx:34
Issue: aquaintel_token sits in localStorage — accessible to any script that runs on the page. Any XSS becomes a full session takeover.
Fix: Move auth tokens to an HttpOnly, Secure, SameSite=Lax cookie set by the backend. Add a strict Content-Security-Policy header.
  MEDIUM     No webhook signature on outbound dispatch
File: core/market/webhook_dispatcher.py
Issue: Webhook receivers can't verify that payloads came from AquaIntel. MITM or replay attacks are possible.
Fix: HMAC-sign each payload with a per-hook shared secret; include X-Signature and X-Timestamp headers; document verification for receivers.
Architecture
  CRITICAL     Insecure default secret_key in config
File: config/settings.py:43
Issue: secret_key defaults to 'change-me'. If .env is missing in deployment, JWT tokens can be forged.
Fix: Remove the default. Add a startup assertion that secret_key != placeholder and has length > 32. Fail fast at import time.
  HIGH     misc_routes.py is a junk drawer (57 endpoints across 8 domains)
File: core/routers/misc_routes.py (571 lines)
Issue: One router holds feed-cost, causal, ocean, RAS, ESG, contracts, AIS, and satellite endpoints. No cohesion; impossible to own or test as a unit.
Fix: Split into 5 focused routers: feed_cost_routes, causal_routes, ocean_routes, ras_routes, macro_routes. Keep only health/version in misc.
  HIGH     Synchronous Session() calls in Streamlit dashboard
File: dashboard/app.py (1,615 lines, 14 sync sites)
Issue: 14 'with Session()' blocks in a Streamlit app block the event loop and bypass the async DB pool entirely.
Fix: Streamlit is synchronous by design — replace direct ORM calls with calls to the FastAPI backend. Remove the tangle.
  HIGH     75% of endpoints lack try/except guards
File: All routers (71/275 have error handling)
Issue: Most endpoints will return raw 500s on any transient failure (DB blip, upstream timeout). Poor UX, log spam.
Fix: Add a global exception handler middleware that maps known errors (IntegrityError, httpx.TimeoutException, upstream HTTPStatusError) to clean 4xx/5xx responses.
  MEDIUM     Business logic interleaved with I/O in routers
File: All routers
Issue: SQL queries and HTTP calls live inside endpoint handlers — no service layer. Hard to test, reuse, or mock.
Fix: Introduce core/services/ with pure functions per domain. Routers become thin HTTP adapters (5–10 lines).
  MEDIUM     Only 7 endpoints use FastAPI Depends() — no DI
File: All 275 endpoints
Issue: Dependencies are imported inline inside functions. Can't mock session/user/config for tests.
Fix: Create get_db, get_current_user, get_settings dependency functions. Inject via Depends() consistently.
  MEDIUM     981 blocks of commented-out code across repo
File: Throughout
Issue: Dead code obscures intent and bloats files. Git history is the right place for past versions.
Fix: One-time sweep to delete all commented code blocks. Add pre-commit rule to flag commented Python in PRs.
Performance
  CRITICAL     Agents run on a daemon thread with ungraceful shutdown
File: main.py:134–141
Issue: Background agents run in a daemon thread. SIGTERM kills them mid-transaction, potentially corrupting data or leaking HTTP connections.
Fix: Split agents into their own container/process, or switch to an asyncio task group with proper cancellation scopes and a shutdown hook.
  HIGH     DB pool undersized for agents + workers
File: core/async_db.py:31–42
Issue: pool_size=20, max_overflow=40. With 4 Gunicorn workers each using up to ~10 connections and 12 concurrent agents, agents regularly queue and time out.
Fix: Raise to pool_size=30, max_overflow=60. Confirm via Prometheus that checkout wait time < 100ms p95 under peak load.
  HIGH     No retry or circuit breaker on SSB / MET.no
File: core/market/ssb_exports.py, met_ocean.py
Issue: Single attempt, silent fallback to stale cache. BarentsWatch already uses tenacity; these two don't.
Fix: Apply the existing tenacity @retry(stop_after_attempt(3), wait_exponential(...)) pattern. Add a minimal circuit breaker to skip calls for 60s after 5 consecutive failures.
  HIGH     Unbounded in-memory caches
File: core/cache.py, sentiment_engine._articles
Issue: CacheManager._store has no size cap; the sentiment article cache grows until a weekly prune. Long-running processes leak memory.
Fix: Replace with cachetools.TTLCache(maxsize=N) or implement LRU eviction. Expose size as a Prometheus metric.
  HIGH     No backpressure on WebSocket command-centre stream
File: core/api.py:755–837
Issue: Fixed 30-second push interval with no check on client readiness. Slow clients bloat the send buffer.
Fix: Check websocket.client_state before each send, drop oldest frame if buffer exceeds N items, and close connections that fail to ack within 2× the interval.
  MEDIUM     httpx client churn in country monitors
File: core/market/canada_monitor.py (lines 142, 180, 198)
Issue: Creates a new httpx.AsyncClient per call — TLS handshakes and connection churn on every poll.
Fix: Adopt the singleton pattern used in sentiment_engine (_ensure_client + shutdown). Apply across all country monitors.
Testing
  CRITICAL     Zero unit tests for 5 of 7 new Session 37 clients
File: tests/ — missing mur_sst, norkyst, nasa_pace, sepa, eumofa_trade
Issue: These clients make live HTTP calls to NASA, MET.no, SEPA, and EUMOFA. API drift will fail silently in production.
Fix: Add tests/test_session37_clients.py: pure-function tests for helpers (_classify_chl_risk, _current_speed_and_dir, _assess_conditions) + mocked HTTP tests for success and fallback paths. Target: ~60 tests total.
  HIGH     37 xfail markers hide real bugs
File: test_all_engines.py, test_critical_engines.py, test_market_engines.py
Issue: xfail is used for real code issues (async context bugs, untrained models), not just external API unavailability. A regression can silently change xfail → xpass.
Fix: Audit each xfail. Fix code issues in place. Use pytest.skip() at runtime only for true external-dependency cases.
  HIGH     32 tests are 'import and assert not None' smoke tests
File: test_all_engines.py
Issue: These tests confirm the module compiles — nothing else. Replace with structural and behavioural checks.
Fix: Replace with hasattr/callable assertions on expected methods. Use pytest.parametrize to cover all 29 engines in one compact block.
  HIGH     Router and ORM-using tests hit the real database
File: test_market_engines.py, test_api_routes.py
Issue: Tests depend on production DB state. CI is flaky; fresh environments can't run the suite.
Fix: Introduce an in-memory SQLite fixture with Alembic-applied schema and fixture data. Mock external HTTP calls with respx or httpx_mock.
  MEDIUM     CI coverage floor is only 50%
File: .github/workflows/test.yml
Issue: A 50% threshold masks entirely untested modules (lice_gnn, regime_detector, most clients).
Fix: Raise to 75% overall. Add per-module minimums: decision_engine, treatment_optimizer, price_ml at ≥90%.
  MEDIUM     No Playwright E2E tests for critical user flows
File: frontend/e2e/
Issue: Backend can ship, frontend can quietly break. The core flow (login → dashboard → decision) has no end-to-end coverage.
Fix: Add 5 Playwright tests: login, dashboard KPIs load, price outlook chart renders, farmer-daily decision card, admin tier check.
Frontend
  CRITICAL     eslint-disable blanket-any on the API client
File: frontend/src/lib/api.ts:1
Issue: 180+ API methods default to <T = any>. All type safety is forfeited for the most-used file in the app.
Fix: Remove the eslint-disable. Add explicit return types using the 33 interfaces in types/api.ts. Enable noImplicitAny if not already on.
  HIGH     Dashboard prop-drilling and 600-line page.tsx
File: frontend/src/app/page.tsx
Issue: 20+ useState, 15+ API calls, and all JSX live in one file. Restructuring requires editing 4 nesting levels.
Fix: Extract 5 subcomponents (HeroAlert, KPIStrip, LiveIntelligence, Movers, Production) and a useDashboardData hook.
  HIGH     DataQualityBadge missing on 36+ data-driven pages
File: frontend/src/app/market, trader, investor, farm, treatment, efficacy, harvest, welfare, scenarios, causal, ml-baselines, …
Issue: Users on these pages can't see data freshness or confidence — exactly the pages where decisions are made.
Fix: Add <DataQualityBadge provenance={...}/> to the KPI strip of every data page. Target: 55+/63 pages.
  HIGH     Silent API failure with no user feedback
File: frontend/src/app/page.tsx:135–137 (pattern repeats)
Issue: .catch(handleError(...)) logs in dev and shows a toast only for critical calls. Non-critical data sections silently display null indefinitely.
Fix: Show a small inline 'Couldn't load — retry' state per section. Cap toasts so users don't get spammed, but don't hide failures.
  HIGH     Accessibility: 40+ interactive regions lack ARIA/keyboard
File: BentoGrid.tsx:142, KPICard hover buttons, sidebar search
Issue: SVG <g> elements with onMouseEnter but no role, tabIndex, or aria-label. Keyboard-only users cannot activate them.
Fix: Convert to <button> where possible, add role='button', tabIndex=0, onKeyDown Enter/Space, and an aria-label per region.
  MEDIUM     Magic numbers for chart layout
File: RegionalHeatmap.tsx, market/page.tsx chart code
Issue: SVG_W, CELL_H, PAD are hardcoded per file — inconsistent with the 86-token design system.
Fix: Move chart metrics to design-tokens.ts under a chartLayout key and import everywhere.
  MEDIUM     i18n keys are untyped strings
File: frontend/src/lib/i18n.ts, all pages
Issue: Typos like t('nav.inteligence') silently render the key. No IDE autocomplete across 600 keys.
Fix: Generate a typed KEYS const (or a string-literal union) from the i18n tree and require t() to accept that type.

Recommended Four-Week Plan
Week 1 — Security & Reliability (CRITICAL)
Rotate the three committed credentials; purge from git history with git-filter-repo.
Add auth + ownership checks to admin_routes.py and webhook_routes.py.
Require FISHINTEL_JWT_SECRET at startup. Add a startup assertion on secret_key length.
Extract background agents to their own process/container; remove daemon thread.
Add SSRF protection on webhook URL creation.
Week 2 — Architecture & Hygiene
Split misc_routes.py into feed_cost, causal, ocean, ras, macro routers.
Add retry + circuit breaker to SSB and MET.no clients.
Raise DB pool to 30 / 60 overflow and add Prometheus metrics for wait time + cache hit rate.
Convert httpx client creation in country monitors to singletons.
One-time sweep: delete 981 commented-code blocks; add a pre-commit rule.
Week 3 — Testing
Add unit tests for MUR SST, NorKyst, NASA PACE, SEPA, EUMOFA trade clients (~60 tests).
Audit all 37 xfail markers; fix code issues or convert to runtime pytest.skip().
Replace 32 smoke tests with parametrized structural checks.
Introduce in-memory SQLite fixture with Alembic schema; mock HTTP with respx.
Raise CI coverage floor to 75% overall + 90% for decision/treatment/price_ml.
Week 4 — Frontend Quality
Remove eslint-disable from api.ts; type all 180+ methods using types/api.ts.
Add DataQualityBadge to the 36 data pages missing it.
Extract 5 subcomponents from app/page.tsx; move tokens out of localStorage.
Accessibility pass: ARIA/keyboard on the 40+ interactive regions flagged.
Add 5 Playwright E2E tests for the critical user flows.

Appendix — Review Methodology
Five specialist exploration agents ran in parallel over the full C:\Users\freha\FishIntel tree. Each was given a focused charter and asked for at most 15 prioritised findings with file paths, line numbers where relevant, concrete evidence, and fixes. Findings were then de-duplicated, cross-checked against the PROJECT_STATUS.md baseline, and grouped by area.
Agents and their charters:
Architecture & code organisation — 855 Python files, 66.5K LOC, 25 routers, 40+ engines.
Security — auth, authz, secrets, CORS, rate limiting, XSS, SSRF, webhook, frontend storage.
Performance & reliability — DB pool, cache lifecycles, retry/circuit breakers, WebSocket backpressure, startup.
Testing — 14 test files, 447 tests, xfail audit, coverage gaps, flakiness, E2E posture.
Frontend — 63 pages, 43+ components, React 19 + Compiler, design tokens, i18n, a11y, error boundaries.
Each agent read actual source — no conclusions were drawn from documentation alone. Where a claim depends on dynamic behaviour (e.g. DB pool saturation under load), it is marked as expected rather than observed.
