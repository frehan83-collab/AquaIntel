# STATUS.md — Autonomous Execution Log (agent handoff)

> Live status for the NEXT_STEPS_PLAN.md workstreams. Read this first if you are
> resuming after an interrupted session. Update the "Session log" section at the
> bottom with every completed (or blocked) workstream.

Repository: `C:\Users\freha\AquaIntel` · Branch: `master` · Baseline commit: `0ba29e3`
Plan: `docs/NEXT_STEPS_PLAN.md` · Rules: `AGENTS.md` (authoritative)

---

## Workstream status

| ID | Workstream | Status | Notes |
|----|-----------|--------|-------|
| P0-1 | Backend-backed e2e in CI | IN PROGRESS | Specs fixed to real contracts; new `e2e-backend` job in `frontend.yml`; local verification done; awaiting CI proof on push |
| P0-2 | DuckDB read path (lice analytics) | BLOCKED (evidence) | sqlite_scanner extension blocked by Windows app-control policy locally; extension-free variant measured ~5× slower than the existing path (220 ms vs 47 ms). Details in plan doc P0-2. Revisit on Linux env / parquet pipeline |
| P0-3 | Cache Components `use cache` scoping | TODO | |
| P0-4 | uv adoption (pin Python 3.12) | TODO | Decision pre-recorded: CI `test.yml` already pins Python 3.12; Docker + uv must match. Local box has 3.14 only — uv must manage 3.12 itself |
| P1-5 | Local env verification & test hygiene | PARTIAL | Backend smoke green (37 passed/1 xfailed/8 xpassed); full suite + xfail triage pending |
| P1-6 | Production parity (agents service; create_all vs Alembic) | TODO | |
| P1-7 | Tier-1 roadmap audit | TODO | |
| P2-8 | Tier-2 roadmap (pick 1–2) | TODO | |
| P2-9 | Honesty & security audit | TODO | |

## Environment facts (verified)

- Local: Windows, Python 3.14.3 (only), Node 24, npm 11. Backend deps for 3.14 are
  installed globally; `python -m uvicorn core.api:app` boots (327 routes).
- Python version decision (required before P0-4): **pin 3.12** — matches CI
  (`test.yml`) and avoids 3.14-vs-torch risk. Do not install the models stack into 3.14.
- `.env` + `data/openclaw.db` are gitignored; local copies were restored from the
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
- Follow-up noted: workflow `paths:` filter is `frontend/**` only — backend-only
  changes won't trigger the backend-backed job. Consider adding `core/**`,
  `agents/**`, `main.py`, `requirements*.txt` paths (or a dedicated workflow) later.
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

- 2026-10-12/13 · P0-1 start: environment setup (clone verified at 0ba29e3, deps OK),
  backend booted, all 39 api specs green after contract fixes, CI bootstrap script +
  `e2e-backend` job added, tsc clean, backend smoke green.
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

