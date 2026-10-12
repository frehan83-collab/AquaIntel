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

**Status (2026-10-13):** new `e2e-backend` job added to `frontend.yml` (needs: build;
Python 3.12 + `scripts/ci_bootstrap_db.py` + uvicorn health-wait; api specs 120s/1 worker,
app specs 60s/1 worker, both BLOCKING, html report artifact on failure).
All 39 api specs + all 49 app specs green locally (incl. fresh-seeded-DB run); 8 stale
specs fixed to the real contracts; admin block rewritten to the pytest 401/403/200
security contract; 2 real bugs fixed (price_feed_hub dead import; /market ssb binding).
**Remaining:** push + confirm the CI run itself goes green; keep the whole-file suite
stable for 3 runs before any further promotion/cleanup.

### P0-2 · DuckDB read path for lice analytics
**Why:** 189k-row lice aggregate; TTL cache gives 70 ms → 2 ms warm, but analytics are
still SQLite/PG. DuckDB is the project's stated next step for this path.
- Add `duckdb` (or `duckdb-engine`) behind the existing lice analytics queries; keep the
  current code path as fallback.
- Gate: keep `test_lice_*`/`test_api_routes.py` green; add provenance to the new path.

### P0-3 · Cache Components `use cache` scoping
**Why:** Next.js 16 supports `use cache`; project wants it where server-renderable data
appears (skill: `next-cache-components-optimizer` is available).
- Identify server-renderable data routes; add `use cache`/Suspense scoping per route.
- Verify with the instant-navigation guard (`npm run test:instant`) and visual baselines.

### P0-4 · uv adoption
**Why:** REPORT_STACK #7 remainder; Python 3.14 locally vs the heavy ML stack.
- Add `pyproject.toml` with locked deps (`uv lock`), split base vs `requirements-models.txt`.
- Pin the Python version CI/Docker use (3.12 is safest for torch; validate 3.14).
- CI: `uv sync` in `test.yml` + Docker build; keep `requirements.txt` in sync or retire it.
- Acceptance: CI green under uv; dev setup documented in README/AGENTS.md.

### P1-5 · Local environment verification & test hygiene
- Run the full suite on Windows/Python 3.14: `python -m pytest tests/ -q`.
  (Execution policy note: use `python -m pytest`, not bare `pytest`.)
- Investigate the 35 xfail/xpass: convert to real passes (bugfix + test) or justify.
- Run `python scripts/smoke_security.py` and `python scripts/preflight_audit.py`.

### P1-6 · Production parity gaps
- Add an agents service to docker-compose/prod deployment (`python main.py --agents-only`)
  so the 12 agents run in prod, not just the API.
- Reconcile `create_all` vs Alembic for local dev (or document `alembic upgrade head` as
  the only path) to kill the `no such column` class of bugs.

### P1-7 · Strategic roadmap verification (Tier 1)
`ADVANCED_ROADMAP.md` Tier-1 features are mostly reported "Shipped" in PROJECT_STATUS.md.
**Audit each against reality**, then close the gaps:
1. Feed Cost Index — margin-squeeze alert (feed up + salmon price down) — verify live.
2. Weather/ocean forecast overlay → 7-day sea temp per farm → lice growth model (Stige
   inputs) — MET.no is shipped; verify the forecast→lice-model wiring exists end to end.
3. ESG/sustainability score per company (lice perf, treatment frequency, mortality, cleaner
   fish) with peer benchmark + trend.
4. Harvest intelligence (AIS wellboat → treatment/harvest inference, 48–72h supply warning).

### P2-8 · Strategic roadmap Tier 2 (choose 1–2)
- Multi-country supply model (Norway+Chile+Scotland+Canada) with disruption alerts.
- Contract risk analyzer for buyers (fixed-price contracts vs forward curve).
- Treatment cost optimizer (mechanical vs thermal vs medicinal vs cleaner fish ROI).
- Investor portfolio exposure dashboard (portfolio-weighted lice risk per MOWI/SALM/LSG).

### P2-9 · Honesty & security audit
- Audit every ML endpoint for `DataProvenance.degraded` on `*-fallback` results and
  truthful `models_used`/`models_fallback` reporting.
- Audit `core/security.py` webhook re-validation at dispatch time; IDOR checks on
  user-scoped resources.

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

## 7. Suggested sequencing (3 sprints)

1. **Sprint A (stabilize):** P0-4 (uv) → P1-5 (local env + test hygiene) → P0-1 (e2e in CI).
2. **Sprint B (performance + quality):** P0-2 (DuckDB) → P0-3 (use cache) → P1-6 (prod parity).
3. **Sprint C (product):** P1-7 Tier-1 audit/gaps → P2-8 pick 1–2 → P2-9 audits.

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


