# HANDOVER — takeover brief for the next coding module

> **Verified at commit `f04e79a` (branch `master`, tree clean, pushed).**
> Every number below was measured, not copied from an older doc. Re-verify with the
> commands in §2 before trusting them.
>
> Read order: **this file** → `AGENTS.md` (authoritative rules) →
> `PROJECT_STATUS.md` (what is shipped) → `CHANGELOG.md` (why) → the per-area docs
> named in §3.

---

## 1. Current state (measured at `f04e79a`)

| Dimension | Value |
|---|---|
| Platform version | `2.6.0` |
| OpenAPI surface | **345 paths / 353 operations** (`docs/openapi.frozen.json`) |
| Tests | **1004 collected** (`pytest --collect-only`) |
| Alembic migrations | **18** (head `018`) |
| Router modules | **38** (`core/routers/`) |
| Engine modules | **77** (`core/market/`) |
| Frontend routes | **68** page files |
| Production topology | `docker-compose.prod.yml`: `api` + `agents` + `db` (TimescaleDB) + `web` |
| Last full-suite run | 969 passed / 3 failed — all 3 fixed afterwards (§6 traps 5–6) |

**What this session delivered** (all pushed): 10 commercial-hardening steps plus 3
follow-up fixes — see §3 for the doc to read per area.

## 2. How to run, test and gate (copy-paste)

```bash
# dev
python main.py                     # API + agents
python main.py --api-only
cd frontend && npm run dev

# the fast gate you should run before every commit
python -m pytest tests/test_entitlements.py tests/test_billing_money_path.py \
  tests/test_indices.py tests/test_accuracy_registry.py tests/test_production_truth.py \
  tests/test_partner_pilots.py tests/test_legal.py tests/test_provenance_ratchet.py \
  tests/test_gtm_roi.py tests/test_migrations.py tests/test_openapi_contract.py -q   # 207 pass, ~14s

# the full suite (≈4.5 min) — command runners time out at ~30s, so background it:
#   Start-Process -FilePath python -ArgumentList '-m','pytest','tests/','-q' \
#     -RedirectStandardOutput data\_suite.txt -NoNewWindow
# NOTE: --timeout is NOT available (no pytest-timeout plugin installed).

# ratchets / verifiers (all must pass before you add routes or data)
python scripts/provenance_ratchet.py             # exit 1 on a new unregistered data route
python scripts/verify_production_truth.py        # exit 1 on a critical prod-truth gap
python scripts/smoke_security.py                 # auth/SSRF/escalation smoke
python -m ruff check <files>                     # ratchet: E9/F821/F811/F401/F841
cd frontend && npx tsc --noEmit                  # must be 0 errors

# after ANY new/changed route:
python scripts/freeze_openapi.py                 # re-freeze the contract (deliberate)
python scripts/provenance_ratchet.py --update    # ONLY after a provenance decision
```

**Windows/PowerShell gotchas that cost real time:** use `python -m pytest` (not
`pytest`); a Python traceback is swallowed by the pipeline — capture it with
`cmd /c "python script.py > out.txt 2>&1"` then read `out.txt`; `git push` writes
progress to stderr so a piped chain may report exit 1 even when the push succeeded —
always confirm with `git ls-remote origin refs/heads/master`.

## 3. What is shipped, and where to read about it

| Area | Doc | Code |
|---|---|---|
| Entitlements (single source of truth) | `docs/ENTITLEMENTS.md` | `core/entitlements.py` |
| Money path (Stripe + mock mode) | `docs/BILLING.md` | `core/billing/{stripe_catalog,entitlement_sync}.py` |
| Named indices + weekly digest | `docs/INDICES.md` | `core/market/{indices,bio_price_weekly}.py` |
| Accuracy & Method (artifact-backed) | `docs/ACCURACY.md` | `core/ml/accuracy_registry.py`, `scripts/publish_accuracy.py` |
| Production truth + freshness | `docs/PRODUCTION_TRUTH.md` | `core/production_truth.py`, `core/market/freshness_monitor.py` |
| Design partners / pilots | `docs/DESIGN_PARTNERS.md` | `core/routers/partner_routes.py` |
| Legal (licences, advice, AI Act, DPA) | `docs/ADVICE_BOUNDARY.md` | `core/legal/{data_licenses,performance_fee}.py` |
| Provenance register + ratchet | `docs/REPORT_LIVENESS.md` | `core/provenance_register.py`, `core/market/provenance_envelope.py` |
| GTM assets | `docs/GTM_*.md` | `core/gtm/roi.py`, `core/routers/gtm_routes.py` |
| Roles to hire | `docs/roles/` | — |

## 4. Non-negotiables (AGENTS.md wins if anything here disagrees)

1. **Never fabricate data or accuracy.** A model fallback is `is_live: false`, always.
   No MAPE/coverage figure without a validated artifact.
2. **One entitlement definition** — `core/entitlements.py`. Never add a tier table
   (three had already drifted before this was fixed).
3. **Provenance on every data route**, or an exemption in
   `core/provenance_register.EXEMPT` **with a written reason**.
4. **Security invariants:** admin-only `/api/admin/*` + `/api/cache/*`; ownership
   checks against the **token** user id (never a body `user_id`); SSRF guard on
   outbound URLs at creation **and** dispatch; production refuses a weak JWT secret.
5. **Surgical diffs** + tests for every bugfix. Update `AGENTS.md`/`CHANGELOG.md` for
   structural changes.
6. **State gaps, never hide them.** Every check in this repo reports `unknown`/
   `degraded` rather than inventing a value — keep it that way, even when a dashboard
   would look nicer green.

## 5. Workstream backlog — pick these up in order

Each item is self-contained: goal → files → steps → **acceptance criteria you can
test** → traps. `WS-1 … WS-4` are the highest value per hour; do them first.

### WS-1 · Make the lice lineage verifiable (highest value)
**Why:** `lice_records` has no `source` column, so the platform cannot distinguish
reported Fiskeridir/Mattilsynet rows from demo seeds. `AI-LPI` therefore reports
`is_live: false` with "lineage unverifiable" on every call — correct today, but it
means the flagship index can never legitimately claim live.
**Files:** `core/models.py` (`LiceRecord.source`), new `alembic/versions/019_*.py`,
the lice ingest path (`core/market/lice_quota_tracker.py`, `core/demo_seed.py`),
`core/market/freshness_monitor.py`, `core/market/indices.py`
(`_lice_lineage_note()` should return `None` once real rows carry a source).
**Steps:** add the column with a `demo_seed` / `fiskeridir` marker convention; write
it on every ingest; keep a default so `create_all` + the conftest reconciliation still
work; have the freshness monitor count synthetic rows for it.
**Acceptance:** `ix._lice_lineage_note() is None`; `AI-LPI` is `is_live: true` when
rows are real and `false` when they are `demo_seed`; `/api/data-freshness` reports
`synthetic_rows` for `lice_records`; a new test in `tests/test_production_truth.py`.
**Traps:** tests need BOTH the migration and the conftest column reconciliation; never
backfill rows as `fiskeridir` without proof.

### WS-2 · Publish the weekly indices on a schedule
**Why:** `/api/indices/*/history` is populated only by test runs, so the published
series is not yet a product.
**Files:** `core/market/bio_price_weekly.py` (`publish_week` exists), an agent in
`agents/`, `main.py` (`--agents-only`), `docs/INDICES.md`.
**Steps:** a weekly agent calling `publish_week()`; idempotence per ISO week is
already enforced by a unique constraint; alert when the current week is missing.
**Acceptance:** after a run `GET /api/indices/ai-sti/history` is non-empty and
`index_observations` shows `fresh` in `/api/data-freshness`; a test proves the
interval ≤ 7 days.
**Traps:** `publish_week()` stores **both** indices (do not double-publish); the
digest degrading when a source is down is correct behaviour.

### WS-3 · Ship model artifacts through the release path
**Why:** weights live in the gitignored `data/models/`, so CI/prod silently fall back
to seasonal-naive; the verifier reports this truthfully as a warning.
**Files:** `docker-compose.prod.yml` (volume exists), a build/release script, CI,
`docs/PRODUCTION_TRUTH.md`.
**Steps:** versioned bundle (manifest + hash), published as a release asset (GHCR),
populate the `models` volume at deploy, and verify the **manifest hash** rather than
file presence.
**Acceptance:** `verify_production_truth.py` reports `model_artifacts` ok with a
manifest; dropping the volume flips it back to a truthful warning.
**Traps:** never commit weights; never claim "3 foundation models" if fewer load.

### WS-4 · Timescale hypertables (deliberately manual today)
**Why:** `docker/init-timescale.sql` creates the extension only; conversion was left
manual because a wrong chunk interval silently degrades plans.
**Files:** `docker/init-timescale.sql`, a gated migration, `core/production_truth.py`.
**Steps:** convert only tables with a real timestamp column
(`lice_records.fetched_at`, `chlorophyll_readings.fetched_at`,
`index_observations.as_of`) with `migrate_data => true` in a guarded DO block; add
retention policies.
**Acceptance:** the verifier reports `hypertables >= 3` on PG, with a documented
rollback. **Traps:** `ssb_weekly_prices` has **no** timestamp column — do not convert.

### WS-5 · Durable quota ledger + metered billing
**Why:** counters are in-process per UTC day per worker, so a paying customer's
allowance is per-pod and overage invoicing is impossible.
**Files:** `core/tier_quota.py`, `core/models.py` (usage table),
`core/billing/stripe_catalog.py` (metered prices), `core/routers/entitlements_routes.py`.
**Steps:** persist (user, plan, day, count) with an upsert, read/write via the DB,
keep the env kill-switches, surface usage in `/api/entitlements/me`.
**Acceptance:** two simulated workers share one counter — a test proves the 429 fires
once across both.
**Traps:** keep anonymous traffic ungated; never count `/api/auth/*`, `/api/health`,
`/api/billing/*`.

### WS-6 · SSO / SAML / OIDC (enterprise blocker)
**Why:** enterprise deals stall on identity. `docs/roles/enterprise-security-engineer.md`
holds the four-part definition of done.
**Files:** `core/auth.py`, `core/routers/auth_routes.py`, `core/entitlements.py`
(group → plan mapping), `core/models.py`.
**Steps:** OIDC/SAML login, SCIM-style provisioning, group→canonical-plan mapping
**without a new tier table**, central revocation, audit-log entries.
**Acceptance:** a provisioned user lands on the right plan via the existing
entitlement path, revocation removes access, and every change is in the audit log.
**Traps:** an IdP attribute must never grant `role=admin`; map only to
`core/entitlements.PLANS` keys.

### WS-7 · Per-tenant isolation + aggregation threshold
**Why:** producer-contributed data must never be de-anonymisable in a published index;
the licence register already records the n ≥ 5 obligation.
**Files:** `core/models.py`, `core/market/indices.py` (enforce, not just document),
`core/legal/data_licenses.py`, `core/routers/partner_routes.py`.
**Steps:** enforce the threshold in the compute path, scope queries per tenant, and
test that a 4-producer aggregate refuses.
**Acceptance:** 4 contributors → refusal carrying the reason; 5 → success.
**Traps:** the refusal message must not name the contributing partners either.

### WS-8 · More accuracy artifacts (and keep the registry honest)
**Why:** one artifact exists (`seasonal_naive_weekly_prices`, MAPE 13.42%, coverage
92.1%, n=208). A model artifact can be published only where weights/torch are
available; supply and lice surfaces have none yet.
**Files:** `scripts/publish_accuracy.py` (extend, do not fork),
`core/ml/accuracy_registry.py`, `core/market/price_ml.py` (`BACKTEST_ARTIFACT`
contract), `docs/ACCURACY.md`.
**Steps:** one artifact per surface you can genuinely measure; always set
`fallback_used` truthfully; omit `coverage_pct` if unmeasured.
**Acceptance:** `/api/accuracy` lists each new artifact; no surface displays a number
without one. **Traps:** the publisher refuses demo-only data — keep that, never add a
`--force` bypass.

### WS-9 · Freshness alerting + a scheduler assertion
**Why:** nothing pages when a source goes `dead`, and nothing proves the weekly
publication ran.
**Files:** `core/market/freshness_monitor.py`, an agent, `core/production_truth.py`.
**Steps:** alert on `critical_unknown` / `dead` / `synthetic_only`; assert
`index_observations` contains the current ISO week; expose alert state on
`/api/data-freshness`.
**Acceptance:** a test simulating a missing current-week row fails with a named reason.

### WS-10 · Wire runtime provenance measurement into CI
**Why:** the ratchet proves a *decision* was recorded, not that provenance is actually
returned; 204 routes are baselined and the real residue is only known by probing.
**Files:** `scripts/probe_liveness.py` (payload-shape classification exists),
`docs/REPORT_LIVENESS.md`, CI.
**Steps:** probe a booted app in CI, publish `no_provenance` counts into the report,
fail when the count increases.
**Acceptance:** a deliberately provenance-free route makes CI fail naming it.

### WS-11 · Remove the last hardcoded tier table (frontend)
**Why:** `frontend/src/app/billing/page.tsx` still carries its own `TIER_DETAILS`
feature/price lists while `/pricing` is catalog-driven — the same drift the backend
SSOT killed.
**Files:** `frontend/src/app/billing/page.tsx`, `frontend/src/lib/api.ts`
(`billingCatalog` exists), `frontend/src/types/api.ts`.
**Steps:** render from `api.billingCatalog()`, delete `TIER_DETAILS`, keep icons as a
presentation map keyed by plan key.
**Acceptance:** `grep -r TIER_DETAILS frontend/src` is empty; `tsc --noEmit` = 0;
changing a price in `core/entitlements.py` changes the page with no frontend edit.

### WS-12 · Enforce the data-licence register at runtime
**Why:** the register *records* that `fish_pool_futures` may not be publicly displayed
and Copernicus raw data may not be resold — but nothing enforces it. A register that
only documents is a liability.
**Files:** `core/legal/data_licenses.py` (`check_use` exists),
`core/routers/market_routes.py` + routes exposing licensed sources,
`core/provenance_register.py`.
**Steps:** gate affected routes on `check_use(source, "public_display" |
"resale_as_data_product")`; refuse with a structured payload naming the reason and the
register link (mirroring the entitlement upgrade payload).
**Acceptance:** a public futures display without a cleared licence returns a structured
refusal; with `classification_status="cleared"` it passes.
**Traps:** refuse and say why — never silently substitute a different number.

### WS-13 · Human-gated items (a module cannot close these)
Recorded so nobody pretends they are done: legal sign-off per `classification_status`
(fish-pool display licence, NLOD attribution wording, producer aggregation threshold),
the performance-fee decision, DPA completion + sub-processor register, penetration
test, SOC 2 Type I. Owners/conditions: `docs/ADVICE_BOUNDARY.md` §5–6,
`docs/roles/enterprise-security-engineer.md`.

## 6. Traps that cost real time in this codebase

| # | Trap | Rule |
|---|---|---|
| 1 | **Alembic placeholders** | `exec_driver_sql` with `%s` is psycopg2-only and is a **syntax error** on SQLite (`near "%": syntax error`). Use SQLAlchemy Core `update()` with bound params in migrations. |
| 2 | **SQLite drops tzinfo** | A datetime read back is naive → `days_remaining` was always `None`. Coerce with an `_as_utc()` helper before comparing. |
| 3 | **SQLite returns ISO strings** | Timestamps come back as **strings**, so `isinstance(x, datetime)` is false and freshness read `unknown` for every source. Parse defensively (str/date/int/datetime). |
| 4 | **SSB week labels** | `get_price_history` returns `"week": "W42"` → `int()` raises `ValueError`. Strip a leading `W`. |
| 5 | **Ratchet inventories** | Never derive a route inventory from the **live app**: other tests inject `/api/test-*` routes and break it. Use `docs/openapi.frozen.json`. |
| 6 | **Demo-seeded rows** | `ssb_weekly_prices` is `source='demo_seed'`; `lice_records` has **no** source column. Never measure accuracy on them, never claim `is_live` from them. |
| 7 | **Empty `alembic_version`** | A `create_all`-built dev DB has an empty version table; the verifier calls that drift. `tests/conftest.py` reconciles missing columns and stamps head for dev/test only. |
| 8 | **`--timeout` is unavailable** | No pytest-timeout plugin. Background long runs with `Start-Process ... -RedirectStandardOutput` and poll the file. |
| 9 | **PowerShell hides tracebacks** | Pipe to a file with `cmd /c "python x.py > out.txt 2>&1"`, then read `out.txt`. `git push` can exit 1 on success — confirm with `git ls-remote`. |
| 10 | **Contract + baseline re-freeze** | Any new route changes `docs/openapi.frozen.json` **and** the provenance baseline. Re-freeze deliberately (`freeze_openapi.py`, `provenance_ratchet.py --update`) — never just to make a failure disappear. |

## 7. Definition of done for the next module

A takeover session is complete when:

1. The fast gate (§2) passes; if you added routes, both re-freezes were deliberate and
   the OpenAPI contract test passes.
2. Every bug found has a regression test; every honesty gap closed is **visible in an
   API response or a doc**, not only in code comments.
3. `CHANGELOG.md`, `PROJECT_STATUS.md`, `STATUS.md` and the relevant `docs/*.md` are
   updated — documentation is part of the deliverable.
4. No second source of truth was introduced (plans, provenance boundary, licence
   register, accuracy registry).
5. Anything unfinished is written as a numbered workstream in this file **with
   acceptance criteria**, never left as a silent gap.



