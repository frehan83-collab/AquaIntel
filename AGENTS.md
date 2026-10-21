# AGENTS.md — FishIntel / AquaIntel Development Guide

> Agent-facing instructions for AI assistants working on this repository.
> Humans: see `CLAUDE.md` (session log) and `CONTRIBUTING.md` (conventions).
> **Taking over coding? Start with `docs/HANDOVER.md`** — verified current state,
> gate commands, the prioritised workstream backlog and the traps that cost real time.
> This file is the **authoritative source for commands, quality gates, and
> non-negotiable rules**. If it disagrees with another doc, this file wins.

## What this is

Production-grade salmon aquaculture intelligence platform ("Bloomberg Terminal
for Salmon"): FastAPI backend (362 operations across 354 paths, 82 engine modules),
Next.js 16 frontend (46 pages), 45+ live data-source clients, 3 foundation-model
forecasting engines (with honest seasonal-naive fallbacks), 1,500+ tests
(1520 collected on 2026-10-21).

- Repository: `github.com/frehan83-collab/AquaIntel` (public). `origin` points
  here directly; the legacy `openclaw-legacy` remote points at the old
  `OpenClaw` URL, which GitHub now redirects to this repository.
- Default branch: `master`.
- Naming: the platform is **AquaIntel** (legacy: FishIntel, OpenClaw). Brand
  strings were renamed `OpenClaw` → `AquaIntel` repo-wide, including browser
  state keys (`openclaw_*` → `aquaintel_*`; existing users lose tour/demo state
  once — the rest of the frontend already uses the `oc_*` prefix). Two
  identifier classes are intentionally **left unchanged** because they are
  cross-boundary state that cannot be migrated from the code alone: the
  `openclaw-legacy` git remote, and the Stripe subscription metadata keys
  (`openclaw_tier`, `openclaw_user_id`) in `core/billing/stripe_billing.py`.
  `config/settings.py` still falls back to `data/openclaw.db` when a populated
  pre-rename dev database exists.

## Commands

```bash
# Backend (port 8000; 8001 in some docs — check frontend/.env.local)
python main.py                          # API + agents
python main.py --api-only               # API only
python -m uvicorn core.api:app --port 8000

# Environment / dependencies (P0-4): uv-managed, Python pinned to 3.12
# (.python-version + pyproject.toml). requirements.lock is a linux-target lock.
uv pip install --system -r requirements.lock   # locked install (CI/Docker use this)
uv pip compile pyproject.toml --python-version 3.12 --python-platform linux -o requirements.lock  # regenerate after dep changes
# Windows dev without uv still: python -m pip install -r requirements.txt

# Frontend (port 3000/3001/3002 — check package.json + .env.local)
cd frontend && npm install && npm run dev
cd frontend && npx tsc --noEmit         # type check (must be 0 errors)

# Tests (run BEFORE every commit; full suite takes >30s)
python -m pytest tests/ -q              # full suite
python -m pytest tests/test_critical_engines.py -q   # fast smoke (~8s)
python -m pytest tests/ -k "Name" -q    # by name
python scripts/smoke_security.py        # auth/SSRF/escalation smoke checks
python scripts/preflight_audit.py       # module import audit (if present)

# One-off diagnostics
python scripts/probe_fred_series.py     # FRED feed health
python scripts/probe_liveness.py        # route liveness audit → docs/REPORT_LIVENESS.md
```

Windows note: if `pip`/`pytest` are blocked by execution policy, use
`python -m pytest ...`. Command runners have a ~30s timeout — start long
test runs with `Start-Process ... -RedirectStandardOutput` and poll the file.

## Non-negotiable rules (enforced in code review)

1. **Honesty layer — never fabricate data or accuracy.**
   - Any ML result tagged `model="...-fallback"` MUST surface as
     `DataProvenance.degraded`, never `.live`. Use
     `DataProvenance.from_model_result(result, source)`.
   - Never display MAPE/coverage/backtest numbers unless a validated artifact in
     the accuracy registry (`core/ml/accuracy_registry.py`, `/api/accuracy`)
     produced them; request-time metrics are withheld
     (`accuracy_registry.withhold_unregistered_metrics`, WS-23).
   - Never claim "3 foundation models" if fewer actually loaded; report
     `models_used` vs `models_fallback` truthfully.
   - Lice-derived values claim live only through a lineage summary from
     `core/source_lineage.py` (every row used is `barentswatch`, every PA fetched,
     newest row within cadence). `lice_records.source` is `barentswatch` /
     `demo_seed` / `unverified`; NULL or unknown is **never** real, and nothing is
     ever backfilled as a real source without row-level proof (WS-1).
2. **Security — auth on anything operational or user-scoped.**
   - `/api/admin/*` and `/api/cache/*` are admin-only
     (`Depends(require_admin)` in `core/auth.py`).
   - User-scoped resources: ownership checks against the **token** user id —
     never trust `user_id` from request bodies (IDOR).
   - Admin is `User.role == "admin"` or email in `FISHINTEL_ADMIN_EMAILS`;
     registration self-serve roles are whitelisted (no admin).
   - External URLs (webhooks, callbacks): `await validate_webhook_url()`
     (DNS-resolving SSRF guard in `core/security.py`) at creation **and**
     dispatch time — outbound dispatchers must re-validate each send.
   - `FISHINTEL_ENV=production` refuses to start with a weak/missing
     `FISHINTEL_JWT_SECRET` (≥32 chars required).
3. **Live data only** — never hardcode NOK/market values; use live FRED/SSB/
   engine data with `DataProvenance` on every engine response.
4. **Traceability** — every number surfaced to users must be attributable to
   a source (cite FRED series IDs, SSB table numbers, paper references).
5. **Surgical diffs** — delta changes only; never rewrite whole files; follow
   existing patterns (singleton engine + `@cached` + `DataProvenance` +
   `structlog`).
6. **Verify after every change** — import the touched module, run the
   relevant test file, then the fast smoke suite before committing.
7. **Code review before GitHub** — every commit must pass an independent
   code review (subagent or `skills: code-review`) of the actual diff.
8. **Entitlements have ONE definition.** Plans, prices, quotas, features and the
   paywall boundary live in `core/entitlements.py` only; `core/auth.TIERS` and
   `core/valuechain/subscription.TIERS` are derived projections. Never add a tier
   table elsewhere. The paywall applies to *authenticated* accounts on
   `PREMIUM_PREFIXES`; anonymous browsing stays open. Every 402/429 must carry
   `upgrade_hint()` so the client can render an upgrade path.
9. **Update this file + `CLAUDE.md`** after structural changes (new routes,
   engines, conventions).

## Architecture map

| Path | Purpose |
|---|---|
| `core/api.py` | FastAPI app, middleware, WS, cache endpoints (admin-gated) |
| `core/routers/` | 39 APIRouter modules (auth, market, ml, admin, webhook, …) |
| `core/market/` | ~71 intelligence engines (singleton + `@cached` + provenance) |
| `core/ml/` | Foundation-model wrappers (chronos, timesfm, moirai) |
| `core/auth.py` | JWT, 4-tier access, `require_admin`, `is_admin` |
| `core/entitlements.py` | **Single source of truth for plans/prices/quotas and the paywall boundary** (see `docs/ENTITLEMENTS.md`); `core/auth.TIERS` and `core/valuechain/subscription.TIERS` are projections of it |
| `core/models.py` | SQLAlchemy models (31 tables, 20 Alembic migrations) |
| `core/source_lineage.py` | **One definition of what a `lice_records.source` value means** (`barentswatch` / `demo_seed` / `unverified`), the synthetic markers, and the lineage-summary rule; the indices, quota tracker, freshness monitor and production-truth verifier project it |
| `core/async_db.py` | `get_async_session()` — **never** sync `Session` in async code |
| `agents/`, `main.py` | 13 background agents (asyncio; daemon-thread mode for dev only); `index_publisher` publishes the published indices (AI-STI; AI-LPI v1.0 withdrawn by WS-19) once per ISO week (WS-2) |
| `frontend/src/app/` | Next.js App Router pages (`"use client"`) |
| `frontend/src/lib/api.ts` | Typed API client — every new endpoint gets a method here |
| `tests/` | pytest (1520 tests); add tests for every bugfix/feature |
| `docs/` | Roadmaps, competitive analysis, code reviews, summit reports |

### Frozen modules (do not extend)
`pairs_engine.py`, `regime_detector.py`, `satellite_engine.py`, `self_evolve.py`

### Known operational gaps (check before assuming)
- Production Docker CMD runs **API only** (`gunicorn core.api:app`). The production
  topology in `docker-compose.prod.yml` now declares a separate `agents` service
  running `python main.py --agents-only`; `python scripts/verify_production_truth.py`
  fails if it is missing. If you deploy from the bare Dockerfile, agents still will
  not run — use the compose file.
- `FISHINTEL_ENV=production` + SQLite is rejected by `config/settings.py` (and by
  the production-truth verifier).
- Foundation models require `torch` etc. (in `requirements.txt`); without
  them all forecasts honestly fall back to seasonal-naive with
  `is_live: false`.
- Model weights live in the gitignored `data/models/` — absent in CI/prod unless a
  volume/release artifact supplies them. `python scripts/verify_production_truth.py`
  reports presence honestly rather than assuming it.
- Local dev SQLite may lag the ORM (`create_all` vs Alembic); if you see
  `no such column`, reconcile with `PRAGMA table_info` + `ALTER TABLE`. The test
  bootstrap now does this automatically (`tests/conftest.py`), and the
  production-truth verifier compares `alembic_version` against the code head.
- Per-source freshness is visible at `GET /api/data-freshness`; sources with no
  measurable timestamp report `unknown`, and demo-only tables report
  `synthetic_only` (never "live").

## Environment variables (security-relevant)

| Var | Meaning |
|---|---|
| `FISHINTEL_JWT_SECRET` | JWT signing key; mandatory ≥32 chars in production |
| `FISHINTEL_ENV` | `production` enables fail-fast config checks |
| `FISHINTEL_ADMIN_EMAILS` | Comma-separated emails granted admin without DB role |
| `FISHINTEL_CHRONOS_MODEL` | Chronos model id (default `amazon/chronos-2`) |
| `FISHINTEL_DEMO_MODE` | Synthetic data for demos/trials |

## Commit & PR workflow

1. `git status` / `git diff` — stage **only** files you touched (never
   `.coverage`, `*.docx`, or unrelated session artifacts).
2. Run: fast test file(s) → `python scripts/smoke_security.py` (if security-
   touched) → `python -m pytest tests/ -q` full suite → `npx tsc --noEmit`
   (if frontend touched).
3. **Independent code review of the diff** (spawn a review subagent with the
   `git diff` output; fix findings before committing).
4. Commit with a descriptive subject + body (what/why; reference CRITICAL
   items or issue ids).
5. Push `master` to `origin`. (The `aqua` remote was retired; the
   `openclaw-legacy` remote remains a read-only legacy reference.)
