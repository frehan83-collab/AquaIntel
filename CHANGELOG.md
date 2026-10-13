# Changelog

All notable changes to FishIntel / AquaIntel. Format follows the spirit of
Keep a Changelog; versions come from `core/version.py` (single source of truth).

## [Unreleased] — post-review hardening session (2026-10-13)

### Fixed (review H1 — rate limiting was configured but never enforced)
- `core/api.py` now registers `SlowAPIMiddleware`: the `Limiter` (default
  `200/minute`, moving-window) previously existed alongside the 429
  handler but was never wired — zero routes were actually limited.
- The middleware is registered **before** `CORSMiddleware` (later
  `add_middleware` calls wrap earlier ones), so CORS stays outermost and
  429 responses still carry CORS + security + correlation headers.
- `headers_enabled=True`: `X-RateLimit-*` + `Retry-After` are now emitted
  so API clients can self-throttle.
- Default limit is env-tunable (`FISHINTEL_RATE_LIMIT`, default
  `200/minute`) — no code change needed for load testing.
- New `tests/test_rate_limit.py` (9 tests): middleware-wiring regression
  net, burst → 429, 429 body + rate-limit headers, 429 keeps outer
  middleware headers, per-key bucket isolation, `_get_rate_limit_key`
  bucketing (X-API-Key / bad-Bearer-falls-back-to-IP / anonymous IP).
- Test-suite/CI safety: `tests/conftest.py` raises the limit before
  `core.api` import (the suite makes ~240 requests from one TestClient
  IP); `FISHINTEL_RATE_LIMIT` added to the `test.yml` pytest step and the
  `frontend.yml` e2e backend. Production default stays 200/minute.

### Fixed (review H2 — tier/paywall claims without enforcement)
- New `core/tier_quota.py` + `TierQuotaMiddleware` (registered in
  `core/api.py`): `TIERS[tier]["api_calls_per_day"]` is now actually
  enforced for authenticated API usage (Bearer JWT or X-API-Key) with a
  structured 429 (`tier_quota_exceeded`, tier, quota, `Retry-After`) once
  the per-UTC-day allowance is exhausted. Per-user buckets;
  `/api/auth/*`, `/api/health`, `/api/billing/*` never consume quota;
  unknown/`<= 0` quotas mean unlimited; kill-switch
  `FISHINTEL_ENFORCE_QUOTAS=0` (on by default in production).
- Honest scope, explicitly documented everywhere: anonymous "public
  demo" traffic is NOT quota-gated (the site stays publicly browsable
  under the global rate limiter), and route-level tier gating (TIERS
  route allow-lists) is NOT enforced yet.
- Honest tier surfaces: `/api/auth/tiers` and `/api/tiers` now report
  `daily_quota_enforced: true` and `route_gating_enforced: false` per
  tier (additive; `/api/tiers` also mirrors the actually-enforced figure
  as `enforced_api_calls_per_day` — its legacy `api_calls_limit` is a
  monthly figure from `core/valuechain/subscription.py` that is NOT what
  is enforced, and tiers unknown to `core/auth.py` fall back to the free
  quota). `docs/openapi.frozen.json` re-frozen (2-line description diff
  only; no paths/schemas changed).
- Frontend `/settings` and `/billing` pages now carry an explicit
  enforcement note (quotas enforced for authenticated API usage;
  route-level gating not yet enforced during beta).
- Dead code removed: `core/auth.require_tier` (zero callers, minimum-tier
  semantics superseded by the documented allow-list model);
  `check_tier_access` kept and pinned with unit tests as the predicate
  the future paywall middleware will use.
- New `tests/test_tier_quota.py` (20 tests): wiring, free/professional
  quotas, per-user buckets, tier-alias resolution, anonymous
  pass-through, auth/health/billing exemption, invalid-credential
  pass-through, env kill-switch, tier-surface honesty flags, and the
  `check_tier_access` allow-list logic.
- CI/test-suite safety: `FISHINTEL_ENFORCE_QUOTAS=0` in
  `tests/conftest.py` + both CI workflows (same pattern as the rate
  limit); enforcement verified explicitly in the new tests.

### Fixed (review H4 — /china-demand printed "estimates shown" while nothing was shown)
- `frontend/src/app/china-demand/page.tsx`: the supplier note and the
  "Data Sources" footer now render only when a snapshot is actually on
  screen (and, for the supplier note, when supplier rows are listed) —
  no provenance claim while loading or after a total fetch failure.
- Distinct fetch-failure state (`snapshotError`): a rose banner states
  exactly what happened ("Failed to load China demand data — no figures
  are currently shown…" / on a failed refresh: "showing the previously
  loaded snapshot") with a Retry button — instead of the old false
  "SSB series unavailable; shown from curated estimates" text.
- New `frontend/e2e/china-demand-honesty.spec.ts` (4 tests, all
  /api/china/** stubbed — no backend needed): loading (gated in-flight
  fetch → no claims), fetch failure (404 → error banner, zero estimate
  claims), live snapshot (LIVE SSB claims shown), degraded snapshot
  (curated-estimate claims shown only because data IS shown).
- e2e tooling fix discovered on the way: the PWA service worker
  (`public/sw.js`) takes over all GET fetches once active and its
  fetches BYPASS `page.route` — stubbed routes silently stopped
  intercepting (observed: stubbed /api/china/demand answered 503
  "Offline" with zero route-handler hits). New
  `blockServiceWorker()` helper in `frontend/e2e/utils.ts` (stubs
  `navigator.serviceWorker.register`; PWARegister swallows the error)
  keeps route stubs reliable for stubbed specs.
- Visual baselines unaffected (`/china-demand` has no baseline; the
  stubbed-routes pattern matches `visual.spec.ts`).

### Fixed (review M1+M3 — liveness keyed on rounded tonnage, contradicting the documented invariant)
- `core/routers/country_routes.py::_china_provenance` and
  `core/market/supply_demand_engine.py::_demand_context`: the
  `or norway.get("tonnes_12m")` clauses are gone — LIVE/degraded is now
  keyed exclusively on records actually returned (`monthly_series`),
  never on a rounded tonnage that can legitimately be 0.
- `tests/test_china_provenance.py::test_live_when_tonnes_present` repinned
  to `test_tonnes_without_records_is_degraded` (tonnes alone → degraded).
- Structured `norway_exports_to_china.is_live` field added to the engine's
  snapshot (additive under `API_SCHEMA_VERSION` 1.1; mirrors the
  records-based `norway_live` in `_format_snapshot`), pinned by new engine
  tests; `docs/openapi.frozen.json` re-frozen — no diff (untyped dict).
- `frontend/src/app/china-demand/page.tsx` now consumes the structured
  `is_live` contract instead of parsing the display string
  (`String(data_source).startsWith("LIVE")`); the e2e honesty stubs carry
  the new field.
- New `TestDemandContextLiveness` in `tests/test_supply_demand_engine.py`
  (fake china engine, no network): tonnes-without-records →
  `china_live_data: false`; records returned → `true`.

### Fixed (review L1 — inconsistent None-guard; follow-up from M1)
- `supply_demand_engine._demand_context` now uses the same
  `(snap or {})` guard as the line above (the `norway` local is gone with
  the dropped clause).

### Added (review M2 — untested china sub-routes)
- `tests/test_china_provenance.py` now covers
  `/api/china/demand-signals` and `/api/china/demand-impact` with both
  degraded (SSB 08799 fails → `is_live: false`, confidence 0.5,
  `fallback_reason`, payload passes through) and live (records returned →
  `is_live: true`, confidence 0.75) states — previously only the
  `/api/china/demand` snapshot route was pinned.

### Fixed (follow-up to H1 — slowapi clobbered route-provided Retry-After)
- Discovered by the full-suite CI-equivalent run:
  slowapi's `_inject_headers` (active because of H1's
  `headers_enabled=True`) OVERWRITES any existing `Retry-After` on every
  response — the 503 upstream-unavailable envelope's `Retry-After: 45`
  came back as the rate-limit window reset (`60`), and 2xx responses got
  a meaningless `Retry-After`. New `AppLimiter(Limiter)` subclass in
  `core/api.py` keeps the `X-RateLimit-*` observability headers but only
  sets `Retry-After` when the response has none already AND the
  allowance is exhausted (429s come from the exception handler, which
  sets its own). `tests/test_error_envelope.py` (the failing regression)
  is green again; new `TestRetryAfterPreservation`
  (no `Retry-After` on 2xx + 503 envelope value preserved) pins it.

## [Unreleased] — RUN-1 Sprint 4: R9 release + R10 accessibility/honesty (2026-10-13)

### Released (R9)
- `PLATFORM_VERSION` 2.2.0 → 2.3.0; `API_SCHEMA_VERSION` 1.0 → 1.1 (the
  additive response-contract change from R7, per the policy documented in
  `core/version.py`); `docs/openapi.frozen.json` re-frozen (2-line diff: the
  provenance `schema_version` default + `info.version`); `/api/health`
  verified reporting 2.3.0 locally and green in CI; all CHANGELOG
  `[Unreleased]` sections folded under the `[2.3.0]` release heading;
  GitHub release published:
  https://github.com/frehan83-collab/AquaIntel/releases/tag/v2.3.0

### Changed (R10 — bounded accessibility & honesty slice)
- `DataQualityBadge` now carries WCAG semantics: `role="status"`,
  `aria-label` (quality, confidence, source, note) and a `title` fallback for
  non-hover users — every existing consumer inherits the improvement.
- Provenance badges added to the `/price-outlook` page (both header variants)
  and `/china-demand`.
- **Honesty fix (deep):** the three `/api/china/*` routes returned
  `DataProvenance.live("SSB + customs data")` even when the SSB 08799 export
  fetch fails, and the engine's own payload asserted `"LIVE — SSB table
  08799"` / `is_live: true` in its nested Norway fields (and the
  `/china-demand` page rendered those claims). All three layers are now
  honest: the engine downgrades the snapshot (`source`, Norway
  `data_source`, supplier `is_live`) whenever no export records came back,
  the routes return `degraded` (confidence 0.5, with the reason), and the
  page shows "SSB series unavailable — Norway shown from curated
  estimates". Liveness is keyed on records actually returned
  (`monthly_series`), never on a rounded tonnage that can legitimately be 0.
- Coverage audit (reproducible): 26 of 65 page files import
  `DataQualityBadge` (24 before this slice); the remainder are static /
  non-data pages (login, privacy, changelog, design-system, …) or noted as
  future candidates (bloom, causal, exposure, twin, predictions).

### Verified
- `ruff check` clean; new honesty regression suite `tests/test_china_provenance.py`
  8 passed (helper logic + engine nested claims + live route both ways);
  `tests/test_routers.py` + openapi contract green; `tsc --noEmit` 0 errors;
  eslint 0 errors; live curl of `/api/china/demand` shows the honest degraded
  provenance. Independent review of this slice applied in full (contradictory
  nested LIVE claims, `<div>`-in-`<p>` hydration hazard fixed by moving the
  badge root/tooltip to spans, hover-only tooltip now focusable, false
  "Degraded" before data arrival removed).


## [2.3.0] — 2026-10-13 — RUN-1 release
(Everything below under this heading was previously marked [Unreleased]:
RUN-1 Sprints 1–3 plus the P0–P2 follow-up sweeps.)

### RUN-1 Sprint 3: R7 integrated supply–demand engine + 2–20w price path (2026-10-13)

#### Added (R7 — "Holy Grail" flagship)
- `core/market/supply_demand_engine.py`: singleton engine composing the smolt
  pipeline (Norway supply + baseline demand), biomass outlook (Monte Carlo,
  seeded), global supply (Chile/Scotland/Faroe), lice pressure → harvest-delay
  adjustment, China demand momentum and SSB 03024 price history.
- **2–20 week price path** (19 weekly points): seasonal median + mean-reversion
  of the current deviation (half-life 4w) **measured from the latest PUBLISHED
  SSB week**; empirical p10–p90 bands from **walk-forward residual quantiles**
  (~80% measured out-of-sample coverage; in-sample quantiles only when history
  is too short for a walk-forward fit). Bounded heuristic overlays (labelled,
  NOT backtested): global supply-deficit tilt (0.5%/pt, cap ±5%) and
  lice-delay tilt (cap 2%), ramped in over 4 weeks. The legacy smolt
  `price_pressure` signal is deliberately NOT used as a price tilt — its
  balance is pipeline coverage, structurally ≈ −80%, so a tilt from it would
  peg constantly (would have been a fabricated signal).
- `scripts/backtest_supply_demand.py`: strict no-lookahead walk-forward
  backtest over real SSB history → `data/models/supply_demand_backtest.json`
  (gitignored, mirroring the `price_backtest.json` artifact contract; route
  surfaces `price_forecast.backtest` ONLY from the validated artifact).
  Measured 2026-10-13 (352 weeks, 248 walk-forward origins):
  **MAPE 9.08% @2w → 20.94% @20w**; walk-forward band coverage **79.3–80.0%**
  (the in-sample-quantile variant covers only 55.3–69.9% — why the engine
  ships the walk-forward calibration).
- Route `/api/supply/demand-balance` extended **additively** (contract
  `additive-v1`): every legacy field byte-identical, plus `balance_label`,
  `integration` (sources + structured fallbacks), `supply_breakdown`,
  `demand_breakdown`, `price_forecast`. `docs/openapi.frozen.json` re-frozen
  (1-line route description; the response schema was and remains `{}`).
- Frontend: `/supply-forecast` demand-balance card gains the price-path chart
  (mid + p10–p90 band), spot week + publication-lag disclosure,
  `DataQualityBadge`, backtest MAPE line, method note, and amber notices when
  the artifact is missing or bands fall back. `frontend/e2e/api-contracts.spec.ts`
  now asserts the live additive contract server-side in CI.
- 11 new engine tests (`tests/test_supply_demand_engine.py`) — offline,
  deterministic, no network/DB — including an H2 regression guard that
  horizons are referenced to the latest published week.

#### Fixed (independent review — all findings applied)
- **H1 (evidence provenance):** silent sub-engine degradation can no longer be
  advertised as live — `_safe` wraps every source (sync *and* async), biomass
  and global supply raise when they have no real result/anchor, and the China
  demand input is explicitly disclosed as industry estimates (with the
  fallback recorded and provenance `degraded`) whenever live SSB exports are
  unavailable. Structured fallback strings now carry the failure reason.
- **H2 (reference frame):** forecast horizons are now anchored to `spot_week`
  — the same reference the walk-forward calibration uses. Previously the live
  path was anchored to `today + h` while MAPE/bands described `spot + h`
  (SSB's ~2-week publication lag therefore understated uncertainty and shifted
  every displayed point). `spot_lag_weeks` + `horizon_reference` are now in
  the payload and the UI shows the lag.
- M1/M2: method note corrected (the walk-forward fallback trigger is "too
  short for a 104w train + 20w horizon", not "history < 2 years"); UI hardened
  against partial artifacts (`?? "–"`, optional `n_origins`). L-fixes:
  `bands_source` disclosed in the UI, `components_backtested` renamed to
  reflect that no component ablation exists, legacy `price_pressure` tile
  labelled with its source model, padStart/spot-week rendering consistency,
  stale comments removed.

#### Verified
- `ruff check` clean; authoritative suite (`pytest tests/`, CI-equivalent)
  **663 passed / 13 xfailed / 10 xpassed / 0 failed (231.31 s)**; `tsc --noEmit`
  and eslint 0 errors; `next build` compiled; live curl of the running route
  (legacy + additive keys, 19 weekly points, honest degraded provenance);
  Playwright api-contracts assertion added so CI's e2e-backend proves the
  additive contract server-side on every run.

### RUN-1 Sprint 2: P0-2 closed, lice read-index shipped (2026-10-13)

#### Closed (R5 — DuckDB P0-2, cross-platform evidence)
- Built `scripts/bench_lice_read.py`: the exact four `/api/lice/summary` queries
  vs DuckDB `sqlite_scanner` ATTACH vs extension-free row-loading; identical
  summaries enforced across candidates (`match=true`).
- Ran on **Linux** (`python:3.12-slim` container, DB staged in a named volume
  so the Docker-for-Windows mount bridge didn't pollute I/O) and Windows,
  186,139 rows, warm medians: **Linux sqlite 19.4 ms vs DuckDB 80.2 ms
  (4.1× slower)** vs rowload-latest 180.4 ms; **Windows 30.0 / 78.8 / 12.6 ms**.
- **Verdict: CLOSE P0-2** — the `sqlite_scanner` path loses on both platforms
  (4.1× Linux, 2.6× Windows); the row-load variant wins only on Windows
  (12.6 vs 30.0 ms) and loses on Linux (180.4 vs 19.4 ms) — no portable win,
  ≥1.5× gate unmet → **no DuckDB read path will ship**. The 2026-10-13 Windows
  extension blocker did not reproduce today, so the decision no longer
  depends on it. Full closure write-up in `docs/NEXT_STEPS_PLAN.md` §P0-2.

#### Fixed (R6 — the real read-path cost: a missing index)
- `/api/lice/summary` filters `lice_records` by `(year, week)` with **no index
  for those columns** (the only index leads with `locality_no`) → **three full
  scans** of 186k rows + a temp b-tree sort per read.
- **Alembic 015** adds `ix_lice_year_week (year, week)` (existence-guarded,
  013 pattern) and `LiceRecord` declares it for create_all parity. EXPLAIN
  QUERY PLAN: `SCAN lice_records` → `SEARCH ... USING INDEX (year=? AND
  week=?)`; bench on an indexed copy: **19–30 ms → <0.1 ms warm**.
- Latency-sweep note (same R6): the e2e-flagged slow route (Scotland snapshot
  ~25 s) is a cold-cache EXTERNAL fetch — measured **25,695 ms cold → 9 ms
  warm** with the existing `@cached(ttl=900)`; network-bound, no DB fix.

#### Verified
- `tests/test_migrations.py` green (fresh-DB `alembic upgrade head` incl. 015,
  plus a new assertion that `ix_lice_year_week` exists after the chain);
  `ruff check .` clean; py_compile on touched modules; full pytest suite
  **652 passed / 13 xfailed / 10 xpassed / 0 failed (231.39 s)**;
  frontend untouched.

### RUN-1 Sprint 1: hygiene & ratchet truth (2026-10-13)

#### Fixed (R1 — /market honesty pass)
- Dead Fish Pool surface removed (feed retired 2025): `FishPoolChart`,
  `fishPool` state, the "Fish Pool Index" + old "WoW Change" KPI cards (both
  rendered a permanent "—"), the ticker-strip entry and the header tagline
  mention ("SSB · Futures · Equity · AIS" now).
- Equity bindings corrected: `/api/market/equity-prices` returns `prices_nok`
  (not `prices`) and has **no per-ticker change field** — the MOWI KPI, the
  ticker strip (SALM/LSG/GSF/BAKKA) and the equity list were permanently
  empty, and change deltas rendered as fabricated "+0.00%". All consumers now
  read `prices_nok`; fabricated deltas removed; the equity card surfaces the
  endpoint's source string ("Yahoo Finance (~15min delay) + SSB fallback").
- "WoW Change" KPI is now real SSB week-over-week (honest "—" when
  unavailable; percent shown via KPICard's `unit` prop because its count-up
  strips "%" from value strings). New "SALM (Lerøy)" KPI. MOWI label
  escaping bug fixed (JSX attribute strings don't process `\u00f8`).
- Evidence: live headless run — KPI row all live (WoW +0.29%, MOWI 203.40,
  SALM 544.00 NOK), 52 seasonal bars, futures card + "SSB synthetic" badge
  intact, 0 console errors / 0 failed requests; tsc + eslint 0 errors;
  pytest full suite 651 passed / 13 xfailed / 10 xpassed / 0 failed.
  Independent review: no CRITICAL/HIGH; its findings applied. Visual note:
  a fresh Linux regen via `visual-baselines.yml` produced a **byte-identical**
  `/market` baseline — the committed screenshot encodes the first-visit wizard
  overlay (visual.spec policy), which dims the page beneath it, so no baseline
  commit was needed.

#### Fixed (R1b — the ruff ratchet had drifted AND was never enforced)
- Cleared **all 30 ratchet violations** repo-wide (`ruff check .` clean under
  the E9/F821/F811/F401/F841 selection): 24 unused imports (F401) + 6 dead
  locals (F841) across `agents/`, `backtest/`, `compliance/`, `dashboard/`,
  `tests/` and `main.py`. In `tests/test_engines.py` a side-effecting call
  was kept as a bare statement; the pure dead assignments were deleted.
- **`test.yml` now actually enforces the ratchet** (`uvx ruff check .`).
  `ruff.toml` claimed "ENFORCED in CI (must pass)" but no workflow ever ran
  ruff — which is exactly how the drift accumulated. Dead code cannot
  silently pile up again.
- Evidence: `ruff check .` → All checks passed; py_compile on all touched
  modules; agent import smoke; targeted pytest over every touched test file
  217 passed / 0 failed; full suite green.

#### Noted (candidates for later RUN-1 workstreams)
- **KPICard count-up quirk**: it parses numeric-looking value strings and
  drops their adornments — "+0.29%" renders "0.29", and in the `no` locale
  "0,29" parses to **0** (comma stops parseFloat). ~20 pages pass
  `%`-suffixed strings to KPICard. A component-level fix (preserve
  prefix/suffix, locale-aware parse) deserves a dedicated workstream.
- `/futures` `<title>` children-array and `/market` hydration warnings (R1c):
  **closed as not-reproducible** — four dev-mode captures (both pages, fresh
  and onboarded profiles, all console types) are clean on the R1 commit; they
  were likely resolved incidentally by earlier work. Reopen with a
  reproduction if they resurface.

### follow-up sweep: /market bindings + frontend CI triggers (2026-10-13, continued)

#### Fixed (documented post-plan follow-ups)
- **`/market` seasonal card** bound `.data` from `/api/market/ssb-seasonal`,
  but the endpoint returns `.seasonal_pattern` (week → median dict) → the card
  showed a permanent loading shimmer. Now maps the dict (keys are ISO week
  numbers) into the chart, the footer honestly says **median** (the endpoint
  computes `np.median`) and appends the `data_years` span, and an empty
  response renders an explicit "Seasonal data unavailable" state instead of
  the eternal skeleton.
- **`/market` Futures Forward Curve card** bound `.curve` from
  `/api/market/futures-curve` (that endpoint returns SSB `.history`) →
  permanently "Futures data unavailable". Repointed to the real forward curve
  `/api/futures/forward-curve` (Fish Pool live forwards → SSB seasonal
  synthesis fallback); the card badge flips to **"SSB synthetic"** when
  `is_synthetic` so a fallback curve is never labelled as Fish Pool live.
- **`/market` macro KPI cards**: `macroSeries("FRED_USDNOK")` /
  `("FRED_WTI_OIL")` are not valid series names for
  `macro_intelligence.get_series_history` (its keys are `nok_usd` /
  `brent_crude`) → both cards 404'd on every visit. Bound to the real series
  and the crude card is relabelled **Brent Crude** (the backend has no WTI
  series; labelling Brent as WTI would be dishonest), incl. the banner ticker
  ("Brent $…" instead of "WTI $…").
- `FuturesForwardCurve` type mirrored a stale contract (`contracts`/`spot_nok`/
  `fx_rate`); now mirrors the engine response (`curve`/`spot_nok_kg`/
  `spot_eur_kg`/`eur_nok_rate`/`is_live`/`is_synthetic`/`data_provenance`).
- **`/investor` Macro Environment card** — same cluster, found by the pre-commit
  review: invalid series names (`FRED_USDNOK`/`FRED_WTI_OIL`/`FRED_SOYBEAN` →
  `nok_usd`/`brent_crude`/`soybeans`), "WTI Crude Oil" labelling Brent data,
  `$/bu` on a USD/tonne series, and a `|| 0` fallback that fabricated a
  **$0.00** quote whenever a fetch failed. Labels/units now match the
  `macro_intelligence.FRED_SERIES` registry; failures render "—" with a
  "FRED series unavailable" note.

#### Changed (review hardening)
- Seasonal card heading relabelled "Weekly Average" → **"Weekly Median"**
  (`market.weekly_avg`, only consumer) — it plots the medians the footer now
  also names.
- Fish Pool badge renders only when a curve exists; anything except an
  explicit `is_synthetic === false` reads "SSB synthetic" (fail-safe — a
  payload without flags can never be presented as live Fish Pool forwards);
  the `curve` mapping is `Array.isArray`-guarded.

#### Changed (CI)
- `frontend.yml` path filters now also trigger on the backend surfaces the
  `e2e-backend` job boots against (`core/**`, `agents/**`, `config/**`,
  `alembic*`, `main.py`, dependency manifests, `scripts/ci_bootstrap_db.py`,
  `scripts/design_token_pipeline.py` and the workflow file itself) — backend-only
  changes previously skipped the backend-backed e2e entirely (documented P0-1
  follow-up).

#### Verified
- Live local rig (uvicorn + `next dev` + headless chromium on /market and
  /investor): 52/52 seasonal bars from the real SSB medians ("Weekly Median",
  footer "(2020-2026)"), forward-curve chart + KPI strip render with an honest
  "SSB synthetic" badge, NOK/USD 9.64 · Brent $83.73 · Soybeans $442.45/t
  (FRED live), **0 console errors / 0 failed requests** on both pages.
- `npx tsc --noEmit` 0 errors; eslint 0 errors (warnings tolerated);
  pytest **651 passed / 13 xfailed / 10 xpassed / 0 failed** (253 s).

### P1-5/P1-6/P1-7 audits (2026-10-13, continued)

#### Changed (P1-5 — test hygiene)
- **Removed 12 stale `xfail` markers** from `tests/test_api_routes.py`: the 11
  "Dev SQLite may lack Alembic migration 00X…" schema-lag guards (obsolete since
  the migrations-first bootstrap everywhere — they XPASS on both dev and
  fresh-seeded CI databases) and the TimesFM "may not be installed" marker (the
  engine's honest seasonal-naive fallback returns `model` + `median`, so the
  contract holds without the model stack).
- Remaining xfails kept + justified in the plan: genuine external-data guards
  (DFO/Sernapesca/Scotland/Hagstova/Iceland/FRED-live) and async-design quirks.
- Full suite evidence: **639 passed, 13 xfailed, 22 xpassed, 0 failed** on
  Windows/Python 3.14.

#### Verified (P1-6 / P1-7 — audits, no code changes)
- P1-6: `docker-compose.yml` already ships the `fishintel-agents` service
  (`--agents-only`, SIGTERM-graceful); fresh-DB `alembic upgrade head` validated
  in three places (ci_bootstrap, container entrypoint — verified live — and
  `tests/test_migrations.py`).
- P1-7: all four Tier-1 features live-verified (feed margin stack + alerts;
  ocean-forecast→lice decision wiring; computed ESG scores; AIS harvest
  intelligence with 72h signals).

### P0-3 + P0-4: instant lock extension & uv adoption (2026-10-13)

#### Added (P0-4 — uv adoption, Python pinned to 3.12)
- **`pyproject.toml`** — single dependency manifest (mirrors requirements.txt;
  optional `models` extra mirrors requirements-models.txt) with the explicit
  **Python 3.12 pin** decision (`requires-python = ">=3.12,<3.13"`,
  `.python-version`), honoring the plan's rule: local 3.14 must not silently
  become the torch-stack target (CI and Docker already ran 3.12).
- **`requirements.lock`** — generated via
  `uv pip compile pyproject.toml --python-version 3.12 --python-platform linux`
  (248 pins; fastapi locked to the verified 0.135.x line). Regeneration is
  interpreter-free and documented in AGENTS.md.
- CI (`test.yml` + the `e2e-backend` job) and the Dockerfile now install from
  the lock via `uv` (`astral-sh/setup-uv@v5` / `ghcr.io/astral-sh/uv:0.10`);
  `requirements.txt` remains for Windows dev without uv.

#### Changed (P0-3 — instant-navigation lock extended, wired into CI)
- `e2e/instant.spec.ts` now locks **11 routes** (added /brief, /farmer-daily,
  /disease, /leaders, /futures, /feed-cost, /global-supply, /notifications) —
  11/11 green on the prod rig; the rig runs blocking in the `e2e-backend` job.
- `frontend.yml`: removed the redundant tolerant backend-free e2e step from the
  build job (superseded by the blocking backend-backed job; it cost ~15+ min
  per run in expected connection-retry stalls with no added signal).

### Note (P0-2 — DuckDB)
- DuckDB read path deferred with evidence: the sqlite_scanner extension is
  blocked by a Windows application-control policy on the dev box, and the
  extension-free variant measured ~5× slower (220 ms vs 47 ms) than the
  current query path. See docs/NEXT_STEPS_PLAN.md P0-2.

### P0-1 backend-backed e2e (2026-10-13)

#### Added
- **`e2e-backend` CI job** (`frontend.yml`): spins a fresh seeded SQLite DB
  (`scripts/ci_bootstrap_db.py`) + uvicorn on :8000, then runs the API contract/
  integration specs and the app specs (navigation, golden-path, interactions)
  **blocking** on chromium, 1 worker, with a failure-report artifact.
- `scripts/ci_bootstrap_db.py` — idempotent fresh-runner DB bootstrap (schema +
  demo seed), mirrors the conftest pattern.
- `frontend/e2e/utils.ts` — `suppressOnboarding()` (pre-marks `oc_onboarded` /
  `openclaw_tour_completed`; the first-visit wizard otherwise intercepts pointer
  events on every fresh browser profile). Visual baselines intentionally unaffected.

#### Fixed
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

### Session 41e (2026-10-12, autonomous run, continued)

#### Added
- **Blocking visual regression in frontend.yml** with Linux baselines for
  chromium AND mobile (Pixel 5); backend-free e2e scoped separately;
  visual-baselines workflow generates/verifies all projects.

#### Fixed
- CI step order: Playwright runs before 
pm run build (the documented
  .next collision corrupts dev assets); dev-server port pinned via
  webServer env; workflow_dispatch added to both frontend workflows.

### Session 41d (2026-10-12, autonomous run, continued)

#### Added
- **Linux visual baselines** (CI-generated + committed): `visual-baselines.yml`
  workflow_dispatch (update/verify modes, ubuntu + Node 22 + chromium);
  artifact-downloaded `*-chromium-linux.png` snapshots committed; verify run
  green. frontend.yml's e2e step now checks them on every frontend change.
- **F841 in the ruff gate**: all 36 dead locals resolved (pure expressions
  deleted; side-effecting awaits kept as bare statements; PyMC
  `with pm.Model():`). ruff.toml now enforces E9/F821/F811/F401/F841.
- `partialPrefetching: true` — App-Shell prefetch model enabled (skill's
  post-adoption step), verified by instant guard 3/3 + visual baselines 4/4.

#### Fixed
- Playwright webServer port: `env: { PORT: 3001 }` pins the dev server
  cross-platform (CI previously timed out on :3000 vs :3001) + 120 s timeout.

### Session 41c (2026-10-12, autonomous run, continued)

#### Added
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

#### Fixed
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

### Session 41b (2026-10-12, autonomous run, continued)

#### Added
- **Tailwind 4.3 migration** (visually verified): `@tailwindcss/postcss`,
  `@import "tailwindcss"` + `@config` compat, v3 border-color base layer,
  class-token renames (outline-hidden ×62, rounded-xs ×12, shadow-xs ×8,
  backdrop-blur-xs ×7, shadow-sm ×1). Gate: 4 committed visual baselines.
- **Visual baselines** — `e2e/visual.spec.ts-snapshots/` (win32 chromium, 4
  routes, deterministic fixtures) + Playwright chromium 1217 installed.
- `.gitignore`: repaired corrupted UTF-16 tail; ignore frontend run artifacts;
  untracked generated root `openapi.json`.

#### Changed
- `visual-regression` skill: Session-41 war stories (baseline-first, dry-run
  renames, dev-server/build collision, separate commits for baselines vs
  migration).

### Session 41 (2026-10-12, autonomous run)

#### Added
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

#### Changed
- CI: Frontend Build added type-check + lint steps; Node 20 → 22 LTS.
- Generated TS client regenerated for 326 routes; eslint baseline 0 errors.

### Session 40 (2026-10-12)

#### Added
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

#### Fixed
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

#### Changed
- `PROJECT_STATUS.md` stats refreshed; version literals centralized.
- `.mcp.json` project config (firecrawl/playwright/context7/planet-docs).

## [2.2.0] — pre-Session-40 baseline
- 324 routes, 30 routers, 605+ tests baseline with prior sessions' hardening
  (error envelope, bounded caches, SSB/MET resilience, WS single-producer).
