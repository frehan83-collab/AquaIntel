# AquaIntel — Next Steps Execution Plan (handoff for coding agent)

> Generated: 2026-10-12 · Local clone: `C:\Users\freha\AquaIntel` · Branch: `master` (clean tree at `0ba29e3`)
> This document is a self-contained brief for any coding agent. Read it together with
> `AGENTS.md` (authoritative rules) and `docs/AUTONOMOUS_PROGRESS.md` (session history).

---

## 1. What this project is

AquaIntel (legacy names: OpenClaw / FishIntel) — a "Bloomberg Terminal for Salmon":
a salmon aquaculture intelligence platform for Norwegian farmers, traders, and analysts.

| Dimension | Current state |
|---|---|
| Backend | FastAPI 2.2.0, ~328 routes, 30 router modules (`core/routers/`) |
| Engines | ~75 data/market engines (`core/market/`, `core/valuechain/`, etc.) + 3 ML foundation models (TimesFM 2.5, Chronos-2, MOIRAI-2) with **honest** seasonal-naive fallbacks |
| Frontend | Next.js 16.4 (Turbopack), React 19, TanStack Query v5, ECharts 6, Tailwind 4.3, 68 compiled routes |
| Data | 45+ live clients (BarentsWatch, SSB, FRED, MET.no, CMEMS, NASA MUR/PACE, NorKyst, SEPA, Sernapesca, DFO, EUMOFA, Euronext ESF futures, …), 7-country coverage |
| DB | 31 tables, 14 Alembic migrations; SQLite dev / PostgreSQL+TimescaleDB prod |
| Tests | ~650 pytest (616 pass, 35 xfail/xpass), Hypothesis property tests, Playwright E2E + visual regression (chromium + mobile Linux baselines, **blocking** in CI) |
| Quality gates | ruff ratchet (E9/F821/F811/F401/F841), `tsc --noEmit` = 0 errors, module-import ratchet (empty allowlist), typed-route floor, OpenAPI drift check |
| CI | 4 workflows: `test.yml`, `frontend.yml`, `docker.yml`, `visual-baselines.yml`; GHCR publishing |
| Extras | MCP server (7 tools), 12 background agents, i18n NO/EN ~600 keys, 86 design tokens (Figma pipeline) |

## 2. Goals (why this exists)

- **Product vision** (`docs/strategic_roadmap.md`): the first real-time algorithmic supply
  intelligence platform for salmon. Revenue target 10–40M NOK ARR from traders, then farmers,
  transporters, processors.
- **The "Holy Grail" model**: integrated supply–demand balance (Norwegian biomass PA 1–13,
  Chile/Scotland/Faroe production, lice-driven harvest delays vs EU/Asia/US demand) →
  price forecast with 2–20 week horizon and uncertainty bands.
- **Monetization** (shipped foundations): subscription tiers, performance fees (20%),
  premium signal tier.
- **Non-negotiables** (from `AGENTS.md`, rule source of truth):
  1. Honesty layer — never fabricate data/accuracy; fallback ML results must surface as
     `DataProvenance.degraded`; report `models_used` vs `models_fallback` truthfully.
  2. Security — admin-only for `/api/admin/*` and `/api/cache/*`; ownership checks vs token
     user (no IDOR); SSRF guard on webhooks at create **and** dispatch; prod refuses weak
     `FISHINTEL_JWT_SECRET`.
  3. Live data only, traceable sources on every number shown to users.
  4. Surgical diffs; follow existing patterns (singleton engine + `@cached` +
     `DataProvenance` + `structlog`).
  5. Verify after every change; independent code review of the diff before commit.
  6. Update `AGENTS.md`/`CLAUDE.md` after structural changes.
- **Frozen modules** (do not extend): `pairs_engine.py`, `regime_detector.py`,
  `satellite_engine.py`, `self_evolve.py`.

## 3. Known operational gaps (check before assuming)

- Production Docker CMD runs **API only** (`gunicorn core.api:app`); agents need
  `python main.py --agents-only` as a separate service (see `docs/DEPLOYMENT.md`).
- `FISHINTEL_ENV=production` + SQLite is rejected by `config/settings.py`.
- Foundation models require the `requirements-models.txt` stack (torch etc.); without them
  everything falls back to seasonal-naive with `is_live: false` (this is by design).
- Local dev SQLite may lag the ORM (`create_all` vs Alembic) → `no such column` means
  reconcile with `PRAGMA table_info` + `ALTER TABLE`.
- Local machine: **Python 3.14.3** (docs say 3.11+; ML stack compatibility unverified on
  3.14 — see workstream 4), Node 24.13.1, npm 11.11.0, Windows.
- Ports: backend 8000 (some docs say 8001 — check `frontend/.env.local`); frontend
  3000/3001/3002 per env/config.
- Command runner timeout ~30 s: start long pytest runs with
  `Start-Process ... -RedirectStandardOutput` and poll the log file.
- CI lesson (41e): Playwright steps MUST run before `npm run build` (`.next` collision).

## 4. Workstreams (prioritized)

### P0-1 · Backend-backed e2e in CI — ✅ DONE (local-verified; CI proof pending push)
**Why:** `api-*.spec.ts` and navigation specs are currently skipped/tolerated in CI because
no FastAPI is running. The project's own #1 remaining priority (41e).
- In `.github/workflows/frontend.yml`, add a service/job step that starts
  `python -m uvicorn core.api:app --port 8000` with a seeded SQLite DB
  (see `conftest.py` bootstrap pattern), then run the backend-dependent Playwright specs.
- Un-tolerate (`continue-on-error` → blocking) navigation specs once green for ≥3 CI runs.
- Acceptance: full e2e suite (incl. api-*) green on CI; no `.next` build-order regression.

**Status (2026-10-13): ✅ COMPLETE — CI-PROVEN.**
New `e2e-backend` job in `frontend.yml` (needs: build; Python 3.12 + `scripts/ci_bootstrap_db.py`
+ uvicorn health-wait; api specs 120s/1 worker, app specs 60s/1 worker, both BLOCKING,
html report artifact on failure; instant-rig step added in P0-3).
Local: all 39 api specs + all 49 app specs green (incl. fresh-seeded-DB run).
CI (commit 8fca76b, Frontend Build run 38317892995): build job ✅ (incl. blocking visual
baselines), **e2e-backend job ✅ — API specs step ✅, app specs step ✅** on a fresh
ubuntu runner. Backend Tests run ✅ and Docker Build ✅ on the same commit. 8 stale
specs fixed to the real contracts; admin block rewritten to the pytest 401/403/200
security contract; 2 real bugs fixed (price_feed_hub dead import; /market ssb binding).

### P0-2 · DuckDB read path for lice analytics — ✅ CLOSED with evidence (2026-10-13, RUN-1 R5+R6)
**Why:** 189k-row lice aggregate; TTL cache gives 70 ms → 2 ms warm, but analytics are
still SQLite/PG. DuckDB is the project's stated next step for this path.
- Add `duckdb` (or `duckdb-engine`) behind the existing lice analytics queries; keep the
  current code path as fallback.
- Gate: keep `test_lice_*`/`test_api_routes.py` green; add provenance to the new path.

**Findings (measured on the real 189k-row dev DB, duckdb 1.5.6, Python 3.14):**
1. The only DuckDB setup that could beat SQL here is the **sqlite_scanner extension**
   (ATTACH the SQLite file). It is **blocked on this Windows box by an application-control
   policy** ("Extension ... could not be loaded: En programkontrollpolicy har blokkert
   denne filen") — locally unverifiable.
2. The extension-free alternative (fetch rows → load into DuckDB → aggregate) measured
   **~220 ms vs 47 ms** for the current 4-query SQLAlchemy path on the latest-week
   aggregate (row-load dominates). Implementing it would be a slowdown with no user value.
3. `duckdb` 1.5.6 has cp314 wheels (installs fine), so the blocker is the extension policy,
   not the package.

**Resolution:** do not ship a DuckDB path until it can be validated end-to-end (Linux dev
env or CI) against a real workload. Revisit with either (a) sqlite_scanner verified on
Linux, or (b) a parquet materialization of lice history once an export pipeline exists.

**CLOSED (2026-10-13, RUN-1 R5+R6)** — validated end-to-end on BOTH platforms with
`scripts/bench_lice_read.py` (186,139 rows, warm, median over N runs, identical summaries
across all candidates): **Linux** (python:3.12-slim container, DB staged in a named volume
to bypass the Docker-for-Windows mount bridge): sqlite **19.4 ms** vs DuckDB sqlite_scanner
**80.2 ms (4.1× slower)** vs row-load-latest 180.4 ms vs full row-load (aborted after
minutes; Windows: 3.6 s/run). **Windows**: 30.0 / 78.8 / 12.6 ms. DuckDB does not meet the
≥1.5× gate on this workload → **no DuckDB read path will ship** (the old Windows
extension-app-control blocker did not even reproduce today — the decision no longer
depends on it). The real read-path cost was a **missing index**: `/api/lice/summary`
filters `lice_records (year, week)` with no matching index → three full scans of 186k rows
+ a temp b-tree sort. **Alembic 015** now ships `ix_lice_year_week (year, week)`
(existence-guarded; model declares it for create_all parity) — EXPLAIN QUERY PLAN:
`SCAN lice_records` → `SEARCH ... USING INDEX (year=? AND week=?)`; the summary read path
drops from 19–30 ms warm to <0.1 ms. Latency-sweep note: the e2e-flagged slow route
(Scotland snapshot ~25 s) is a cold-cache external fetch — measured 25,695 ms cold →
9 ms warm with the existing `@cached(ttl=900)`; network-bound, no DB fix applies.
No requirements/code changes made (no fake value, per AGENTS.md honesty rule).

### P0-3 · Cache Components `use cache` scoping — ✅ DONE (audit + extended guard, 2026-10-13)
**Why:** Next.js 16 supports `use cache`; project wants it where server-renderable data
appears (skill: `next-cache-components-optimizer` is available).
- Identify server-renderable data routes; add `use cache`/Suspense scoping per route.
- Verify with the instant-navigation guard (`npm run test:instant`) and visual baselines.

**Findings & outcome (via the `next-cache-components-optimizer` skill):**
1. `cacheComponents: true` + `partialPrefetching: true` are already adopted (Session 41),
   and the three existing `instant()` locks (/, /market, /traffic-light) were green.
2. Audit result: there are **no server-renderable data routes** — every page is a
   `"use client"` component fetching via TanStack Query; the only server components
   (layout/loading/not-found) are pure static shells with no data fetching. Adding
   `use cache` scopes would require converting client pages to server components — an
   architecture change out of scope; correctness/no-fake-value rules apply.
3. Correct deliverable per the skill (grow the static-shell guarantee, one verified
   route at a time): **extend the instant-navigation lock** to 8 more key routes
   (/brief, /farmer-daily, /disease, /leaders, /futures, /feed-cost, /global-supply,
   /notifications). Verified locally on the prod rig: **11/11 instant tests green**;
   the rig now runs as a blocking CI step in the `e2e-backend` job.
**Deferred:** per-route `use cache` conversion (needs a server-data architecture first).

### P0-4 · uv adoption
**Why:** REPORT_STACK #7 remainder; Python 3.14 locally vs the heavy ML stack.
- Add `pyproject.toml` with locked deps (`uv lock`), split base vs `requirements-models.txt`.
- Pin the Python version CI/Docker use (3.12 is safest for torch; validate 3.14).
- CI: `uv sync` in `test.yml` + Docker build; keep `requirements.txt` in sync or retire it.
- Acceptance: CI green under uv; dev setup documented in README/AGENTS.md.

### P1-5 · Local environment verification & test hygiene — ✅ DONE (2026-10-13)
- Run the full suite on Windows/Python 3.14: `python -m pytest tests/ -q`.
  (Execution policy note: use `python -m pytest`, not bare `pytest`.)
- Investigate the 35 xfail/xpass: convert to real passes (bugfix + test) or justify.
- Run `python scripts/smoke_security.py` and `python scripts/preflight_audit.py`.
**Outcome:**
- Full suite on Windows/Py3.14: **639 passed, 13 xfailed, 22 xpassed, 0 failed**
  (4:11); `ruff` clean on all touched modules; `tsc --noEmit` clean;
  `scripts/smoke_security.py` all checks pass.
- xfail/xpass triage (`-rX` listing): the 12 XPASSes in `test_api_routes.py` were
  **stale migration-lag guards** (dev-SQLite schema drift — solved platform-wide by
  the migrations-first bootstrap + `tests/test_migrations.py`) plus the TimesFM
  "may not be installed" marker (the endpoint's honest seasonal-naive fallback
  satisfies the test regardless). **12 markers removed** (exactly those; verified by
  diff). Kept + justified: genuine external-data guards
  (DFO/Sernapesca/Scotland/Hagstova/Iceland/FRED-live fetches in
  `test_all_engines.py`/`test_critical_engines.py`) and async-design quirks
  (benchmark/ESG `compute_all` calling async internals — `test_engines.py`,
  `test_all_engines.py`); the 7 remaining `test_api_routes.py` xfails are the
  audit_logs/resistance-column/insurance/contracts env-dependent set.

### P1-6 · Production parity gaps — ✅ MOSTLY DONE (verified 2026-10-13)
- Add an agents service to docker-compose/prod deployment (`python main.py --agents-only`)
  so the 12 agents run in prod, not just the API.
- Reconcile `create_all` vs Alembic for local dev (or document `alembic upgrade head` as
  the only path) to kill the `no such column` class of bugs.
**Verified/outcome:** `docker-compose.yml` already ships `fishintel-agents`
(`command: python main.py --agents-only`, graceful SIGTERM, own resource limits) — the
"agents absent from prod" gap was already closed in-repo. Fresh-DB `alembic upgrade head`
is now validated in three places: `scripts/ci_bootstrap_db.py` (migrations-first), the
Docker entrypoint (verified live during P0-4: migrations OK → gunicorn → healthy), and
`tests/test_migrations.py`. Remaining nicety: point local-dev docs at `alembic upgrade
head` as the canonical schema path.

### P1-7 · Strategic roadmap verification (Tier 1) — ✅ DONE (audited + live-verified 2026-10-13)
`ADVANCED_ROADMAP.md` Tier-1 features are mostly reported "Shipped" in PROJECT_STATUS.md.
**Audit each against reality**, then close the gaps:
1. Feed Cost Index — margin-squeeze alert (feed up + salmon price down) — verify live.
2. Weather/ocean forecast overlay → 7-day sea temp per farm → lice growth model (Stige
   inputs) — MET.no is shipped; verify the forecast→lice-model wiring exists end to end.
3. ESG/sustainability score per company (lice perf, treatment frequency, mortality, cleaner
   fish) with peer benchmark + trend.
4. Harvest intelligence (AIS wellboat → treatment/harvest inference, 48–72h supply warning).
**Audit result (code inspection + live endpoint evidence):**
1. Live: `/api/feed-cost/latest` computes the full margin stack (feed cost/kg salmon,
   production cost, salmon spot, `margin_pct`, `margin_trend` incl. "squeezing"
   detection); `/api/feed-cost/alerts` present. ✅
2. `decision_engine.get_decision()` pulls `met_ocean.get_ocean_forecast` and overrides
   stale DB sea-temp before the lice action + SHAP-style importance; forecast also feeds
   contract-risk, welfare scorer, ocean routes. ✅
3. Live: `/api/esg/scores` returns genuinely computed scores with full component
   breakdown; sample: SALMAR rank 1, 92.0 (A+), 41 localities / 7 PAs. ✅
4. Live: `/api/ais/harvest-intelligence` returns vessels, supply/treatment pressure,
   72h harvest & treatment signals, price signal + rationale; consumed by /market. ✅
**No code gaps found in Tier-1 — audit closes without changes.**

### P2-8 · Strategic roadmap Tier 2 — ✅ DONE (verified shipped 2026-10-13)
- Multi-country supply model (Norway+Chile+Scotland+Canada) with disruption alerts.
- Contract risk analyzer for buyers (fixed-price contracts vs forward curve).
- Treatment cost optimizer (mechanical vs thermal vs medicinal vs cleaner fish ROI).
- Investor portfolio exposure dashboard (portfolio-weighted lice risk per MOWI/SALM/LSG).
**Verification (engines + route exposure):** all four already exist end-to-end —
contracts: `contract_risk_engine.py` (incl. `PortfolioRisk`) exposed via
`POST /api/contracts/evaluate`, `POST /api/contracts/portfolio`,
`GET /api/contracts/hedge-signals`, plus `/api/regime/company-risk`; treatment
optimizer: `decision_routes.py` suite (`/api/treatment/optimize|compare|
network-schedule|cost-benefit|cost-comparison|history|efficacy-by-method|
log-outcome`); investor portfolio: `/api/decision/portfolio/{company}` +
`investor_routes` event-impact/scenario endpoints; multi-country supply:
per-country monitors (Chile/Canada/Iceland/Faroe/Scotland) with disruption levels
+ `/api/global-supply` (disruption_pct). No build work required.

### P2-9 · Honesty & security audit — ✅ DONE (clean, 2026-10-13)
- Audit every ML endpoint for `DataProvenance.degraded` on `*-fallback` results and
  truthful `models_used`/`models_fallback` reporting.
- Audit `core/security.py` webhook re-validation at dispatch time; IDOR checks on
  user-scoped resources.
**Audit result (code inspection + live checks — no gaps found):**
- SSRF: `core/security.py` blocks forbidden hosts/suffixes, literal + inet_aton
  shorthand IPs, resolves DNS and requires EVERY address to be public (fail-closed);
  `webhook_dispatcher.send_to_webhook` re-validates `validate_public_url` at dispatch
  time (rebinding defense) and webhook routes re-validate on test-dispatch; ownership
  is enforced from the token user (create/delete/test), IDOR-fixed.
- IDOR spot-check: `apikey_routes` scopes list/create/revoke strictly by
  `u.user_id`; admin contract 401/403/200 is CI-enforced by the new e2e admin block;
  `scripts/smoke_security.py` (escalation/SSRF/admin) passes.
- Honesty: every ML route result is tagged via
  `DataProvenance.from_model_result` (fallback/`fallback_members` → degraded);
  the ensemble endpoint reports `models_used` vs `models_fallback` truthfully and is
  live only when ≥1 real model ran (verified at `ml_routes.py` ensemble).

## 5. Commands cheat sheet (for the agent)

```bash
cd C:\Users\freha\AquaIntel

# Backend
python -m uvicorn core.api:app --port 8000          # API only
python main.py --api-only
python main.py --agents-only

# Tests (Windows: use python -m; long runs → Start-Process + poll)
python -m pytest tests/test_critical_engines.py -q   # fast smoke ~8s
python -m pytest tests/ -q                           # full suite (long)
python scripts/smoke_security.py

# Frontend
cd frontend && npm install
npx tsc --noEmit                  # must be 0 errors
npm run lint                      # 0 errors (warnings tolerated for now)
npm run build
npx playwright test               # e2e
npm run test:instant              # instant-navigation guard
npm run tokens:verify             # design token pipeline

# Before commit
git diff                          # stage ONLY touched files (never .coverage/*.docx)
python -m pytest <touched test files> -q
python -m pytest tests/ -q
npx tsc --noEmit                  # if frontend touched
# independent code-review subagent on the diff
git push origin master
```

## 6. Definition of done (per workstream)

- Feature/bugfix works end to end (manual or test proof), with provenance/fallback honesty.
- New tests added; full pytest suite green; `tsc --noEmit` 0 errors; ruff ratchet intact.
- CI green for the touched workflow(s).
- Docs updated: `CHANGELOG.md`, `AGENTS.md`/`CLAUDE.md` if structural,
  `docs/AUTONOMOUS_PROGRESS.md` session entry.

## 7. Suggested sequencing (3 sprints) — ✅ COMPLETE (2026-10-13)

1. **Sprint A (stabilize):** P0-4 (uv) → P1-5 (local env + test hygiene) → P0-1 (e2e in CI).
   ✅ Done — CI-proven (runs 38317892995, 38319321808: build + e2e-backend + backend + docker all green).
2. **Sprint B (performance + quality):** P0-2 (DuckDB) → P0-3 (use cache) → P1-6 (prod parity).
   P0-2 closed-with-evidence (RUN-1 R5+R6); P0-3 done (instant lock ×11, CI-wired); P1-6 verified done-except-doc-nicety.
3. **Sprint C (product):** P1-7 Tier-1 audit → P2-8 → P2-9.
   ✅ Audits complete, all features verified shipped; no gaps to build.

## 8. Risks & gotchas

- Python 3.14 may not support the full ML stack → pin 3.12 via uv and Docker.
- Visual baselines are Linux-generated; Windows-generated screenshots will mismatch —
  always regenerate baselines via the `visual-baselines.yml` workflow (`update=true`),
  never locally on Windows.
- Workflow-file changes don't match `frontend/**` path filters → keep `workflow_dispatch`
  on frontend workflows.
- Frozen modules must not be extended; structural changes to routers/engines require
  updating the import ratchet test allowlist (currently empty) and `AGENTS.md` map.
- Don't trust docs that say Next 15.5/React 19.1: actual pinned versions are in
  `frontend/package.json` (Next 16.4) and `core/version.py`.

## 9. Post-plan follow-up sweep (2026-10-13)

Status of the four follow-ups handed off at plan exhaustion (§7):

1. ✅ `frontend.yml` paths filter — extended to the backend surfaces the
   `e2e-backend` job boots (`core/**`, `agents/**`, `config/**`, `alembic*`,
   `main.py`, dependency manifests, the two scripts it runs, the workflow file
   itself). Backend-only changes now exercise the real e2e contract.
2. ✅ `/market` futures card — repointed from `/api/market/futures-curve`
   (returns SSB `.history`; the page read `.curve` → permanently empty) to the
   real `/api/futures/forward-curve`, with an `is_synthetic`-aware badge
   ("Fish Pool" ↔ "SSB synthetic").
3. ✅ P0-2 DuckDB — CLOSED (RUN-1 R5/R6): no portable DuckDB win on either
   platform (Linux 19.4 vs 80.2 ms); the missing `(year, week)` index shipped
   as Alembic 015 instead.
4. ✅ seasonal-card explicit empty state — plus the underlying binding fix
   (`.data` → `.seasonal_pattern`, week→median dict) and an honesty relabel
   (the endpoint computes medians, not averages).

Bonus same-class finds during live verification (fixed, honest relabels):
- macro series names (`FRED_USDNOK`/`FRED_WTI_OIL` → `nok_usd`/`brent_crude`;
  both cards had 404'd since inception) and WTI→Brent (no WTI series exists in
  `macro_intelligence.FRED_SERIES`; the banner ticker now says "Brent $…").
- `/investor` Macro Environment card (found by the pre-commit review, same
  cluster): invalid series names (`FRED_SOYBEAN` → `soybeans` too), "WTI Crude
  Oil" labelling Brent data, `$/bu` on a USD/tonne series, and a fabricated
  **$0.00** fallback — labels/units now match the registry, failures render
  "—" + "FRED series unavailable".
- `FuturesForwardCurve` in `frontend/src/types/api.ts` was a stale contract;
  now mirrors `euronext_futures.get_forward_curve` and is consumed typed by
  the /market page.
- Review hardening: seasonal heading "Weekly Average" → "Weekly Median"; Fish
  Pool badge renders only with a curve and only when `is_synthetic === false`
  (fail-safe — unknown payloads read "SSB synthetic"); empty-state strings
  assert no unverified causes.

Evidence (live local rig — uvicorn + `next dev` + headless chromium on
/market and /investor): 52/52 seasonal bars from real SSB medians; 12-month
curve renders with the synthetic badge; NOK/USD 9.64 · Brent $83.73 ·
Soybeans $442.45/t (FRED live); 0 console errors / 0 failed requests;
`tsc --noEmit` + eslint 0 errors; pytest 651 passed / 13 xfailed / 10 xpassed
/ 0 failed.



