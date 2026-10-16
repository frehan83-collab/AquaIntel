# ARCHITECTURE REPORT — Backend Excellence & Performance
**FishIntel Deep Excellence Summit — 2026-06-12**
**Agent:** ARCHITECTURE | **Scope:** async correctness, agent runtime, FastAPI practices, router consistency, resilience, versioning
**Method:** static analysis (grep over `core/`, `agents/`, `dashboard/`), runtime measurement (in-process TestClient without lifespan side effects, bcrypt micro-benchmark, read-only SQLite export simulation, middleware behavior test). All timings measured on the dev box (Windows 11, Python 3.14.3) unless labeled EXPECTED.

---

## Verdict

The foundation is **structurally sound but operationally unfinished**. The async migration is ~97% complete by call-site count, the router decomposition is real, and the import graph is clean (0.8s cold import of the whole app, measured). What remains are a small number of high-leverage gaps: **the production Docker deployment never runs the 12 agents at all**, the remaining sync DB islands sit in exactly the paths that block the event loop hardest (billing, custom-alert evaluation), bcrypt runs on the event loop per API-key request (189 ms measured), the ETag layer is empirically dead code, and the connection-pool math is inverted relative to what the Session 38 review claimed. None of this is sand — every fix below fits inside the existing structure.

Measured route inventory: **320 HTTP routes + 2 WebSockets** (304 across 25 router modules in `core/routers/`, 16 in `core/api.py`). The "~340" figure in PROJECT_STATUS.md overcounts by ~20.

---

## 1. Async Audit — Every Remaining Offender

### 1.1 Sync SQLAlchemy `Session()` inside async code paths (event-loop blockers)

| # | File:Line | Context | Impact |
|---|-----------|---------|--------|
| 1 | `core/billing/stripe_billing.py:112` | `async create_checkout_session` -> `with DBSession()` | Blocks loop for DB I/O; called from `POST /api/billing/create-checkout` (`core/routers/billing_routes.py:22`) |
| 2 | `core/billing/stripe_billing.py:175` | `async _handle_checkout_completed` | Same — webhook handler path |
| 3 | `core/billing/stripe_billing.py:217` | `async _handle_subscription_updated` | Same |
| 4 | `core/billing/stripe_billing.py:237` | `async _handle_subscription_deleted` | Same |
| 5 | `core/billing/stripe_billing.py:261` | `async get_subscription_status` | Called per page-load of /billing |
| 6 | `core/billing/stripe_billing.py:298` | `async cancel_subscription` | Same |
| 7 | `core/billing/stripe_billing.py:327` | `async get_invoice_history` | Same |
| 8 | `core/routers/notification_routes.py:432` | `async _fetch_current_metric` -> `with SyncSession()` (lice_avg) | Called **per rule** from `GET /api/notifications/alerts/rules/evaluate` (`evaluate_custom_rules`, line 517) — N rules x sync query on the loop |
| 9 | `core/routers/notification_routes.py:464` | same function, `sst` branch | Same |
| 10 | `core/routers/notification_routes.py:502` | same function, `bloom_risk` branch | Same |
| 11 | `core/market/climate_risk_engine.py:103` | `async _fetch_live_bloom_risk` -> `with DBSession()` | GROUP BY join over bloom assessments on the loop; serves `/api/climate/*` |
| 12 | `core/market/climate_risk_engine.py:413` | second sync session in same engine | Same |

**Not offenders (sync by design, acceptable):** `dashboard/app.py` (14 uses — separate Streamlit process), `core/demo_seed.py:195` (startup-only), test files. `core/models.py:577 init_db()` runs sync inside the async lifespan — one-time, acceptable.

**Additional blocking work on the event loop (not SQL):**

| File:Line | What | Measured/Expected |
|-----------|------|-------------------|
| `core/auth.py:214` (`verify_api_key` inside `async _authenticate_via_api_key`) | `bcrypt.checkpw` per candidate key, **per API-key-authenticated request** | **189 ms measured** (rounds=12). 10 concurrent API-key requests => ~1.9 s of serialized loop stall. The single worst per-request blocker in the platform. |
| `core/routers/auth_routes.py:88,95` | `verify_password` + optional `hash_password` rehash in `async login` | 189–380 ms measured per login (verify + rehash = 2 bcrypt ops). Bounded by the 10/min login rate limit but still stalls every other in-flight request. |
| `core/auth.py:221` | `await s.commit()` updating `last_used` on **every** API-key request | A DB write per authenticated request — on SQLite this takes the write lock; on PG a row update + commit round trip. |
| `core/billing/stripe_billing.py` (throughout) | The `stripe` SDK is synchronous; `stripe.checkout.Session.create` etc. are blocking HTTPS calls inside `async` methods | EXPECTED 200–1500 ms loop stall per billing operation (network RTT to Stripe). |
| `core/routers/admin_routes.py:453` (`_row_to_dict` loop) + `:469` (`_build_csv`) | Full-table export materialization in the handler | Measured via read-only simulation on the real DB: `lice` = 186,139 rows -> fetch 0.20 s (off-loop via aiosqlite) + **0.71 s pure CPU on the loop** (dictify + CSV) producing a 12.9 MB string. |

**No `requests.` usage anywhere in app code** (verified — zero matches in `core/`, `agents/`); 32 files in `core/` use `httpx`. `time.sleep` exists only in `scripts/`. This is genuinely good.

### 1.2 Migration path to 100% async (effort: ~1.5 dev-days total)

1. **stripe_billing.py** (0.5 day): convert the 7 sessions to `async with get_async_session()`; wrap every `stripe.*` SDK call in `await asyncio.to_thread(...)`. No interface change — all callers already `await` these methods.
2. **notification_routes.py `_fetch_current_metric`** (0.25 day): the function is already `async` and already uses async sessions in its other branches — convert the 3 sync branches to the pattern at line 401.
3. **climate_risk_engine.py** (0.25 day): same mechanical conversion; methods already `async`.
4. **bcrypt off the loop** (0.5 day):
   ```python
   # core/auth.py — in async contexts
   ok = await asyncio.to_thread(_bcrypt.checkpw, raw_key.encode(), api_key.key_hash.encode())
   ```
   Plus an in-process verified-key cache to amortize the cost entirely:
   ```python
   # sha256(raw_key) -> (user_id, tier, verified_at); TTL 300s, max 1024 entries
   # bcrypt only on cache miss; clear entry on revoke/rotate endpoints
   ```
   Also throttle the `last_used` write at `core/auth.py:221` (write at most once per 5 min per key).

---

## 2. Agent Runtime — The Daemon Thread, and the Worse Problem Behind It

### 2.1 What exists

- 12 agents (`agents/` + `execution/` + `compliance/` + `core/twin/self_evolve.py`), all subclassing `agents/base.py:BaseAgent` — a clean `tick()`-every-`interval_seconds` loop (default 900 s, `agents/base.py:31`) with `asyncio.Event` stop signaling and per-agent health counters. The base class itself is well designed.
- `main.py:136-141`: in full mode, agents run via `asyncio.run(run_agents())` on a **daemon thread** while uvicorn owns the main thread. On process exit the daemon thread is killed abruptly: the `agent.stop()` calls and `shutdown()` coroutines at `main.py:92-102` are unreachable in this mode (they only fire on `KeyboardInterrupt`/`CancelledError` inside the agents' own loop, which a daemon-thread kill never delivers). Mid-write SQLite transactions are rolled back by WAL journaling (data-safe), but in-flight multi-step sequences (e.g., `agents/data_ingest.py:44-74` upsert localities -> upsert lice) are left partially applied, and httpx/OAuth clients never close.

### 2.2 The finding the daemon thread was hiding: **production runs zero agents**

- `Dockerfile:33-41`: `CMD ["gunicorn", "core.api:app", ...]` — gunicorn imports `core.api:app` directly. `main.py` never executes in the container.
- `docker-compose.yml` services: `db`, `fishintel` (gunicorn container; comment at line 23 says "Backend: agents + API" — **false**), `frontend`, `nginx`. There is **no service that runs `python main.py --agents-only`**.
- Consequence: in any Docker deployment, BarentsWatch ingestion, sentiment polling (`main.py:43-54`), backfill, bloom monitoring, signal generation — all of it — silently never runs. The platform serves whatever data is in the mounted `data/aquaintel.db` volume, decaying forever. The daemon-thread shutdown bug is a **dev-mode** problem; the **production** problem is that the agent subsystem doesn't exist there.

### 2.3 Decision: split-process architecture (no new dependencies)

Rejected alternatives: **APScheduler/ARQ** (ARQ needs redis — not installed; APScheduler duplicates what `BaseAgent` already does), **agents inside FastAPI lifespan as the production mode** (with `-w 4`, all four gunicorn workers would each start all 12 agents — 4x duplicate ingestion and write contention; gating to one worker is fragile).

**The design (effort: 1 day):**

1. **Production:** add a compose service:
   ```yaml
   fishintel-agents:
     build: .
     command: ["python", "main.py", "--agents-only"]
     env_file: [.env]
     volumes: ["./data:/app/data", "./logs:/app/logs"]
     depends_on: { db: { condition: service_healthy } }
     restart: unless-stopped
   ```
2. **Graceful shutdown** in `run_agents()` (`main.py:57`):
   ```python
   stop = asyncio.Event()
   # POSIX (container): loop.add_signal_handler(SIGTERM, stop.set); SIGINT same.
   # Windows dev: KeyboardInterrupt -> finally-block calls stop.set().
   await stop.wait()
   for agent in agents: agent.stop()              # sets each _stop_event
   await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=25)
   await ingest.shutdown(); await exposure.shutdown()  # close httpx clients
   ```
   25 s drain fits compose's 30 s SIGTERM->SIGKILL window. Because `BaseAgent.start()` waits on `_stop_event.wait()` between ticks (`agents/base.py:56-58`), agents finish the current `tick()` rather than dying inside it.
3. **Dev single-process mode:** replace the daemon thread (`main.py:134-141`) with agents hosted in the API lifespan, gated by `FISHINTEL_EMBED_AGENTS=1` (default for `python main.py`, absent in Docker). One event loop, one process, clean Ctrl-C teardown — also removes today's two-event-loops-two-threads-one-SQLite-file situation.
4. **Crash visibility:** an agent that raises in `tick()` logs and continues (`agents/base.py:51-54`) — good — but a dead/cancelled task is invisible. Surface `agent.health()` aggregation on `/api/admin/status` (data structures already exist).

---

## 3. FastAPI 2026 Practices vs Reality

### 3.1 Connection pools — the Session 38 "undersized" claim is inverted

- `core/async_db.py:34-42`: async PG pool `pool_size=20, max_overflow=40` **per process**.
- `core/models.py:486-492`: a *second*, sync PG engine `pool_size=10, max_overflow=20` per process (still used by the section 1.1 offenders).
- `Dockerfile:35`: `-w 4` gunicorn workers => theoretical peak **4 x (60 + 30) = 360 connections**. TimescaleDB pg16 default `max_connections` is 100 and `docker-compose.yml` sets no override. Under burst the platform exhausts the *server*, not the pool — `FATAL: sorry, too many clients already` exactly when load peaks. Session 38's "DB pool undersized" is directionally wrong.
- **Decision (0.25 day):** `pool_size=5, max_overflow=10` per worker (peak 4x15=60 async), delete the sync PG pool once 1.2 lands, set `command: postgres -c max_connections=200` in compose as belt-and-braces, add `pool_timeout=10` so saturation surfaces as a fast error rather than a hang.
- **SQLite async engine has no busy timeout:** `core/async_db.py:29` passes no `connect_args`, so aiosqlite uses the sqlite3 default 5 s, while the sync engine gets 30 s (`core/models.py:482`) and `init_db` sets `busy_timeout=30000` only on its own connection (`core/models.py:582` — busy_timeout is per-connection and does not propagate). Under agent/backfill writes, async API calls can raise `database is locked` after 5 s. **Fix: one line** — `create_async_engine(_async_url, connect_args={"timeout": 30})`.

### 3.2 Caching layers

- `core/cache.py` — two parallel cache singletons (`EngineCache` + `CacheManager`) with the same semantics. Both are **unbounded dicts with lazy-only eviction**: expired entries are deleted only if the same key is read again (`cache.py:50-53`, `149-151`). Keys built from `str(args)` of arbitrary calls (`cache.py:91`) — endpoints with user-variable params grow the dict monotonically. Inside the 2 GB-capped container with `--max-requests 10000` recycling this is survivable, but it is a slow leak by construction.
- **Per-worker reality:** with 4 gunicorn workers there are 4 independent caches; `POST /api/cache/invalidate` (`core/api.py:373-383`) clears only the worker that served the request — and it is **unauthenticated**, so anyone can repeatedly clear caches and trigger upstream re-fetch storms. The same per-worker fragmentation applies to the slowapi rate limiter (in-memory storage => effective limit ~4x advertised tier) and to `cache_manager.get_stats()` on /admin.
- **Decision (0.5 day):** single bounded cache (max ~2,000 entries, LRU on insert, opportunistic sweep), deprecate one of the two classes, admin-auth on invalidate, document per-worker semantics. Do **not** add Redis now — single-host deployment doesn't justify it; revisit at multi-instance.

### 3.3 The ETag layer is dead code — **measured**

`core/cache_headers.py:133` guards ETag generation with `hasattr(response, "body")`. Under Starlette's `BaseHTTPMiddleware`, `call_next` returns `_StreamingResponse`, which has no `.body`. Empirical test (this audit: minimal Starlette app + the real middleware): `Cache-Control: public, max-age=300` is set, **ETag is never emitted**, the 304 branch never executes. The CLAUDE.md claim "API caching (ETag + 5-tier Cache-Control)" is half-true: tiers work, ETag/304 has never worked.
**Decision (0.5 day):** delete the in-middleware ETag path and let nginx (already fronting the API with proxy cache) handle conditional requests. Also fix: `/api/admin/status` is marked `public, max-age=3600` (`cache_headers.py:36`) — ops data must not be publicly cacheable through the nginx proxy cache.

### 3.4 Pydantic v2 / response_model coverage — measured

- `core/schemas.py`: 27 BaseModel classes exist. **`response_model=` appears on exactly 8 of 320 routes (2.5%)**: 1 in `lice_routes.py:19`, 1 in `decision_routes.py:236`, 6 in `notification_routes.py`. `core/api.py:274` imports `HealthResponse` and then doesn't apply it to `/api/health` (line 286).
- Consequence: OpenAPI documents `{}` for 97.5% of endpoints, the 59 hand-written TS interfaces in `frontend/src/types/api.ts` have zero enforcement against drift, and FastAPI's response validation/filtering is absent.

### 3.5 Lifespan correctness

- `core/api.py:44-53`: **all 4 gunicorn workers run `alembic upgrade head` concurrently at boot.** Concurrent DDL can deadlock or double-apply non-transactional steps; the except-clause downgrades any failure to a warning, so a worker can serve traffic against a half-migrated schema. **Decision (0.25 day):** run migrations as a compose entrypoint/init step; in lifespan only *verify* head revision and refuse to start otherwise.
- `Dockerfile:32` comment says "preload shares engine singletons" but the CMD has **no `--preload` flag** — the comment is wrong (not preloading is actually correct for asyncio engines; fix the comment).
- `core/models.py:585-596`: `init_db` schedules `seed_demo_outcomes()` via `loop.create_task(...)` without retaining a reference — fire-and-forget tasks can be garbage-collected and exceptions silently dropped. Retain a module-level reference or await in lifespan.

---

## 4. Router Consistency Matrix (measured, 25 router modules + api.py)

| Router | Routes | response_model | HTTPException | Auth deps | Provenance refs | Pagination params | Soft-200 errors |
|---|---|---|---|---|---|---|---|
| admin_routes | 6 | 0 | 6 | **0** | 1 | 2 | — |
| alerts_routes | 12 | 0 | 0 | 0 | 4 | 1 | — |
| analytics_routes | 24 | 0 | 5 | 0 | 16 | 1 | — |
| apikey_routes | 4 | 0 | 5 | **4** | 0 | 0 | — |
| auth_routes | 4 | 0 | 3 | 0 | 0 | 0 | — |
| billing_routes | 5 | 0 | 5 | 0 | 0 | 0 | — |
| bloom_routes | 5 | 0 | 0 | 0 | 14 | 3 | — |
| country_routes | 25 | 0 | 1 | 0 | 46 | 0 | — |
| decision_routes | 15 | 1 | 0 | 0 | 9 | 1 | 4 |
| disease_routes | 7 | 0 | 0 | 0 | 14 | 1 | — |
| farm_routes | 20 | 0 | 6 | 0 | 8 | 0 | 1 |
| integration_routes | 4 | 0 | 0 | 0 | 0 | 0 | — |
| investor_routes | 8 | 0 | 4 | 0 | 0 | 0 | — |
| lice_routes | 1 | 1 | 0 | 0 | 7 | 0 | — |
| locality_routes | 1 | 0 | 0 | 0 | 0 | 0 | — |
| market_routes | 26 | 0 | 1 | 0 | 8 | 0 | 2 |
| misc_routes | 57 | 0 | 13 | 0 | 38 | 0 | 1 |
| ml_routes | 23 | 0 | 13 | 0 | 48 | 0 | 1 |
| notification_routes | 13 | 6 | 3 | 0 | 12 | 1 | — |
| signals_routes | 10 | 0 | 3 | 0 | 0 | 3 | — |
| supply_chain_routes | 4 | 0 | 0 | 0 | 0 | 0 | — |
| supply_routes | 7 | 0 | 0 | 0 | 16 | 0 | 1 |
| traceability_routes | 15 | 0 | 3 | 0 | 18 | 1 | — |
| twin_routes | 3 | 0 | 1 | 0 | 0 | 0 | — |
| webhook_routes | 5 | 0 | 7 | 0 | 0 | 0 | — |
| **core/api.py** | 16 | 0 | n/a | 0 | n/a | n/a | — |
| **TOTAL** | **320** | **8 (2.5%)** | 79 | **4 (1.3%)** | 259 (10 routers: zero) | 14 | **17** |

Other inconsistencies: 8 of 25 routers declare no `prefix=` (paths hardcoded per-route); three competing error conventions — `raise HTTPException` (79x), `return {"error": ...}` with HTTP 200 (17x, e.g. `decision_routes.py:27`, `market_routes.py:330`, `supply_routes.py:33`), and `{"status": "not_configured"}` soft states; **96 silent `except Exception: pass/return` swallows across 40+ files in `core/`**. A dead auth stub `def verify_api_key(): return True` sits at `core/api.py:279-281` ("Simplified — add real auth in production") — unused but a foot-gun; delete it.

### The single standard to converge on (effort: 2 days, mostly mechanical)

1. **Error envelope + global handlers** in `core/api.py`:
   ```python
   class ErrorBody(BaseModel):
       error: str            # machine code: "not_found", "upstream_unavailable", "validation"
       detail: str
       request_id: str | None

   @app.exception_handler(Exception)            # 500 + request_id, logged once
   @app.exception_handler(UpstreamUnavailable)  # 503 + Retry-After (new in core/errors.py)
   ```
   Rule: **data-unavailable is HTTP 503, or HTTP 200 with explicit provenance `data_quality="source_unavailable"` — never a bare 200 `{"error": ...}`.** Kill all 17 soft-200s.
2. **Provenance as the response envelope** — `ProvenanceWrapped[T]` exists in TS; add the Pydantic mirror in `core/schemas.py` and adopt on the 40 highest-traffic endpoints first (lice, market, brief, decision, disease).
3. **response_model on every new endpoint** + CI guard: a 10-line pytest introspecting `app.routes` that fails when route count rises but typed-route count doesn't.
4. **Pagination contract**: `limit: int = Query(100, le=1000), offset: int = 0` + `{"items": [...], "total": n}` for every list endpoint (`admin_routes.py:551` is the model citizen; ~14 such params exist platform-wide today).

---

## 5. Performance Bottleneck Profile (measured)

| Operation | Measured | Notes |
|---|---|---|
| `import core.api` (full app, 25 routers) | **0.8 s** | Lazy-import discipline is working |
| `GET /api/health` | 9 ms cold / 3 ms warm | async DB ping fine |
| `GET /api/lice/summary` | 67 ms / 52 ms repeat | Aggregates the 186,139-row table per call — **no caching**; fine on SQLite today, cache candidate at PG scale |
| `GET /api/admin/status` | 6 ms | Served **without auth** (confirmed live in this audit) |
| `GET /api/notifications/alerts` | **1,199 ms** | `check_all()` performs a live SSB HTTP fetch in the request path; the same routine runs per-WS-connection every 30 s |
| bcrypt `checkpw` | **189 ms** | On the event loop per API-key request (`core/auth.py:214`) |
| Full `lice` export materialization (186k rows) | **0.91 s total, ~0.71 s pure CPU**, 12.9 MB CSV | Read-only simulation of `admin_routes.py:449-469`; endpoint is unauthenticated |
| SSB cold fetch | ~1.1 s observed | 6 h TTL cache (`ssb_price_client.py:55-57`), 30 s timeout, **no retry, no stampede lock** |

EXPECTED (not measured): Stripe SDK calls 200–1500 ms blocking; MET.no per-PA forecast similar profile to SSB; foundation-model endpoints dominated by model availability (torch absent locally -> fallback paths).

---

## 6. Resilience — Top 10 Realistic Failure Modes

| # | Failure mode | Handled today? | Evidence | Mitigation (decision) |
|---|---|---|---|---|
| 1 | **Docker prod runs no agents** -> data silently decays; demo shows stale weeks | NO | `Dockerfile:33` gunicorn-only CMD; no agents service in `docker-compose.yml` | Section 2.3 compose service — **the #1 demo killer** |
| 2 | SSB/MET.no outage with cold cache -> 30 s request stalls, no breaker | PARTIAL (6 h TTL cache only) | `ssb_price_client.py:54-57` no tenacity (vs `barentswatch.py:78` which has it); `met_ocean.py:66` same | tenacity (2 retries, 5 s cap) + serve-stale-on-error + single-flight lock; 0.5 day |
| 3 | `/ws/alerts` per-connection duplicate work **and duplicate webhook dispatch** — N dashboards => N identical Slack posts every 30 s and N x 1.2 s engine sweeps | NO | `core/api.py:799-836`: `check_all()` + `webhook_dispatcher.dispatch_alert` run **inside each connection's loop** | Single background producer task computes once per 30 s, broadcasts via the currently-unused `ConnectionManager.broadcast` (`api.py:727`), dispatches webhooks exactly once; 0.5 day |
| 4 | SQLite `database is locked` under concurrent agent writes + API traffic | PARTIAL (WAL set; sync 30 s timeout) | async engine missing busy timeout — `async_db.py:29` (5 s default) vs `models.py:482` (30 s) | One-line `connect_args={"timeout": 30}` |
| 5 | PG connection exhaustion under burst (4 workers x 90 peak conns vs max_connections 100) | NO | `async_db.py:37-38`, `models.py:489-490`, `Dockerfile:35`, no compose override | Section 3.1 pool resize + `max_connections=200` |
| 6 | API-key flood pins the event loop via bcrypt (cheap app-level DoS) — rate-limit key is the *unverified* key string (`api.py:166-168`) so attackers rotate keys to dodge it | NO | `auth.py:213-214`; 189 ms measured per attempt | Section 1.2 to_thread + verified-key cache + fail-fast on malformed prefix |
| 7 | Unauthenticated ops endpoints: `POST /api/cache/invalidate`, `GET /api/admin/export/*` (13 MB / ~1 s CPU each), `GET /api/admin/status` | NO | `api.py:373`, `admin_routes.py:400` (0 auth deps in matrix); 200-without-credentials confirmed in this audit | Admin auth on both routers (extends Session 38 item — the `api.py` cache endpoints were missed there) |
| 8 | Restart logs out everyone mid-demo (ephemeral JWT secret) | NO (known) | Warning observed at import in this audit; `docker-compose.yml:54` defaults to `change-me-in-production` | Session 38 CRITICAL — confirmed still live 2026-06-12 |
| 9 | Migration race / half-migrated schema at boot | NO | `api.py:44-53` all 4 workers race `alembic upgrade head`; failures downgraded to warnings | Section 3.5 migrations to entrypoint; verify-only in lifespan |
| 10 | Memory creep -> 2 GB container OOM-kill | PARTIAL (`--max-requests 10000` recycles workers) | Unbounded caches (`cache.py:40,133`) x4 workers; 12.9 MB export strings; unbounded `chat_agent.conversation_history` (`api.py:577`) | Section 3.2 bounded cache + row-capped/streamed exports |

---

## 7. API Versioning — Decision

**Do not introduce `/api/v2` path versioning now.** There is one first-party client (`frontend/src/lib/api.ts`, 690 lines) plus nascent API-key users; no `/api/v*` prefix exists anywhere (verified). Path-versioning 320 endpoints would double the section-4 consistency problem before fixing it.

**Adopt instead (1.5 days):**
1. **Additive-only contract policy**: fields are added, never renamed/removed/retyped in place; breaking shape changes ship as a new endpoint, with the old one marked `deprecated=True` in the route decorator plus a `Deprecation` response header and a 2-release sunset.
2. **`schema_version` field inside the `ProvenanceWrapped` envelope** (section 4.2) so engine-output evolution is observable per-response without URL churn.
3. **Generate the TS client from OpenAPI** (`openapi-typescript` against `/openapi.json`) and retire the 59 hand-written interfaces in `frontend/src/types/api.ts` as section-4.3 coverage grows — drift becomes a compile error instead of a runtime surprise. This is the real payoff of response_model coverage.
4. Centralize the version string: `core/api.py:82` says "2.2.0" while `/api/metrics` (`api.py:362`) reports "2.1.0" — the two literals already disagree.

---

## 8. Prioritized Action Plan

| Priority | Action | Effort |
|---|---|---|
| P0 | `fishintel-agents` compose service + graceful-shutdown signal handling (2.3) | 1 day |
| P0 | Auth on ops endpoints incl. `api.py` cache endpoints; JWT secret enforcement (with Session 38 work) | 0.5 day |
| P1 | bcrypt off-loop + verified-key cache + last_used throttling (1.2.4) | 0.5 day |
| P1 | Convert 12 sync-session call sites + to_thread Stripe SDK (1.2) | 1 day |
| P1 | `/ws/alerts` single-producer broadcast; webhooks dispatched once (6.3) | 0.5 day |
| P1 | aiosqlite busy timeout; PG pool resize + max_connections (3.1) | 0.25 day |
| P2 | Error envelope + global handlers; kill 17 soft-200s; pagination contract (4) | 2 days |
| P2 | SSB/MET tenacity + serve-stale + single-flight (6.2) | 0.5 day |
| P2 | Bounded cache, single cache class, authenticated invalidation (3.2) | 0.5 day |
| P2 | Lifespan: migrations to entrypoint, fix preload comment, seed-task reference (3.5) | 0.25 day |
| P3 | Remove dead ETag code; un-cache `/api/admin/status` (3.3) | 0.5 day |
| P3 | Versioning policy + OpenAPI-generated TS client pilot on 40 endpoints (7) | 1.5 days |

**Total: ~9 dev-days to a foundation that genuinely holds for 5 years.**

---

*All measurements taken 2026-06-12 on the dev machine (Python 3.14.3, SQLite DB 199 MB / 186,139 lice records). No platform code, config, or tests were modified; the admin-export benchmark was a read-only simulation to avoid writing audit-log rows.*
