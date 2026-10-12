# Changelog

All notable changes to FishIntel / AquaIntel. Format follows the spirit of
Keep a Changelog; versions come from `core/version.py` (single source of truth).

## [Unreleased] — P0-1 backend-backed e2e (2026-10-13)

### Added
- **`e2e-backend` CI job** (`frontend.yml`): spins a fresh seeded SQLite DB
  (`scripts/ci_bootstrap_db.py`) + uvicorn on :8000, then runs the API contract/
  integration specs and the app specs (navigation, golden-path, interactions)
  **blocking** on chromium, 1 worker, with a failure-report artifact.
- `scripts/ci_bootstrap_db.py` — idempotent fresh-runner DB bootstrap (schema +
  demo seed), mirrors the conftest pattern.
- `frontend/e2e/utils.ts` — `suppressOnboarding()` (pre-marks `oc_onboarded` /
  `openclaw_tour_completed`; the first-visit wizard otherwise intercepts pointer
  events on every fresh browser profile). Visual baselines intentionally unaffected.

### Fixed
- **`price_feed_hub._get_ssb_prices`** called non-existent
  `ssb_client.get_latest_prices` (import error) → `/api/futures/forward-curve`
  returned an empty curve forever. Now uses
  `ssb_price_client.get_price_history(n_weeks=260)` + `price_nok`→`price_nok_kg`
  normalization. Verified: 12-point synthetic curve, honest degraded provenance.
- **`ssb_price_client` week-count-agnostic cache** (found by fresh-DB e2e): an
  8-week startup fetch answered the hub's 260-week request for the whole 6 h TTL
  → "Insufficient price history" → empty curve (cached 600 s by the
  `/api/futures/forward-curve` route). Both the fresh-cache and serve-stale
  paths now require the cached request window to cover the incoming request
  (`_cache_requested`); 3 regression tests added.
- **`alembic upgrade head` aborted on fresh databases** (`013_performance_indexes`
  re-created `ix_audit_logs_user_id`/`_action` already created by
  `011_audit_logs`) — the production entrypoint migration step would have failed
  on any brand-new deploy. 013's creates/drops are now index-existence-guarded;
  verified `upgrade head` completes on an empty DB + subprocess regression test
  (`tests/test_migrations.py`).
- **`/market` page** read `.data` from `/api/market/ssb-price-history` (endpoint
  returns `.history`, field `price_nok`) → price chart + spot KPI permanently
  empty. Now mapped correctly; the header DataQualityBadge no longer fabricates
  a 90% confidence figure (classifies live/degraded without invented numbers).
- **`/trader` page** same bug class: spot KPI read `price_nok` (endpoint returns
  `price_nok_kg`) and forward-curve rows read `price_nok`/`price` (hub returns
  `projected_nok_kg`) → permanently "--". Now normalized via `priceOf()`.
- e2e specs aligned with the real contracts: `/api/metrics` JSON shape,
  `/api/market/ssb-price-history`, `/api/leaders/top30`,
  `/api/regulatory/traffic-light/current`; admin block now tests the
  anonymous-401 / non-admin-403 / admin-200 contract (mirrors
  `tests/test_api_routes.py`); fragile selectors (hidden hamburger `.first()`,
  mixed CSS+text click, strict-mode `text=Disease`, PDF-by-text) replaced with
  role/a11y-contract locators; URL race → `toHaveURL()` auto-retry.

## [Unreleased] — Session 41e (2026-10-12, autonomous run, continued)

### Added
- **Blocking visual regression in frontend.yml** with Linux baselines for
  chromium AND mobile (Pixel 5); backend-free e2e scoped separately;
  visual-baselines workflow generates/verifies all projects.

### Fixed
- CI step order: Playwright runs before 
pm run build (the documented
  .next collision corrupts dev assets); dev-server port pinned via
  webServer env; workflow_dispatch added to both frontend workflows.

## [Unreleased] — Session 41d (2026-10-12, autonomous run, continued)

### Added
- **Linux visual baselines** (CI-generated + committed): `visual-baselines.yml`
  workflow_dispatch (update/verify modes, ubuntu + Node 22 + chromium);
  artifact-downloaded `*-chromium-linux.png` snapshots committed; verify run
  green. frontend.yml's e2e step now checks them on every frontend change.
- **F841 in the ruff gate**: all 36 dead locals resolved (pure expressions
  deleted; side-effecting awaits kept as bare statements; PyMC
  `with pm.Model():`). ruff.toml now enforces E9/F821/F811/F401/F841.
- `partialPrefetching: true` — App-Shell prefetch model enabled (skill's
  post-adoption step), verified by instant guard 3/3 + visual baselines 4/4.

### Fixed
- Playwright webServer port: `env: { PORT: 3001 }` pins the dev server
  cross-platform (CI previously timed out on :3000 vs :3001) + 120 s timeout.

## [Unreleased] — Session 41c (2026-10-12, autonomous run, continued)

### Added
- **Instant-navigation regression guard** (`e2e/instant.spec.ts` +
  `playwright.instant.config.ts`; `@next/playwright@16.4.0`): prod-rig
  `instant()` lock around initial loads of `/`, `/market`, `/traffic-light`;
  testing API env-gated (`FISHINTEL_E2E=1`) so it never ships to deployments.
  Differential: GREEN 3/3 on the prod build; RED probe with an empty document
  (non-vacuity proven).
- **5-day wave forecast** (`/api/ocean/waves/pa/{pa}/forecast`): CMEMS WAM
  daily means, separate 6h cache, deterministic simulated fallback; MCP
  `get_wave_risk(..., forecast_days)` now returns `{current, forecast}`.
  LIVE verified: PA-4 0.17/0.20/0.45/0.49/0.41 m over 5 days.
- **ruff CI gate** (`ruff.toml`: E9/F821/F811/F401) + `tests/test_module_imports.py`
  ratchet (every `core/` module must import; empty allowlist).

### Fixed
- `_rule_based_chat_response` NameError — the LICE and SIGNAL chat answer
  branches called an unimported `get_async_session()` (found by ruff F821).
- `core/models.py` missing `asyncio` import; `admin_routes` missing
  `AsyncIterator` import (annotation defects).
- **Two engines broken since creation** (found by the new import ratchet):
  `core/ml/harvest_optimizer` (5 nonexistent names -> `THERMAL_TOLERANCE`,
  `MAX_SGR_PCT`, `_temperature_growth_factor` Q10 helper added to
  biomass_predictor) and `core/valuechain/farmer_advisory` (nonexistent
  `ShortTermForecast` -> real `StageForcast`).
- 128 unused imports removed (F401), 6 availability probes annotated.

## [Unreleased] — Session 41b (2026-10-12, autonomous run, continued)

### Added
- **Tailwind 4.3 migration** (visually verified): `@tailwindcss/postcss`,
  `@import "tailwindcss"` + `@config` compat, v3 border-color base layer,
  class-token renames (outline-hidden ×62, rounded-xs ×12, shadow-xs ×8,
  backdrop-blur-xs ×7, shadow-sm ×1). Gate: 4 committed visual baselines.
- **Visual baselines** — `e2e/visual.spec.ts-snapshots/` (win32 chromium, 4
  routes, deterministic fixtures) + Playwright chromium 1217 installed.
- `.gitignore`: repaired corrupted UTF-16 tail; ignore frontend run artifacts;
  untracked generated root `openapi.json`.

### Changed
- `visual-regression` skill: Session-41 war stories (baseline-first, dry-run
  renames, dev-server/build collision, separate commits for baselines vs
  migration).

## [Unreleased] — Session 41 (2026-10-12, autonomous run)

### Added
- **Next.js 16.4 upgrade** (Turbopack builds, 68/68 routes) + ESLint 9 flat
  config (eslint-config-next@16 native arrays); CI frontend job now runs
  `tsc --noEmit` + `lint` on Node 22.
- **TanStack Query v5** — dashboard data layer (14 `useQuery` resources,
  dedupe/stale-while-revalidate/retry, same return contract).
- **ECharts 6** — `OceanAreaChart` rebuilt on echarts 6.1 with lean module
  registration and an identical props contract (dashboard + twin unchanged).
- **CMEMS wave client** (`core/market/wave_client.py`, F2) — WAM
  GLOBAL_ANALYSISFORECAST_WAV_001_027 live per-PA significant wave height +
  operational risk bands; routes `/api/ocean/waves/{status,pa/{pa}}`; MCP
  `get_wave_risk` (7 tools). Deterministic simulated fallback w/ `is_live=false`.
- **OpenAPI drift guard** — `docs/openapi.frozen.json` (314 paths) +
  `tests/test_openapi_contract.py` + `scripts/freeze_openapi.py`.
- **Deterministic visual-regression spec** `frontend/e2e/visual.spec.ts`
  (all `/api/**` stubbed) — the gate for the Tailwind 4 migration.
- `docs/AUTONOMOUS_PROGRESS.md` — full session log and next priorities.

### Changed
- CI: Frontend Build added type-check + lint steps; Node 20 → 22 LTS.
- Generated TS client regenerated for 326 routes; eslint baseline 0 errors.

## [Unreleased] — Session 40 (2026-10-12)

### Added
- **CI is green for the first time**: Backend Tests + Docker Build both pass on
  `master`. The trigger fix (main→master), dependency split, build-time DB
  bootstrapping, fastapi pinning and the metrics-path fix are all in this list;
  the history is in the commit log (`835cdd6`..`3e733cc`).
- `core/version.py` — single version source (PLATFORM_VERSION, API_SCHEMA_VERSION);
  provenance envelopes now carry `schema_version` (arch report §7.2).
- `requirements-models.txt` — heavy foundation-model stack split out of
  `requirements.txt` (~2 GB lighter default install and Docker image).
- Router decomposition: `misc_routes.py` → `feed_cost_routes`, `ocean_routes`,
  `macro_routes`, `causal_routes`, `ras_routes` (57 routes preserved verbatim,
  mechanically verified old ≡ new); 16 structural tests.
- `response_model` wave 1 (4 new exact schemas; typed routes 8 → 12) +
  `TYPED_ROUTE_FLOOR` CI ratchet test.
- `core/pagination.py` (PageParams/paginate) + all 11 unbounded `limit` params
  Query-bounded (le ≤ 1000 / 10000 / 50000 where justified).
- **`core/satellite/cdse_client.py`** — pure-httpx CDSE Sentinel-2 client
  (OAuth token cache + Statistical API); `sentinelhub` C-dependency stack
  retired; `config/settings.py` gains `sentinel_hub_client_*` fields.
- **`core/mcp_server.py`** — FishIntel exposed as an MCP server (6 tools:
  morning brief, price outlook, lice summary, causal insights, feed cost,
  traffic-light) for external AI agents.
- **`frontend/src/types/generated.ts`** — OpenAPI-generated TypeScript types
  (openapi-typescript 7.13); `npm run gen:api` workflow documented in
  REPORT_STACK.md.
- `scripts/firecrawl_research.py` research helper; `docs/MCP_SETUP.md`;
  project `.mcp.json`; 4 new project skills (engine-audit, release,
  satellite-research, visual-regression); ecosystem skills installed.
- Research: `docs/summit/REPORT_SATELLITE.md` (verified quotas + cost path),
  `REPORT_STACK.md` (2026 versions), `docs/raw/` source captures.

### Fixed
- Missing-await bug class burn-down: biomass outlook/scenarios (+ scenario
  cache-key collision), GNN training data, LLM farm-network tool, federated
  benchmark (endpoints were fully dead), pairs engine overlay chain, ESG getters,
  morning brief (sync Session + wrong method + Bloom section), resistance tracker.
- **ocean_currents phantom product**: `NORSHELFS_ANALYSISFORECAST_PHY_003_058`
  does not exist in the CMEMS catalogue (verified live: norkyst/norshelf →
  NO MATCH — NorKyst800 is MET.no-only); repointed to
  `cmems_mod_glo_phy_anfc_0.083deg_P1D-m`.
- Admin exports now stream (CSV/JSON generators) — 186k-row export no longer
  materializes ~13 MB in memory; audit logs `streamed=true`.
- `/api/lice/summary` TTL-cached: 70 ms → 2 ms warm (35×) on the 186k-row aggregate.
- API keys: malformed keys fail fast before DB/bcrypt; `last_used` write
  throttled to 60 s.
- Chat agent conversation history bounded (200 entries).
- Migrations run once in `scripts/docker-entrypoint.sh` before gunicorn workers
  (`FISHINTEL_RUN_MIGRATIONS=0`); `docs/DEPLOYMENT.md` documents the flow.
- CI hardening: fresh-runner DB bootstrap in conftest (schema + demo seed),
  production-scale tests skip below 10k lice rows, SQLite parent dir auto-created,
  `/api/metrics` single-owner (Prometheus text moved to `/api/metrics/prometheus`).
- Docker entrypoint LF-normalized; `.gitattributes` already enforces this.

### Changed
- `PROJECT_STATUS.md` stats refreshed; version literals centralized.
- `.mcp.json` project config (firecrawl/playwright/context7/planet-docs).

## [2.2.0] — pre-Session-40 baseline
- 324 routes, 30 routers, 605+ tests baseline with prior sessions' hardening
  (error envelope, bounded caches, SSB/MET resilience, WS single-producer).
