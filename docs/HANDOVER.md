# HANDOVER — takeover brief for the next coding module

> **Verified at commit `f04e79a` (branch `master`).** The WS-1 figures below were
> measured on the working tree before the WS-1 commit (2026-10-16, see §5):
> migrations at head `019`, fast gate 211 passed + 1 network skip, §6 traps 11–15.
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
| Tests | **1024 collected** (`pytest --collect-only`, 2026-10-16 after WS-1) |
| Alembic migrations | **19** (head `019`) |
| Router modules | **38** (`core/routers/`) |
| Engine modules | **77** (`core/market/`) |
| Frontend routes | **68** page files |
| Production topology | `docker-compose.prod.yml`: `api` + `agents` + `db` (TimescaleDB) + `web` |
| Last full-suite run | **1000 passed / 1 skipped / 13 xfailed / 10 xpassed / 0 failed** in 4m45s (2026-10-16, after WS-1 + review fixes) |

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
  tests/test_gtm_roi.py tests/test_migrations.py tests/test_openapi_contract.py -q   # 208 pass + 1 skip (network), ~20s

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
test** → traps. WS-1 is done; `WS-2 … WS-4` are the highest value per hour — do them next.

### WS-1 · Make the lice lineage verifiable — **DONE 2026-10-16**
**Shipped:** `core/source_lineage.py` — the one vocabulary for `lice_records.source`
(`barentswatch` / `demo_seed` / `unverified`; the `fiskeridir` marker proposed here
earlier was replaced because the only writer is the BarentsWatch Fishhealth API v2
client, so it is the system of record). Alembic **019**: `source VARCHAR(32) NOT NULL
DEFAULT 'unverified'`, NULL → `unverified`, relabels **only** the demo key
(locality 10001–10022 × the seed year 2025) as `demo_seed`, never a real source,
repairs a conftest-reconciled nullable column, batch-mode downgrade.
`agents/data_ingest.py` writes `barentswatch` on **both** upsert branches;
`core/demo_seed.py` writes `demo_seed`; `agents/historical_backfill.py` skips a week
only when its rows are **verified**. `lice_quota_tracker` publishes a row-level
`lineage` (same predicates as its data query, per PA and merged nationally, inside
the cached payloads, mirrored to `last_lineage`) and its provenance is degraded with
the reason when the lineage does not support live — including the single-locality
path. `indices._lice_lineage_note(lineage)` is row-level. `/api/data-freshness`
reports `verified_rows` / `unverified_rows` / `no_verified_rows`; the verifier adds
the **critical** `lice_source_column` check and the `freshness_no_verified_rows`
warn verdict. 20 tests (`tests/test_production_truth.py::TestLiceLineage`,
`tests/test_migrations.py`, `tests/test_indices.py`, `tests/test_market_engines.py`).
**Acceptance met:** `ix._lice_lineage_note()` is None after a compute whose window
is all `barentswatch`, every PA fetched and fresh (proved with stubbed lineage); on
this box it names "6997/6997 lice rows used carry no verified source … newest lice observation is 2026-W15, 27 weeks old … newest lice row was fetched 4604 h ago" with every PA listed; AI-LPI is live/degraded by that rule; the freshness entry shows
synthetic 1,040 / verified 0 / unverified 185,099, `no_verified_rows: true`.
**Deliberately not done:** no pre-WS-1 row was relabelled as real — audit logs record
only per-tick insert counts, which is not row-level proof. The tracker's year-wide
window (WS-15) and the dead ingest (WS-16) keep AI-LPI degraded here until a real
re-ingest; on a fresh production DB every row arrives as `barentswatch`.

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

### WS-14 · Propagate the lice lineage to every lice consumer
**Why:** WS-1 verified one index. 14+ consumers still stamp
`DataProvenance.live(... BarentsWatch ...)` on lice-derived payloads with no lineage
input — one verified index next to a dozen unverified live labels on the same table.
**Files (line numbers measured 2026-10-16):** `core/routers/lice_routes.py:88`,
`core/market/decision_engine.py:138,217`, `core/routers/analytics_routes.py:228,304,340`,
`core/routers/farm_routes.py:84,306`, `core/routers/notification_routes.py:54,584`,
`core/routers/bloom_routes.py:302,307` (hardcodes `is_live: true`),
`core/market/asc_compliance.py:416,489`, `core/market/regulatory_reporter.py:440`,
`core/routers/misc_routes.py:140`, `core/routers/supply_routes.py:89,177,198,223`.
**Steps:** for each, `summarise_lineage` over the rows it actually used (same
predicates), then the tracker's `_provenance_for` pattern (lift it into
`core/source_lineage.py` so there is one implementation).
**Acceptance:** no lice-derived `DataProvenance.live(` without a lineage input; on
an unverified DB `scripts/probe_liveness.py` reports them degraded; one test per
consumer with a demo-seed stub. **Traps:** `bloom_routes` hardcodes `is_live: true`;
`/api/lice/summary` already degrades on staleness — merge, do not double-report.

### WS-15 · Quota tracker window + AI-LPI magnitude
**Why:** `_get_pa_lice_data` filters `year == max(year)` only (it computes
`max(week)` and never uses it), so "latest" is a year-to-date average; and the
national utilisation reads **238,367 %** with every PA over quota — the emission
model's magnitude is implausible. A correct live badge on that number is a
credibility problem WS-1 cannot fix.
**Files:** `core/market/lice_quota_tracker.py` (`_get_pa_lice_data`,
`_estimate_farm_emission`, `PA_HYPOTHETICAL_QUOTA`), `core/market/indices.py`
(`INDEX_METHOD_VERSION` bump — revision policy), `docs/INDICES.md`.
**Steps:** window = latest reported week per PA (or a documented rolling window);
recalibrate quota/emission units against the IMR reference and publish the note in
`methodology()`; bump the method version so history keeps both.
**Acceptance:** `lineage["year"]` + a `week` field reflect the latest week; national
utilisation lands in a plausible range with the calibration published; the WS-1
tests still pass. **Traps:** changing the window changes the lineage the index reads.

### WS-16 · Lice ingest health (blocks any live AI-LPI)
**Why:** the last real lice rows arrived 2026-04-07; the 2026-10-12 tick logged
"0 new lice records for 2026-W42"; `lice_records` is `dead` with 0 verified rows.
**Files:** `agents/data_ingest.py`, `core/barentswatch.py`, `.env` (BarentsWatch
credentials), `core/market/freshness_monitor.py` (alerting — WS-9).
**Steps:** diagnose the 0-row tick (auth, endpoint, `hasReported` filter), fix it,
then let the backfill (which now skips only verified weeks) re-ingest 2020→now —
roughly 350 sequential POSTs; pace it if BarentsWatch rate-limits.
**Acceptance:** `/api/data-freshness` lice `fresh` with `verified_rows > 0`; AI-LPI
`is_live: true` once the window is all `barentswatch`, every PA current and fresh;
a test proving a 0-row tick raises an alert (WS-9). **Traps:** never relabel rows
by hand — the upsert is the only honest path to `barentswatch`. `fetched_at` is a
write time: the re-ingest bumps it on old weeks, which is why the lineage gates on
the observation week too — the freshness monitor still reads `fetched_at`, so it
will say `fresh` after a re-ingest even when the newest observation is months old
(fold the observation-week age into the monitor in WS-9).

### WS-17 · Accuracy publisher column bug
**Why:** `scripts/publish_accuracy.py::_db_series` selects `price_nok` but the
column is `price_nok_kg`; a bare `except` hides it, so its demo-row skip has never
actually run against the DB (the live-fetch path masked it).
**Files:** `scripts/publish_accuracy.py`, `tests/test_accuracy_registry.py`.
**Steps:** fix the column, narrow the except, import `SYNTHETIC_MARKERS` from
`core/source_lineage.py` instead of the local copy, regression test on a seeded
temp DB. **Acceptance:** `_db_series()` returns rows and reports
`skipped_synthetic` on a demo-seeded DB. **Traps:** never add a `--force` bypass.

### WS-18 · Stamped-but-unmigrated dev databases
**Why:** `data/openclaw.db` is stamped 018 but lacks 015's `ix_lice_year_week`:
the conftest stamps `create_all`-built DBs at head, so a migration whose DDL the ORM
does not declare (indexes, backfills) can be skipped silently.
**Files:** `tests/conftest.py`, `core/production_truth.py`, `core/models.py::init_db`.
**Steps:** a verifier check comparing migration-declared indexes with
`inspect(engine).get_indexes`; guard-create `ix_lice_year_week`.
**Acceptance:** the verifier reports index drift on this box before the fix and ok
after; `EXPLAIN` on `/api/lice/summary` uses the index. **Traps:** never fix by
stamping; 019 survives this because it is existence-guarded — new migrations must be.

## 6. Traps that cost real time in this codebase

| # | Trap | Rule |
|---|---|---|
| 1 | **Alembic placeholders** | `exec_driver_sql` with `%s` is psycopg2-only and is a **syntax error** on SQLite (`near "%": syntax error`). Use SQLAlchemy Core `update()` with bound params in migrations. |
| 2 | **SQLite drops tzinfo** | A datetime read back is naive → `days_remaining` was always `None`. Coerce with an `_as_utc()` helper before comparing. |
| 3 | **SQLite returns ISO strings** | Timestamps come back as **strings**, so `isinstance(x, datetime)` is false and freshness read `unknown` for every source. Parse defensively (str/date/int/datetime). |
| 4 | **SSB week labels** | `get_price_history` returns `"week": "W42"` → `int()` raises `ValueError`. Strip a leading `W`. |
| 5 | **Ratchet inventories** | Never derive a route inventory from the **live app**: other tests inject `/api/test-*` routes and break it. Use `docs/openapi.frozen.json`. |
| 6 | **Demo-seeded rows** | `ssb_weekly_prices` is `source='demo_seed'`; `lice_records.source` is `barentswatch` / `demo_seed` / `unverified` (WS-1). Never measure accuracy on synthetic rows; never claim `is_live` from `demo_seed` or `unverified`. |
| 7 | **Empty `alembic_version`** | A `create_all`-built dev DB has an empty version table; the verifier calls that drift. `tests/conftest.py` reconciles missing columns and stamps head for dev/test only. |
| 8 | **`--timeout` is unavailable** | No pytest-timeout plugin. Background long runs with `Start-Process ... -RedirectStandardOutput` and poll the file. |
| 9 | **PowerShell hides tracebacks** | Pipe to a file with `cmd /c "python x.py > out.txt 2>&1"`, then read `out.txt`. `git push` can exit 1 on success — confirm with `git ls-remote`. |
| 10 | **Contract + baseline re-freeze** | Any new route changes `docs/openapi.frozen.json` **and** the provenance baseline. Re-freeze deliberately (`freeze_openapi.py`, `provenance_ratchet.py --update`) — never just to make a failure disappear. |
| 11 | **Demo locality numbers live in the real range** | `DEMO_LOCALITIES` 10001–10022 sit inside BarentsWatch's 5-digit numbering (the lowest real locality on the dev DB is 10029; no real row shares a demo number today, but nothing reserves the range). Identify demo rows only by `source='demo_seed'`, never by locality. A first measurement here wrongly counted 10027/10029 as demo — re-measure before repeating a number. |
| 12 | **Column presence is not lineage** | `lice_records.source` existing says nothing about the rows — a demo-seeded CI database has the column too. Claim live only from `summarise_lineage` over the rows actually used. |
| 13 | **Empty `alembic_version` bricks the ingest** | A `create_all`-built DB whose chain aborts at 001 never runs 019, so every lice insert fails. Recover with `alembic stamp 018` then `alembic upgrade head` — never stamp head. The verifier's `lice_source_column` check catches it. |
| 14 | **The freshness monitor runs in a worker thread** | `fm.report()` uses `asyncio.to_thread`; an in-memory SQLite engine is empty in that thread. Test it with a file-backed engine. |
| 15 | **Long shell heredocs on this box** | Git-Bash `cat <<'EOF'` with a long Python body intermittently fails to parse. Write the patch to a file and run `python file.py`. |

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



