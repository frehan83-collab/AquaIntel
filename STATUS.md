# STATUS.md — Autonomous Execution Log (agent handoff)

> Live status for the NEXT_STEPS_PLAN.md workstreams. Read this first if you are
> resuming after an interrupted session. Update the "Session log" section at the
> bottom with every completed (or blocked) workstream.

Repository: `C:\Users\freha\AquaIntel` · Branch: `master` · Baseline commit: `919855c`
Plan: `docs/AUTONOMOUS_RUN_PLAN.md` (**RUN-1**, active) · Prior plan:
`docs/NEXT_STEPS_PLAN.md` (exhausted) · Rules: `AGENTS.md` (authoritative)

---

## Workstream status

| ID | Workstream | Status | Notes |
|----|-----------|--------|-------|
| P0-1 | Backend-backed e2e in CI | ✅ DONE (CI-PROVEN) | Commit 8fca76b: Frontend Build run 38317892995 — build ✅ + **e2e-backend ✅** (api specs step ✅, app specs step ✅ on fresh ubuntu runner); Backend Tests ✅; Docker ✅ |
| P0-2 | DuckDB read path (lice analytics) | ✅ CLOSED (evidence) | RUN-1 R5 validated it on Linux (container + named volume): sqlite **19.4 ms** vs DuckDB sqlite_scanner **80.2 ms (4.1× slower)** vs rowload 180.4 ms; Windows 30.0/78.8/12.6 ms; identical summaries everywhere. Gate (≥1.5×) not met → **no DuckDB path ships**. The real read-path fix shipped as R6: Alembic 015 `ix_lice_year_week` (EXPLAIN-proven SCAN→SEARCH, 19–30 ms → <0.1 ms). Details: plan doc P0-2 + CHANGELOG Sprint 2 |
| P0-3 | Cache Components `use cache` scoping | DONE (audit) | Skill-guided audit: no server-renderable data routes exist (all pages client components). Deliverable shipped: instant() lock extended 3 → 11 routes, rig wired into CI `e2e-backend` (11/11 green locally on prod rig) |
| P0-4 | uv adoption (pin Python 3.12) | IN VERIFICATION | pyproject.toml + .python-version (3.12 pin) + requirements.lock (248 pins, linux target); CI test.yml + e2e-backend + Dockerfile switched to uv; Docker build verifying locally; CI proof pending push |
| P1-5 | Local env verification & test hygiene | ✅ DONE | Full suite on Win/Py3.14: 639 passed / 13 xfailed / 22 xpassed / 0 failed; ruff + tsc + smoke_security clean; 12 stale migration-lag xfail markers removed (TimesFM one verified CI-safe via honest fallback); remaining xfails justified in plan |
| P1-6 | Production parity (agents service; create_all vs Alembic) | ✅ MOSTLY DONE | compose already ships `fishintel-agents` (--agents-only, SIGTERM); fresh-DB migrations validated in 3 places (ci_bootstrap, container entrypoint live, test_migrations.py) |
| P1-7 | Tier-1 roadmap audit | ✅ DONE (live-verified) | All 4 Tier-1 features verified live: feed margin stack + alerts; ocean-forecast→lice decision wiring; ESG scores (SALMAR 92/A+ computed); AIS harvest intelligence (72h signals). No code gaps |
| P2-8 | Tier-2 roadmap (pick 1–2) | ✅ DONE (verified shipped) | All four candidates already exist end-to-end: contracts (evaluate/portfolio/hedge-signals + engine), treatment optimizer (8 routes), portfolio decisions + investor scenarios, global supply w/ disruption tracking |
| P2-9 | Honesty & security audit | ✅ DONE (clean) | SSRF guard + dispatch-time re-validation + rebinding defense verified; IDOR spot-checks clean (api keys, webhooks); every ML route tagged via from_model_result; ensemble reports models_used/fallback truthfully |

## Environment facts (verified)

- Local: Windows, Python 3.14.3 (only), Node 24, npm 11. Backend deps for 3.14 are
  installed globally; `python -m uvicorn core.api:app` boots (327 routes).
- Python version decision (required before P0-4): **pin 3.12** — matches CI
  (`test.yml`) and avoids 3.14-vs-torch risk. Do not install the models stack into 3.14.
- `.env` + `data/aquaintel.db` are gitignored; local copies were restored from the
  `C:\Users\freha\FishIntel` dev box (same commit as the clone).
- Visual baselines are Linux-generated — regenerate only via `visual-baselines.yml`
  (`update=true`), never on Windows.
- Playwright: chromium browsers already cached locally; dev server pinned to :3001 by
  `playwright.config.ts` (webServer env PORT).

## P0-1 detail (what changed, what remains)

### Contract fixes in `frontend/e2e/api-contracts.spec.ts` (empirically verified
against a live local backend on 2026-10-12; all stale, spec had never run in CI):
- `/api/metrics` is JSON (`cache`/`process` keys), NOT Prometheus text → assertion fixed.
- `/api/ssb/price-history` → real path `/api/market/ssb-price-history`.
- `/api/analytics/leaders` → real path `/api/leaders/top30`.
- `/api/traffic-light/current` → real path `/api/regulatory/traffic-light/current`.
- Admin block asserted unauthenticated 200s — WRONG (endpoints are `require_admin`).
  Rewritten to mirror `tests/test_api_routes.py`: anonymous 401, non-admin 403,
  admin (via `FISHINTEL_ADMIN_EMAILS` bootstrap email) 200. The CI job sets
  `FISHINTEL_ADMIN_EMAILS=ci-admin@fishintel.test`; the spec registers + logs in
  (idempotent, falls back to login on re-runs).

### New CI job (`e2e-backend` in `.github/workflows/frontend.yml`)
- `needs: build`; ubuntu-latest; Python 3.12 + `pip install -r requirements.txt`;
  `scripts/ci_bootstrap_db.py` (new: schema + demo seed, mirrors conftest
  fresh-runner bootstrap); uvicorn on :8000 with health-wait loop; Node 22 + `npm ci`;
  Playwright chromium; blocking runs:
  - `api-contracts.spec.ts api-integration.spec.ts` (120 s/test, 1 worker)
  - `navigation.spec.ts golden-path.spec.ts interactions.spec.ts` (60 s/test)
- Playwright webServer boots the dev server itself — no `npm run build` in this job
  (.next collision lesson from session 41e).

### Local verification (done)
- `python scripts/ci_bootstrap_db.py` on a fresh `DATABASE_URL`: **Alembic to
  head OK** + demo seed (22 localities, 1,144 lice records) — full fresh-DB
  validation (no `.env`, CI env vars) ran BOTH spec suites green:
  api-contracts + api-integration **39/39**, navigation + golden-path +
  interactions **49/49**.
- `npx tsc --noEmit` clean; targeted pytest (resilience + migrations + affected
  4 files: 264 passed / 12 xfailed / 13 xpassed); `ruff check` clean;
  `scripts/smoke_security.py` all checks pass.

### Remaining for P0-1
- Push + watch CI run of the new job go green (needs network repo write access).
- ✅ DONE (2026-10-13 follow-up sweep): workflow `paths:` filters now include
  the backend surfaces the job boots against (`core/**`, `agents/**`,
  `config/**`, `alembic*`, `main.py`, dependency manifests,
  `scripts/ci_bootstrap_db.py`, `scripts/design_token_pipeline.py`, the
  workflow file itself) — backend-only changes trigger the backend-backed e2e
  instead of silently skipping it.
- Accepted risk (review F4): the blocking job's assertions depend on live
  third-party APIs (SSB/SEPA/DFO…). Mitigations: Playwright retries=2 on CI,
  120 s/test timeouts, honest degraded responses still 200. Vendor-outage
  flakes → re-run the job; do not weaken assertions.

### Independent code review (2026-10-13, pre-commit)
Review subagent verdict: no CRITICAL/HIGH; safe to commit. Applied its MEDIUMs:
F1 fabricated-90%-confidence badge removed (market header classifies
live/degraded without invented numbers); F2 serve-stale path gated like the
fresh-cache path (+3rd regression test); F3 `/trader` same-class field bugs
fixed (all four usages); F5 bootstrap runs Alembic BEFORE create_all — which
exposed and fixed the **013 duplicate-index migration bug** (fresh
`alembic upgrade head` aborted → would break any brand-new production deploy) +
added `tests/test_migrations.py`.

## Session log

- 2026-10-12/13 · P0-1: complete locally (see P0-1 detail above). Pushed 8fca76b.
  CI: Backend Tests ✅ (incl. new migration + cache-window tests), Docker Build ✅;
  Frontend Build still running at handoff (build job's tolerant e2e step is slow —
  removed in the P0-3/4 push; the blocking e2e-backend job proves the real gate).
- 2026-10-13 · P0-2: Blocked with measurements (see table + plan doc). No code shipped.
- 2026-10-13 · P0-3: `next-cache-components-optimizer` invoked; audit found no
  server-renderable data routes (all pages client components; shells only in
  layout/loading/not-found). Shipped the productive subset: instant() lock 3 → 11
  routes (11/11 green on prod rig locally; order validated: dev-server specs →
  teardown → prod build → instant) + rig wired into CI `e2e-backend`. Committed 0dfea97.
- 2026-10-13 · P0-4: pyproject.toml (3.12 pin per the explicit decision rule) +
  .python-version + requirements.lock via uv pip compile (interpreter-free —
  uv's managed 3.12 is blocked by the same Windows app-control policy as the
  duckdb extension; used `--python-version 3.12 --python-platform linux`).
  One honest caveat: sdist metadata for the lock was built under 3.14 (uv's
  warning), so the platform proof is the Docker build (local, in progress) and
  the CI installs. test.yml + e2e-backend + Dockerfile switched to uv;
  requirements.txt kept for Windows-without-uv.

- 2026-10-13 · P0-1 app-spec triage complete (8 initial failures → all root-caused):
  - Stale selectors fixed: `.first()` svg matched the hidden hamburger; invalid
    CSS+text mixed click selector; strict-mode `text=Disease`; PDF button now via
    `getByRole("button", { name: /PDF/ })`; URL race → `expect(page).toHaveURL()`.
  - OnboardingWizard (`oc_onboarded` localStorage gate) intercepts pointer events
    on fresh profiles → new `e2e/utils.ts#suppressOnboarding` used by the 3 app
    specs only (visual baselines untouched).
  - **Real backend bug (fixed)**: `core/market/price_feed_hub._get_ssb_prices`
    called non-existent `ssb_client.get_latest_prices` → import + method error →
    `/api/futures/forward-curve` returned an empty curve (chart could never
    render). Now imports `ssb_price_client.get_price_history(n_weeks=260)` and
    normalizes `price_nok` → `price_nok_kg`. Verified: 12-point synthetic curve,
    honest degraded provenance (is_synthetic=true).
  - **Real frontend bug (fixed)**: `/market` page read `.data` from
    `/api/market/ssb-price-history` (endpoint returns `.history`, field
    `price_nok` not `price_nok_kg`) → price chart + spot KPI permanently empty.
    Now mapped correctly. Spec anchors on InteractiveChart's a11y contract
    (`role="img"` + "N data points" aria-label) so it can't pass vacuously.
  - Observed but NOT fixed (out of P0-1 scope, honesty preserved): `/market` still
    binds `.curve`(futures)/`.data`(seasonal) from endpoints that return
    `.history`/`.seasonal_pattern`; the "Futures Forward Curve" card (Fish Pool
    badge) now honestly shows "data unavailable" — feeding SSB data there would
    be mislabeled. Candidates for a P1-7 follow-up sweep. Also noted: a React
    `<title>` children-array warning on /futures, and a hydration warning on
    /market (non-fatal, no test uses error-boundary assertions on them).


- 2026-10-13 · P1-5: full suite green on Win/Py3.14 (639 passed / 13 xfailed /
  22 xpassed / 0 failed); 12 stale xfail markers removed after -rX triage
  (TimesFM removal verified CI-safe against the engine's honest fallback;
  test_api_routes rerun: 151 passed / 7 xfailed / 0 xpassed); committed 26eb194.
- 2026-10-13 · P1-6/P1-7/P2-8/P2-9: audits complete — agents service already in
  compose (SIGTERM-graceful); fresh-DB migrations validated 3 ways (ci_bootstrap,
  live container entrypoint, test_migrations.py); all Tier-1 and Tier-2 roadmap
  features verified shipped with live endpoint evidence; honesty + security audit
  clean (SSRF guard + dispatch-time re-validation + rebinding defense, IDOR
  spot-checks, from_model_result tagging everywhere, truthful ensemble
  models_used/models_fallback). No code gaps found.
- 2026-10-13 · CI final state: 8fca76b (P0-1) all three workflows green;
  686a93c (P0-3+P0-4) all three green incl. uv installs + instant rig on CI;
  26eb194 (P1-5) Backend+Docker green; 9bf6760 (follow-up sweep)
  Frontend+Backend+Docker all green — visual regression passed against the
  committed Linux baselines (unchanged: the fixed cards sit below the
  viewport fold), e2e-backend 39 api + 49 app specs + instant rig green on
  the fresh DB (run 38372300505).
- 2026-10-13 · **Full plan exhausted — every workstream DONE or
  BLOCKED-with-evidence.**
- 2026-10-13 · **Follow-up sweep (post-plan):** /market card bindings fixed —
  seasonal card binds `.seasonal_pattern` (week→median dict; footer says
  "median" + data span `(2020-2026)`; explicit empty state instead of the
  eternal skeleton); futures card repointed to the real
  `/api/futures/forward-curve` (Fish Pool live → SSB synthetic fallback) with a
  synthetic-aware badge; macro KPI cards fixed (`FRED_USDNOK`/`FRED_WTI_OIL`
  were never valid series names → both 404'd on every visit; now `nok_usd` /
  `brent_crude`, WTI→Brent relabel incl. the banner ticker; heading "Weekly
  Average"→"Weekly Median"; badge fail-safe, only when a curve exists). Same
  cluster fixed on /investor (`nok_usd`/`brent_crude`/`soybeans`,
  Brent/Soybeans labels, $/t unit, no fabricated $0.00 → "—"). Stale
  `FuturesForwardCurve` TS type aligned to the engine contract. `frontend.yml`
  paths filter extended with the backend surfaces (P0-1 follow-up above).
  Verified live on the local rig (/market + /investor): 52/52 seasonal bars,
  curve + KPIs render, "SSB synthetic" badge, NOK/USD 9.64 / Brent $83.73 /
  Soybeans $442.45/t, 0 console errors / 0 failed requests; tsc 0 errors;
  eslint 0 errors; pytest 651 passed / 13 xfailed / 10 xpassed / 0 failed
  (253 s).
- Remaining documented follow-ups: **P0-2 DuckDB** (still environment-blocked —
  Windows app-control policy; revisit on a Linux env) and the noted /futures
  `<title>` children-array + /market hydration warnings (non-fatal, no
  assertions on them).
- 2026-10-13 · **RUN-1 planned**: `docs/AUTONOMOUS_RUN_PLAN.md` created — a
  long autonomous run in 4 sprints with 10 workstreams R1–R10 (Sprint 1
  hygiene/contract hardening → Sprint 2 DuckDB-on-Linux + latency → Sprint 3
  Holy-Grail supply–demand flagship → Sprint 4 release/polish). The 11-step
  "delta loop" is the per-change protocol; stop conditions and a run-complete
  checklist are included. Next agent starts at Sprint 0 of RUN-1.
- 2026-10-13 · **RUN-1 Sprint 0–1 progress:**
  - Sprint 0 (orientation): clean tree verified; backend boots (327 routes,
    /api/health 200, v2.2.0); fast smoke green (37 passed).
  - **R1 DONE (commit 48c743b)** — /market honesty pass: dead Fish Pool
    surface removed (chart/state/KPI cards/strip entry/tagline); equity
    bindings fixed (`prices_nok`; the fabricated "+0.00%" change deltas
    deleted; source caption added); "WoW Change" KPI now real SSB
    week-over-week; new SALM KPI; MOWI label-escape bug fixed. Gates: full
    suite 651/13/10/0, tsc + eslint 0 errors, live render all-live KPI row
    + 0 console errors/404s, independent review clean (no CRITICAL/HIGH;
    findings applied). Visual: Linux regen via `visual-baselines.yml` came
    back **byte-identical** — the /market baseline encodes the first-visit
    wizard overlay (dimmed page below), so no baseline commit was needed.
  - **R1b DONE (commit c6107c8, CI-PROVEN)** — the ruff ratchet had
    **drifted (30 violations repo-wide) and was never CI-enforced** despite
    ruff.toml's "ENFORCED in CI" claim. Cleared all 30 (24 F401 + 6 F841;
    side-effecting test call kept as bare statement); `test.yml` now runs
    `uvx ruff check .`. Evidence: `ruff check .` clean; py_compile + agent
    imports OK; targeted tests over every touched file 217 passed; full
    suite green; CI Backend Tests green **with the new ruff step**.
  - R1c closed: /futures `<title>` + /market hydration warnings are **not
    reproducible** (4 dev captures: both pages × fresh/onboarded, all
    console types — clean); likely resolved incidentally. Reopen only with
    a reproduction.
  - **RUN-1 Sprint 1 (R1 / R1b / R1c) COMPLETE & CI-PROVEN** — all six
    workflow runs green across the two commits (48c743b: Frontend 7m26s,
    Backend 2m59s, Docker 1m57s; c6107c8: Frontend 7m19s — triggered via
    the extended paths on agents/** — Backend 3m12s **including the new
    ruff step**, Docker 1m50s). Visual regression passed against the
    unchanged committed baselines (byte-identical regen verified).
    **Next: Sprint 2 — R5 (DuckDB bench on Linux via Docker) → R6
    (latency sweep / migration 015), per `docs/AUTONOMOUS_RUN_PLAN.md`.**
- 2026-10-13 · **RUN-1 Sprint 2 (R5 + R6) complete (commit 539d7a0, CI-PROVEN):**
  - **R5** — `scripts/bench_lice_read.py` built and run on BOTH platforms
    (Linux: python:3.12-slim container with the DB staged in a named volume —
    the Docker-for-Windows mount bridge measurably pollutes I/O; first
    attempt read 1,217 ms vs native 19 ms). Warm medians (186,139 rows):
    Linux sqlite 19.4 / DuckDB 80.2 / rowload-latest 180.4 ms; Windows
    30.0 / 78.8 / 12.6 ms; all summaries identical (match=true). **P0-2
    CLOSED: no DuckDB path ships** (gate ≥1.5× unmet; even the old Windows
    extension blocker did not reproduce today).
  - **R6** — the real cost was a missing index: `/api/lice/summary` filters
    `lice_records (year, week)` → three full scans + temp b-tree sort. Alembic
    **015** `ix_lice_year_week` (existence-guarded; model parity) —
    EXPLAIN: SCAN → SEARCH USING INDEX; indexed-copy bench 19–30 ms → <0.1 ms.
    Latency note: Scotland snapshot is a cold-cache external fetch (25,695 ms
    cold → 9 ms warm; `@cached(ttl=900)`), not a DB issue.
  - Gates: test_migrations green (fresh-DB upgrade head with 015 + new
    index-existence assertion); ruff clean; full suite 652 passed / 13
    xfailed / 10 xpassed / 0 failed (231.39 s); frontend untouched.
  - **CI (539d7a0): all three workflows green** — Docker Build 2m07s;
    Backend Tests incl. the new ruff ratchet step + full suite; Frontend
    Build incl. **e2e-backend on a fresh DB bootstrapped through Alembic 015**
    (39 api + 49 app specs + instant rig) — 015 is validated end-to-end in CI.
  - **Next: Sprint 3 — R7 (Holy-Grail supply–demand upgrade) per
    `docs/AUTONOMOUS_RUN_PLAN.md`; R8 only if budget remains.**
  - Noted for later workstreams: KPICard count-up strips "%" from value
    strings app-wide (~20 pages) and mis-parses nb-locale "0,29" as 0 →
    candidate component fix (see CHANGELOG "Noted").

- 2026-10-13 · **RUN-1 Sprint 3 (R7 — "Holy Grail" flagship) complete:**
  - **Engine** — new singleton `core/market/supply_demand_engine.py` composing
    smolt pipeline + biomass outlook (MC, seeded) + global supply +
    lice-pressure harvest-delay + China demand + SSB 03024 history into one
    balance, plus a **2–20 week price path** (19 points): seasonal +
    reversion core (half-life 4w) with **walk-forward residual p10–p90
    bands** (~80% measured out-of-sample coverage; in-sample fallback only
    when history is too short for a walk-forward fit). Heuristic overlays
    labelled NOT-backtested: global supply-deficit tilt (0.5%/pt, cap ±5%)
    and lice-delay tilt (cap 2%), ramped in over 4 weeks. The legacy smolt
    `price_pressure` is deliberately NOT used as a tilt (structurally
    ≈ −80% pipeline coverage — a tilt from it would peg constantly, i.e.
    a fabricated signal).
  - **Backtest (real artifacts only)** — `scripts/backtest_supply_demand.py`,
    strict no-lookahead walk-forward, 352 weeks / 248 origins:
    **MAPE 9.08% @2w → 20.94% @20w**; band coverage 79.3–80.0% (wf) vs
    55.3–69.9% (in-sample quantiles). Artifact at
    `data/models/supply_demand_backtest.json` (gitignored, `price_ml`
    contract); the route surfaces `price_forecast.backtest` ONLY from the
    validated artifact, null elsewhere.
  - **Route (additive-v1)** — `/api/supply/demand-balance` keeps all 7 legacy
    fields byte-identical and adds `balance_label`, `integration`
    (sources + structured fallbacks), `supply_breakdown`, `demand_breakdown`,
    `price_forecast`. `docs/openapi.frozen.json` re-frozen (1-line route
    description; its response schema was and remains `{}`). Live curl proof:
    legacy `signal: undersupply` + all additive keys, 19 points starting
    W42 (= spot W40 + 2, lag disclosed), provenance honestly **degraded 0.6**
    with reason "china demand: live SSB exports unavailable (estimates
    used)".
  - **Frontend** — `/supply-forecast` demand-balance card gains the
    price-path chart (mid + p10–p90 band), spot week + publication-lag
    disclosure, `DataQualityBadge`, backtest MAPE line, method note, and
    amber notices when the artifact is missing or bands fall back;
    `frontend/e2e/api-contracts.spec.ts` asserts the live additive contract
    in CI.
  - **Independent review: no CRITICAL; both HIGH + M/L findings applied** —
    H1 (silent sub-engine degradation can no longer be advertised as live:
    `_safe` wraps sync+async, biomass/global raise on empty results, China
    estimates disclosed with the fallback recorded); H2 (forecast horizons
    re-anchored to the latest PUBLISHED week — the calibration reference —
    with `spot_lag_weeks` disclosed); M1/M2 method-note + UI robustness;
    L-fixes (structured fallback reasons, `bands_source` in UI,
    `components_backtested` naming, legacy price_pressure tile source tag).
    One real bug caught by the tests during the fix round: `_safe` awaited a
    sync source (now awaitable-aware).
  - Gates: ruff clean; new engine tests 11/11 (offline, deterministic);
    route + openapi-contract tests green; `tsc` + eslint 0 errors;
    `next build` compiled; full suite 663 passed / 13 xfailed / 10 xpassed / 0 failed (231.31 s).
  - **CI (a456747): all three workflows green** — Docker Build ✅;
    Backend Tests ✅ (ruff ratchet + full suite); Frontend Build ✅
    (build job incl. type check / lint / visual regression against the
    unchanged baselines + **e2e-backend on a fresh DB**: API-contract specs
    — including the new live additive-contract assertion — app specs and
    the instant rig all passed).
  - **R7 is CI-PROVEN.** Next: **R9 release** (executed: PLATFORM_VERSION
    2.2.0 → 2.3.0, API_SCHEMA_VERSION 1.0 → 1.1 for the additive
    contract, CHANGELOG [Unreleased] → [2.3.0], `gh release create`,
    `/api/health` verified locally reporting 2.3.0), then R10 if budget
    remains, per `docs/AUTONOMOUS_RUN_PLAN.md`.


- 2026-10-13 · **RUN-1 Sprint 4 (R9 release + R10 bounded slice):**
  - **R9 DONE** — `PLATFORM_VERSION` 2.2.0 → **2.3.0**; `API_SCHEMA_VERSION`
    1.0 → **1.1** (the additive contract change from R7, per the policy in
    `core/version.py`); frozen OpenAPI re-frozen (2-line diff: provenance
    `schema_version` default + `info.version`; drift test green);
    `/api/health` verified locally reporting 2.3.0; CHANGELOG `[Unreleased]`
    sections folded under `[2.3.0]`; **GitHub release published**:
    https://github.com/frehan83-collab/AquaIntel/releases/tag/v2.3.0
    (commit e59aa57; Docker ✅ + Backend Tests ✅ on it, Frontend watched).
  - **R10 (bounded accessibility/honesty slice)** — `DataQualityBadge` now
    has WCAG semantics (`role=img` + `aria-label` incl. confidence/source,
    focusable tooltip, span-based markup avoiding `<div>`-in-`<p>` hydration
    hazards); provenance badges added to `/price-outlook` (both headers)
    and `/china-demand`; **honesty fix (deep)**: the `/api/china/*` routes
    AND the engine's nested Norway claims (source / data_source / supplier
    is_live) plus the page copy all claimed LIVE while the SSB 08799 export
    fetch was failing — all three layers now downgrade to estimates
    (routes: `degraded`, 0.5, with reason; engine: `is_live: false`,
    "Estimate (SSB 08799 returned no records)"; page: conditional texts).
    Liveness keyed on records returned (`monthly_series`), never a rounded
    tonnage. New regression suite `tests/test_china_provenance.py` (8
    passed). Coverage audit: 26 of 65 page files import the badge (24
    before); static pages excluded; future candidates noted (bloom, causal,
    exposure, twin, predictions). Independent review of this slice applied
    in full (no CRITICAL; all HIGH/MEDIUM findings fixed).
  - Gates: ruff clean; `test_routers.py` + openapi contract **48 passed**;
    `tsc` + eslint 0 errors; full suite + CI on this commit to be confirmed
    in the run summary.
  - **RUN-1 status: R1–R10 all delivered** (R1/R1b/R1c, R5/R6, R7, R9, R10;
    R8 deliberately deferred per plan — budget). Remaining future work
    tracked in `docs/NEXT_STEPS_PLAN.md` + this log.


## Commercial hardening — Step 1 (entitlements SSOT) — 2026-10-16

- **Shipped:** `core/entitlements.py` is now the ONLY plan/price/quota/feature
  definition. `core/auth.TIERS` and `core/valuechain/subscription.TIERS` are
  projections of it (they were two divergent tables; `/api/tiers` served both and
  `intelligence` silently ran on the free quota).
- **Paywall enforced** for authenticated accounts on `PREMIUM_PREFIXES` → 402 with
  an actionable upgrade payload; anonymous browsing stays open. Independent
  kill-switches for gating and quota (the first cut nested gating inside the quota
  switch — caught by the new tests).
- **New:** `/api/entitlements/{plans,me,check}`, Alembic 016 (legacy tier
  normalisation), `docs/ENTITLEMENTS.md`, `tests/test_entitlements.py`.
- **Gates:** `test_entitlements.py` + `test_tier_quota.py` 67 passed; auth/tier/
  billing slice 82 passed; ruff clean; OpenAPI re-frozen; platform version → 2.6.0.
- **Next:** Step 2 — the money path (Stripe catalog → checkout → webhook →
  entitlement → gated route, test-mode capable).

## Commercial hardening — Step 2 (the money path) — 2026-10-16

- **Shipped:** `core/billing/stripe_catalog.py` (catalog derived from the
  entitlement SSOT; idempotent Stripe Products/Prices; explicit mock mode) and
  `core/billing/entitlement_sync.py` (the ONE place a billing event becomes an
  entitlement — shared by the real webhook and the mock path).
- `stripe_billing.TIER_PRODUCTS` was a third drifting tier table → now derived.
- New: `GET /api/billing/catalog`, `POST /api/billing/webhook/mock` (non-prod,
  token-guarded), checkout accepts `?plan=`; public `/pricing` page driven by the
  catalog; `api.billingCatalog()` / `api.billingCheckout()`.
- **Fixed a production-blocking schema drift:** `subscriptions.stripe_customer_id`
  exists in migration 002 but was absent from this box's DB. `tests/conftest.py`
  now auto-reconciles missing ORM columns (the PRAGMA/ALTER loop in AGENTS.md).
- **Gates:** `test_billing_money_path.py` 12 passed; ruff clean; `tsc` 0 errors;
  OpenAPI re-frozen.
- **Value:** the previously-blocked premium route now returns non-402 after the
  (mock) payment — the money path is proven, not asserted.

## Commercial hardening — Step 3 (named indices + Bio→Price Weekly) — 2026-10-16

- **Shipped AI-STI and AI-LPI** (method v1.0.0) with published weights, scoring
  formulas, per-component source attribution and renormalising aggregation; a
  missing source degrades the index loudly and an all-source outage returns
  `null` rather than a fabricated value.
- **Bio→Price Weekly v1** composes both indices + supply + price panels into one
  weekly digest; `publish_week()` stores both observations.
- **History:** `index_observations` (Alembic 017), unique per
  (index_code, week, version) so published values are immutable.
- **Endpoints:** `/api/indices`, `/ai-sti`, `/ai-lpi`, `/{code}/history`,
  `/methodology`, `/bio-price-weekly`, admin `/publish`. Public `/indices` page
  shows components + live/degraded badge.
- **Gates:** `test_indices.py` 20 passed; ruff clean; `tsc` 0 errors; OpenAPI
  re-frozen (326 paths).
- **Also fixed:** the earlier background full-suite attempt silently failed
  (`--timeout` needs pytest-timeout, not installed) — the suite is now run without
  it (see the run summary).

## Commercial hardening — Step 4 (Accuracy & Method) — 2026-10-16

- **Shipped** `core/ml/accuracy_registry.py` (validated, versioned artifact store
  under tracked `artifacts/accuracy/`), `scripts/publish_accuracy.py` (real
  walk-forward; interval calibrated in-sample, coverage measured out-of-sample),
  endpoints `/api/accuracy`, `/method`, `/artifacts/{id}`, and the public
  `/accuracy` page with machine-readable fallback disclosure.
- **Honesty trap closed:** the only locally persisted SSB price rows (52) are
  `source='demo_seed'` (synthetic). The publisher now filters on source, reports
  the synthetic rows it ignored, and exits non-zero writing nothing — so
  `/api/accuracy` returns `published: false` and names the fix instead of
  publishing a fabricated MAPE. This is the honesty layer working as intended.
- **Gates:** `test_accuracy_registry.py` 27 passed; `tsc` 0 errors; ruff clean.
- **Open:** an artifact can only be published from a host with real price access
  (`python scripts/publish_accuracy.py --weeks 260`).

## Commercial hardening — Step 5 (production truth) — 2026-10-16

- **Shipped** `docker-compose.prod.yml` with agents as a separate service
  (`--agents-only`) alongside TimescaleDB/api/web, `core/production_truth.py` +
  `scripts/verify_production_truth.py` (deploy-gating: exit 1 on critical),
  `core/market/freshness_monitor.py` + `GET /api/data-freshness` (12 sources,
  staleness vs cadence, `synthetic_only` disclosure), `docker/init-timescale.sql`.
- **Real bug found by the new verifier:** this repo's dev DB had an EMPTY
  `alembic_version` (`DB at None, code head 017`). conftest now reconciles missing
  columns and stamps head for create_all-built dev/test DBs → re-run reports
  `at head 017`, 0 failures.
- **Real bug found by the freshness monitor:** SQLite returns timestamps as ISO
  strings, so every source reported `unknown` until coercion was added; and the dev
  DB's `ssb_weekly_prices` is correctly flagged `synthetic_only` (52 demo rows).
- **Gates:** `test_production_truth.py` 17 passed; ruff clean; `alembic_head` OK.

## Commercial hardening — Step 6 (design-partner pilots) — 2026-10-16

- **Shipped** the pilot runbook as code: `design_partners` + `partner_metrics`
  (Alembic 018) and admin-gated surfaces to create → set reciprocity → onboard →
  score metrics → convert/churn.
- **Pilots grant real entitlements** through `core.billing.entitlement_sync`, so a
  partner sees exactly what a paying customer gets; no new tier (rule 8 intact).
- **Scorecard** computes latest value vs latest target with an `achieved` flag;
  status machine is enforced (illegal transition 409).
- **Real bug found:** `days_remaining` was always None (SQLite returns naive
  datetimes) — fixed.
- **Gates:** `test_partner_pilots.py` 18 passed; ruff clean.

## Commercial hardening — Step 7 (legal foundations) — 2026-10-16

- **Shipped** the data-licence register (`core/legal/data_licenses.py`, 8 sources)
  with an enforced honesty rule: everything defaults to `pending_legal_review` and
  `check_use()` refuses uncleared uses even when the licence permits them. Honest
  state exposed by the API: **8 registered, 0 cleared**; `fish_pool_futures` flagged
  as blocking any public futures display.
- **Signals-vs-advice boundary**, **EU AI Act transparency notes** (3 systems) and a
  **DPA/GDPR scaffold** published as structured data at `/api/legal/*`.
- **Performance fee deferred and enforced**: default off, five conditions to enable,
  and a test asserting no plan advertises one.
- **Gates:** `test_legal.py` 18 passed; ruff clean.

## Commercial hardening — Step 8 (provenance register + ratchet) — 2026-10-16

- **Shipped the formal exempt register** (`core/provenance_register.py`, 18 entries
  with category + reason) and froze the non-exempt inventory in
  `docs/provenance_baseline.json`: **238 /api GET routes → 31 exempt, 207
  baselined, 0 unregistered**.
- **Ratchet:** `scripts/provenance_ratchet.py` (exit 1 on drift) +
  `tests/test_provenance_ratchet.py` (13). A new data route must carry provenance or
  be exempted with a reason, or the gate fails.
- **`with_provenance` decorator** applied to 5 more routes; it preserved the
  engine's own provenance on the futures routes instead of overwriting it.
- **Gates:** ratchet exit 0; 13 passed; ruff clean.









