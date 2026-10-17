# HANDOVER — takeover brief for the next coding module

> **Verified at commit `f04e79a` (branch `master`).** The WS-1 figures below were
> measured on the working tree before the WS-1 commit (2026-10-16, see §5):
> migrations at head `019`, fast gate 211 passed + 1 network skip, §6 traps 11–15.
> **WS-2 landed 2026-10-16** too: the `index_publisher` agent (13th) and
> `core/market/index_publication.py`; fast gate 240 passed + 1 skip.
> **WS-19 landed 2026-10-17:** index method 2.0.0 (AI-STI without the lice-quota
> component, AI-LPI v1.0 withdrawn), Alembic **020** (head `020`) marking the
> method-1.0.0 observations superseded; fast gate 247 passed + 1 skip.
> **WS-20's signals takedown landed 2026-10-17:** `GET /api/signals` serves no
> signal; `tests/test_signals_takedown.py` joined the fast gate (262 passed + 1 skip).
> **WS-23's takedown landed 2026-10-17:** no accuracy figure outside the registry;
> `tests/test_accuracy_claims.py` joined the fast gate (274 passed + 1 skip).
> **WS-21 landed 2026-10-17:** regulatory facts as dated, sourced data
> (`core/regulatory_facts.py`); `tests/test_regulatory_facts.py` joined the fast gate
> (346 passed + 1 skip).
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
| Tests | **1053 collected** (`pytest --collect-only`, 2026-10-16 after WS-2) |
| Alembic migrations | **20** (head `020`, since WS-19) |
| Router modules | **38** (`core/routers/`) |
| Engine modules | **77** (`core/market/`) |
| Frontend routes | **68** page files |
| Production topology | `docker-compose.prod.yml`: `api` + `agents` + `db` (TimescaleDB) + `web` |
| Last full-suite run | **1029 passed / 1 skipped / 13 xfailed / 10 xpassed / 0 failed** in 4m38s (2026-10-16, after WS-2 + four review rounds and a final read) |

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
  tests/test_gtm_roi.py tests/test_migrations.py tests/test_openapi_contract.py \
  tests/test_signals_takedown.py tests/test_accuracy_claims.py \
  tests/test_regulatory_facts.py -q   # 346 passed + 1 skip (network), ~30s (after WS-21)

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
test** → traps. WS-1, WS-2 and WS-19 are done.

**Priority changed 2026-10-17 by [`docs/VALUE_ANALYSIS.md`](VALUE_ANALYSIS.md).** The
value analysis found buyer-visible defects that outrank the infrastructure items.
Order (matches VALUE_ANALYSIS section 6): **WS-19 first, before any agent runs**,
then WS-26 (hide what will not be repaired soon; owner decides the list) together
with WS-20's takedown of the SHORT equity signals, WS-20, WS-23, WS-14 together with
WS-22's stale-decision-card rule, WS-21, the rest of WS-22, WS-16 (with WS-9's
zero-row alert), WS-24, WS-25; WS-27 once the owner has decided the design questions.
Keep `--api-only` until WS-19 and WS-16's completeness rule have landed. WS-3 only
after WS-23 has regenerated the backtest and conformal residuals on real rows; WS-17
and WS-8 are part of WS-23. Deferred until a named deal needs them: WS-4, WS-5, WS-6,
WS-7, WS-10, WS-13's SOC 2 / pen test and WS-18. WS-15's quota calibration is dropped
(superseded by WS-19) until a quota regime publishes allocations.

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

### WS-2 · Publish the weekly indices on a schedule — **DONE 2026-10-16**
**Shipped:** `agents/index_publisher_agent.py` (`index_publisher`, the 13th agent,
started by `python main.py --agents-only`): hourly check; builds the digest and
stores one observation per ISO week when `index_publication.status()` says the week
is missing **and** `readiness()` approves (never a null value; only a live digest
within the first 72 h of the week; a disclosed degraded one after); never
double-publishes (a lost race is a duplicate); a failed or incomplete publication is
an error log, an `index_publication` audit row, `last_failure` in `health()` and a
raised tick. `status()` reads the store: latest week per index with value and
provenance, weeks behind, **interval in ISO weeks** (wall-clock gaps are
informational — they drift with the hourly tick), `degraded_current`,
`skipped_weeks`; honest on a missing table. Surfaces: `publication` on
`GET /api/indices`, verifier `index_publication_current_week` +
`index_publication_interval` (a wait inside the grace is info), freshness cadence
(168 + 72 + 1 h) and hint from one definition. The admin `POST /api/indices/publish`
shares the gate (409 when withheld; `force=true&reason=` overrides the grace, audited;
the store refuses null values).
Also fixed: `save_observation` race-safe; `BaseAgent` status recovers after a failed
tick. 29 tests (`tests/test_indices.py::TestWeeklyPublication`,
`tests/test_production_truth.py::TestIndexPublicationCheck`).
**Acceptance met:** the agent publishes once per week across an injected week boundary
(7 d + 30 min is one step; 2 weeks is a named skipped week); `/api/indices/*/history`
is non-empty and the store reports `fresh`; the verifier names the week. **Honest scope:** on this box the
2026-W42 rows were written by the publish test before the lineage guard (trap 16);
the agent's first real run happens with the `agents` service. Human paging on a
missing week is WS-9.

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
**Steps:** alert on `critical_unknown` / `dead` / `synthetic_only` /
`no_verified_rows` (WS-1) and on `index_publication.status()["missing"]` (WS-2 — the
assertion exists; only the paging is missing); expose alert state on
`/api/data-freshness`; fold the lice observation-week age into the monitor (it reads
`fetched_at`, a write time).
**Acceptance:** a test simulating a missing current-week row fails with a named reason.

### WS-10 · Wire runtime provenance measurement into CI
**Why:** the ratchet proves a *decision* was recorded, not that provenance is actually
returned; 204 routes are baselined and the real residue is only known by probing.
**Files:** `scripts/probe_liveness.py` (payload-shape classification exists),
`docs/REPORT_LIVENESS.md`, CI.
**Steps:** probe a booted app in CI, publish `no_provenance` counts into the report,
fail when the count increases.
**Acceptance:** a deliberately provenance-free route makes CI fail naming it.

### WS-11 · Remove the last hardcoded tier table (frontend) — **DONE 2026-10-17 (with WS-20)**
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
**Widened (2026-10-17):** the same rule for every route that stays visible after
WS-26, lice-derived or not: `is_live` from the age of the newest observation,
`freshness` set to that observation's time (today it is the request time on every
probed route; cached routes carry the cache-fill time), an empty payload never live,
a lice week below WS-16's completeness threshold never live. Covers decision, brief,
leaders, ESG, traffic light and the country snapshots. Also remove the unconditional
LIVE pulse (`frontend/src/components/TopBar.tsx:162`) and replace the price-outlook
"REAL DATA" badge (`frontend/src/app/price-outlook/page.tsx:373`) with a
week-and-source stamp; the "All Clear" hero (`DashboardHeroAlert.tsx:80`, used only on
`/`) and the badges at `frontend/src/app/page.tsx:118` and `exposure/page.tsx:389` go
when WS-26 removes those pages.
**Acceptance added:** a test per visible route that a payload older than its source's
cadence reports `is_live: false`, and that a partial lice week is never live.

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
**Superseded in part (2026-10-17):** the utilisation compares a lice count with
constants labelled tonnes, for a quota regime that is still a proposal with no
published allocations. Do not calibrate it; withdraw it (WS-19) and fix the window
only if a rebuilt index still reads the tracker.

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
**Widened (2026-10-17):** on this box the ingest is dead mainly because no agent runs
(the API was started `--api-only`). The ingest also asks for the current ISO week
first and accepts a partial answer, and `/api/lice/summary` uses the newest week
whatever its size: 2026-W15 holds 34 farms against 473 in W14, so the dashboard's
national average describes 34 farms. Add: request the last completed week, retry on
zero reported farms, use a week only above a completeness threshold (for example 80%
of the previous week's reporting farms), and flag only rises in the anomaly engine.
**Run the agents only after WS-19 and this item's completeness rule** (`--agents-only`
starts all 13 agents, including the frozen self-evolving agent and the execution and
hedger agents). **Acceptance replaced (2026-10-17):** AI-LPI v1.0 is withdrawn by
WS-19, so the AI-LPI clause no longer applies; instead `/api/lice/summary` is live
only on a complete, verified week.

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

### WS-19 · Guard the index history before any agent runs — **DONE 2026-10-17**
**Shipped:** index method **2.0.0** (`core/market/indices.py`): `quota_pressure`
removed from AI-STI (biomass / harvest keep their 0.40 : 0.35 ratio, published as
0.5333 / 0.4667); AI-LPI v1.0 **withdrawn** (`PUBLISHED_INDICES = ("AI-STI",)`,
`WITHDRAWN_INDICES`, `SUPERSEDED_VERSIONS`; AI-LPI answers `status: "withdrawn"`,
`value: null`, the reason, and is never computed, built, stored or reported
missing). `index_publication.INDEX_CODES` projects the published set (agent,
`status()`, `readiness()`, `publish_week()`, `store_digest()`, verifier). Alembic
**020** adds `superseded_by` / `superseded_reason` / `superseded_at` to
`index_observations` and marks every 1.0.0 row (existence-guarded; Core `update()`;
downgrade keeps the rows); `history()` exposes the marks. Digest: published
indices + a `withdrawn` block, no lice wording in the headline. `/indices` shows
"withdrawn". Tests: `tests/test_indices.py::TestIndexGuard` (6) and
`tests/test_migrations.py::test_020_…` — all 7 failed on the old code.
**Acceptance met:** AI-STI moves in its documented direction per component and
reads exactly 0 and 100 at ±10 % momentum; no computation of any code calls the
lice-quota tracker; a real publisher tick (test, and once on a backup copy of this
box's DB) stores only AI-STI at 2.0.0 with no quota input — on this box it stores
nothing because AI-STI has no value ("no comparable prior period"). The two
2026-W42 rows are marked `superseded_by='2.0.0'` with their values intact.
Review fixes: the digest degrades when AI-STI does (the read rests on it alone)
and the supply panel follows the biomass tracker's lineage; the freshness monitor
ignores superseded rows (`SourceSpec.excluded_when_set`); GTM copy no longer sells
AI-LPI; `docs/openapi.frozen.json` re-frozen deliberately (two descriptions only —
response shapes had changed). **Left open:** no lice index is published (a rebuild
needs observable facts and verified lice rows — WS-16, then a new method version);
`tests/test_production_truth.py`'s verifier stubs still use "AI-LPI"/"1.0.0" as
arbitrary codes (harmless). The agents service stays off until WS-16's
completeness rule lands.

*Original brief, kept for the record:*
**Why:** `main.py` starts `IndexPublisherAgent` whenever it runs without `--api-only`,
and after the 72 h grace it stores a disclosed degraded value. AI-STI reads 100
"severe" from one component (national lice-quota utilisation 238,367%), and AI-LPI's
`quota_headroom` is inverted (`score = 100 - utilisation`, so more headroom raises
risk), holding it between about 27 and 55 (`core/market/indices.py:404-421`).
2026-W42 already holds a test-written AI-STI of 100 and an AI-LPI of 55 stored as
`is_live: true`; any agent run from 2026-W43 on would add a degraded AI-STI of 100
(and the inverted AI-LPI) every week once the 72 h grace ends, about 2026-10-22.
**Files:** `core/market/indices.py`, `core/market/index_publication.py`,
`agents/index_publisher_agent.py`, `main.py`, `docs/INDICES.md`.
**Steps:** remove `quota_pressure` from AI-STI and withdraw AI-LPI v1.0 (or disable
the publisher behind a setting) with an `INDEX_METHOD_VERSION` bump; mark the two
test-written 2026-W42 rows superseded (do not delete history); if a lice index is wanted,
rebuild it on observable facts (biomass-weighted share of sites above the limits,
weeks to limit). **Acceptance:** a test that each index moves in the documented
direction and can reach its full 0-100 range; a publisher tick on this box stores
nothing built on the quota tracker. **Traps:** never edit stored observations; the
method version keeps old and new apart.

### WS-20 · Public honesty: landing page, API docs, plan ladder, one name — **PARTLY DONE 2026-10-17**
**Done:** testimonials, typed counts, unproven claims and the fake waitlist removed
from the landing page; plans render from the catalog on landing and billing (WS-11
closed); the API reference matches the frozen contract and real response shapes;
plan-catalog wording corrected; `tests/test_public_claims.py` guards page sources
and rendered catalog text. **Signals takedown done 2026-10-17:**
`core/legal/equity_signals.py`; `GET /api/signals` serves the withdrawal notice and
never reads the table, confirm/reject answer 410, `/api/market/hedger-signals` serves
only `SALMON_SPOT`, the chat paths no longer list or advertise signals, the /trader
panel, /signals trading and order sections and the dashboard widget are gone,
`/api/legal/advice-boundary` lists `withdrawn_outputs` and `under_review`;
`tests/test_signals_takedown.py` (15, in the fast gate). The legal opinion and the
other equity-direction surfaces are WS-28. **Left:** one product name and the
Desk/Operator inversion (owner decisions); the
OpenAPI `info.description` "real-time salmon market intelligence" (`core/api.py`,
needs a deliberate re-freeze of `docs/openapi.frozen.json`).
**Why:** the public landing page shows invented testimonials under "Trusted by
Industry Leaders", one credited to Nordic Investment Bank
(`frontend/src/app/landing/page.tsx:47-66, 264`); stale counts ("229 API Endpoints"
at `landing/page.tsx:69, 149-150, 222` and `frontend/src/app/api-docs/page.tsx:688`)
and unproven claims ("Real-time", "1,815 farms", "TFT", a causal z-score,
`landing/page.tsx:13-19, 72, 99-100`); a landing price list that matches neither
`/pricing` nor `core/entitlements.py`. Desk (NOK 2,990) includes "Everything in
Operator" (NOK 4,900) (`core/entitlements.py:147-153`). The product shows two names
(FishIntel, AquaIntel).
**Files:** `frontend/src/app/landing/page.tsx`, `frontend/src/app/api-docs/page.tsx`,
`frontend/src/app/billing/page.tsx` (WS-11's `TIER_DETAILS`), `core/entitlements.py`,
`frontend/src/app/layout.tsx`, `frontend/public/manifest.json`, `Sidebar.tsx`.
Anonymous `GET /api/signals` serves 50 SHORT signals on Grieg, Lerøy, Mowi and SalMar
with per-share impact estimates, shown on `/trader` and `/signals` without provenance,
against the project's own advice boundary (`/api/legal/advice-boundary`); this may
count as an investment recommendation under the EU Market Abuse Regulation.
**Steps:** take the SHORT equity signals down first (route, `/trader` panel,
`/signals` page) and get a short legal opinion; delete the testimonials and the
counts; render every displayed price from
`/api/billing/catalog` (closes WS-11); fix the ladder; pick one product name (owner
decision). The paywall inversion (anonymous visitors get 200 on premium routes while
signed-in Insight and Operator users get 402, `core/entitlements.py:335-337`,
`core/tier_quota.py:137-139`) is a pricing decision, not part of this item: either
treat anonymous as the free plan with a demo login for prospects, or open the same
routes to free users until there is a paid plan to protect.
**Acceptance:** `/api/signals` serves no buy/sell/short direction on a listed
security; `grep -rnE "229|TIER_DETAILS|TESTIMONIALS|Trusted by|Market Engines|1,815|Real-time|TFT" frontend/src/app/landing frontend/src/app/api-docs frontend/src/app/billing`
is empty; every displayed price comes from `api.billingCatalog()`; a test that no
plan's feature list includes a dearer plan. **Traps:** the testimonials need a real, permissioned quote
before anything returns.

### WS-21 · Regulatory facts as dated, sourced data — **DONE 2026-10-17**
**Done:** `core/regulatory_facts.py` (decisions, dated capacity cuts, § 8 limits by
region and week, dated US tariff rows) and its consumers; see CHANGELOG.
**Verification note:** every fact was researched on 2026-10-17 and checked by two
independent verifiers against primary sources: the regjeringen.no announcements and
the Lovdata capacity regulations (FOR-2017-12-20-2397, FOR-2020-02-04-105,
FOR-2022-06-07-972, FOR-2024-03-22-515, FOR-2026-08-20-1764), lakselusforskriften
§ 8/§ 10 on Lovdata, the Federal Register Section 301 notice 2026-15181 and HTSUS
0302.14/0304.41. Medium-confidence items: the cut start dates for 2022, 2024 and 2026
(in-force + 6 months, § 9; 2020 is from LG-2021-80234) and the Faroes' US tariff (assumes
the Faroes are their own country of origin).
**Follow-ups (not done):** (1) still on a flat 0.5 limit: `treatment_optimizer.py`,
`core/valuechain/farmer_advisory.py`, `lice_quota_tracker.py` (risk level),
`core/ml/harvest_optimizer.py`, `supply_demand_engine.py`, `correlation_engine.py` —
route each through `regulatory_facts.lice_limit`; (2) the simulator models a colour as a
capacity level, not the next decision's step (red cuts again, yellow restores nothing),
and disagrees with `event_impact_model`; (3) the `/api/chat` system prompt and
`core/llm/rag.py` state lice-derived colours, an annual cadence and 0.2 as a reporting
threshold, and the rule-based chat crashes on a traffic-light question
(`core/api.py`, `states.items()` on a list); (4) a full municipality → county table
(SSB KLASS 131) so sites without a production area get an established window; (5) watch
the Court of International Trade ruling on the Section 301 duties and add a tariff row
when it lands; (6) the frozen regime detector's transition priors are fixed literals.
*The original task, as written before the work (kept for the record):*
**Why:** the served traffic-light colours are wrong for 6 of 13 areas against the
19 June 2026 decision (PO1, PO12, PO13 green; PO3 red; the rest yellow); they come
from the frozen regime detector or hard-coded defaults
(`core/market/traffic_light_simulator.py:80-84`). Decision cards use a 0.5 lice limit
all year (`core/market/treatment_constants.py:137`) and the regulatory reporter
applies 0.2 only for PA 2-7 in weeks 16-21 (`core/market/regulatory_reporter.py:189-191`).
US tariffs are pre-July-2026 (`core/market/competitiveness_engine.py`: Norway 15%,
Chile 0%, Scotland 2.5%, Faroes 15%).
**Files:** `traffic_light_simulator.py`, `treatment_constants.py`,
`regulatory_reporter.py`, `decision_engine.py`, `competitiveness_engine.py`, a new
dated data file with source URLs.
**Steps:** load official decisions, limits and tariffs as data rows with
`source_url` and `valid_from`; the simulator predicts changes, never the current
colour; one limit function used by the decision engine and the reporter.
**Acceptance:** tests asserting the 2026 colours; the spring 0.2 window (weeks 16-21
in Nord-Trøndelag and southwards, weeks 21-26 in Nordland, Troms and Finnmark;
lakselusforskriften § 8) in both the decision engine and the reporter; the July 2026
tariffs (Norway 12.5%, Chile 12.5%, UK 10%; Faroes and Iceland outside the new
measure; Canada USMCA-exempt), each payload citing its `source_url`.

### WS-22 · Numbers buyers check
**Why:** Mowi shows 113,600 t because volume = localities x 800
(`core/market/top50_engine.py:249-250`; Mowi harvested about 332 kt in Norway in
2025). The supply balance's smolt pipeline is about 5.6x too low (140,450 t against
793,334 t of 26-week demand) and its `biomass_current_tonnes` of 24,796 t is
implausible. `/api/disease/norway` lists the first 20 active outbreaks in upstream
order (`core/market/mattilsynet_client.py:289`), hiding the newest. The brief counts
every stored bloom row ever (`core/market/morning_brief.py`). Competitiveness fell
back to a hard-coded NOK/USD of 0.093 (`competitiveness_engine.py:89`) while
reporting `data_quality: live`. `foundation_models_available` comes from
`import torch`. ROI defaults: producer 228x from a 1.5% harvest-timing gain tied to
AI-STI (`core/gtm/roi.py:23`), desk 491x from a 0.35 NOK/kg basis improvement
(`:34`), processor 1,693x from a hard-coded 0.5 share of the whole margin
(`:138-139`). Decision cards recommend treatment on lice data months old: the newest
8 rows are taken whatever their age (`core/market/decision_engine.py:300-313`),
acted on (`:104-107`) and stamped live (`:138`).
**Acceptance:** one regression test per item; every ROI assumption line defaults to
zero until the customer supplies it (the processor's hard-coded 0.5 becomes a named
input), and each ICP reports the break-even value of its main assumption; a decision card on lice data older than 14 days
returns no TREAT/SCHEDULE action and says why; the disease list is sorted newest
first.
**Added 2026-10-17 (WS-20 review):** `/api/disease/alerts` returns "no outbreaks"
while Mattilsynet has active ISA cases: `core/market/disease_alerts.py` queries only
WOAH and Sernapesca, yet the route's provenance names Mattilsynet
(`core/routers/disease_routes.py`). Merge the Mattilsynet cases or stop claiming the
source, and degrade when the WOAH fetch fails. The subscription's `api_calls_month`
is never incremented (only read), so any monthly-usage display is always 0.

### WS-23 · Accuracy against a strong baseline (contaminated backtest) — **TAKEDOWN DONE 2026-10-17**
**Takedown shipped:** no route prints an accuracy figure the registry does not
hold. `core/market/price_ml.py` never reads `data/models/price_backtest.json` for
display (`mape_backtest`/`band_trust` null; the statement points at
`/api/accuracy`), and loads conformal residuals only from an artifact declaring
`demo_rows_used: 0` (the 2026-10-12 one does not, so the rule tier's bands are
honestly uncalibrated); `/api/market/price-outlook` stores at most one prediction
per ISO week and horizon; `/api/market/prediction-history` serves
`mape_backtest: null`; the `/api/ml/*/model-comparison` routes withhold their
request-time MAPE/RMSE/coverage (`accuracy_registry.withhold_unregistered_metrics`);
the supply-demand path dropped its "~80% coverage" claim and serves its artifact
only when registered. `tests/test_accuracy_claims.py` (in the fast gate).
**Left (the re-run half, steps below):** loader skips `demo_seed`; carry-forward
artifact; `publish_accuracy.py` publishes the served model's backtest on the same
weeks with a Diebold-Mariano test; residuals re-derived with `demo_rows_used: 0`;
serve only the backtested configuration; weekly forecast log;
`scripts/backtest_price_ml.py` must write `demo_rows_used: 0` or its residuals
never load. Also: the in-process `PriceEnsemble.retrain()` sets residuals without a
lineage declaration (its bands then say so); the 879 stored MAPE copies stay in
`price_predictions`, unserved; `tests/test_entitlements.py` and
`tests/test_price_outlook_resilience.py` still call the outlook against the real
store (WS-24); on Python 3.14 `predict()` reaches the TFT tier only inside a running
event loop (`asyncio.get_event_loop()` raises outside one).
**Why:** the price outlook prints "Backtested 4-week MAPE: 8.5%" from
`data/models/price_backtest.json` (2026-10-12). That run merged the database's SSB
rows over the real CSV, database winning (`scripts/backtest_price_ml.py`,
`load_ssb_series`), and all 52 database rows are `demo_seed` (2025W01-W52) — trap 6.
A read-only same-window re-run of the price-only path on real prices
(`data/historical/ssb_prices_2000_2026.csv`, 207 target weeks 2022W42-2026W41, not
stored) gives 4.17 / 6.47 / 8.53 / 13.18% at 1 / 2 / 4 / 8 weeks against
carry-forward's 4.23 / 6.60 / 8.82 / 13.69% (Diebold-Mariano p 0.15 / 0.04 / 0.01 /
0.02): a real but small edge. The registry's year-back baseline is 13.42%. The claim is also outside the registry, and `data/models/conformal_residuals.json`
comes from the same run. The figure is also copied into `price_predictions` on every
outlook request and served by `/api/market/prediction-history`
(`core/routers/market_routes.py:293-313, 532-556`).
**Files:** `scripts/backtest_price_ml.py`, `scripts/publish_accuracy.py` (it can only
build the seasonal-naive artifact today), `core/market/price_ml.py`,
`core/routers/accuracy_routes.py`.
**Steps:** take the 8.5% claim down everywhere it is served; stop storing a
prediction on every request (one per ISO week at most) and null `mape_backtest` in the
history; make the loader skip `demo_seed` rows; add a
horizon-matched carry-forward artifact; extend `publish_accuracy.py` to publish the
served model's backtest on the same weeks with a Diebold-Mariano test; re-derive the
conformal residuals; serve only the backtested configuration (the live outlook adds
lice inputs the backtest held neutral); start a weekly forecast log, scored against
carry-forward, stored where tests cannot write.
**Acceptance:** `/api/accuracy` lists carry-forward and the served model on one
window with the test result; no route prints an accuracy figure the registry does
not hold; a test that the backtest loader refuses `demo_seed` rows.
**Added 2026-10-17 (WS-20 review):** `/api/ml/chronos/model-comparison` returns
`mape`/`rmse`/`coverage_80` per model from a single holdout of `horizon` points
(`core/ml/chronos_baseline.py::compare_models`), on a series whose newest weeks are
the `demo_seed` DB rows. It is covered by the acceptance above: drop the figures or
label them as per-call diagnostics on real rows only.

### WS-24 · Test isolation for the dev database
**Why:** test runs wrote all 260 `design_partners` rows ("X", "Scorecard Co", "Recip
Co"), audit rows and price predictions into `data/openclaw.db`, the same trap the
WS-2 publish tests had. **Acceptance:** a full test run leaves the row counts of
`design_partners`, `audit_logs`, `price_predictions` and `index_observations` in the
dev DB unchanged.

### WS-25 · Cold starts off the request path
**Why:** the liveness probe saw 60 of 219 routes exceed 12 s, but it runs the app
in-process (`scripts/probe_liveness.py`, `httpx.ASGITransport`, 8 requests in
flight) with no lifespan and no shared cache, so it measures cold engines, not the
production server. The dashboard waited about 30 s for the macro snapshot on one
cold start; Canada and Iceland snapshots took 55-57 s on a cold cache (about 0.2 s
warm). **Files:** `core/market/macro_intelligence.py` (sequential FRED fetches), the
brief, feed-cost and leaders engines, the country monitors, `agents/`.
**Steps:** persist last-good values (DB or disk) refreshed by the agents; fetch FRED
series in parallel; serve the last good value as degraded when stale.
**Acceptance:** with last-good values persisted, `python scripts/probe_liveness.py`
in a fresh process shows 0 routes over 12 s (or add a `--base-url` mode and probe the
production server configuration right after start).

### WS-26 · Navigation cut (owner decides the list; do it early)
**Why:** 57 sidebar entries in 8 sections for six customer types; one question split
across pages and engines that disagree; `/indices` and `/accuracy` linked from
nowhere. VALUE_ANALYSIS section 4 proposes keep / merge / hide / delete per page.
Hiding first means later repairs target only what stays visible.
**Files:** `frontend/src/components/Sidebar.tsx`, the affected `frontend/src/app/*`;
optionally the routers behind hidden desks (VALUE_ANALYSIS section 8).
**Steps:** agree the list with the owner; hide behind a flag before deleting; add
privacy-respecting page analytics so later cuts rest on usage.
**Acceptance:** the sidebar shows the agreed desks only; hidden pages answer only
behind the flag; no page title is used twice.

### WS-27 · Design identity (layer 1 now, layer 2 after the owner decides)
**Why:** one template (translucent gradient cards, KPI tiles, fade-ins, blurred
chrome; about 355 `GlassCard` and 260 `KPICard` tags) is repeated across the app, the
product shows two names, and the chrome claims "LIVE" on weekly data.
VALUE_ANALYSIS section 7 splits the fix in two. Layer 1, content conventions:
week-and-source stamps, a confidence mark on every figure, seasonal fans, 13-area
small multiples, editorial charts, one number formatter. Layer 2, the optional
"Sjøkart" visual system: S-52 chart palette, a Norwegian display face, hairline
tables, keyboard first.
**Files:** layer 1: `KPICard.tsx`, a new `Figure` component, the chart components,
`TopBar.tsx`, `DashboardHeroAlert.tsx`; layer 2: `docs/DESIGN_SYSTEM.md`,
`docs/figma-tokens.json`, `frontend/tailwind.config.ts`, `frontend/src/app/globals.css`,
`frontend/src/app/layout.tsx`, `Sidebar.tsx`.
**Steps:** layer 1 on the pages that stay visible after WS-26; owner decisions for
layer 2 (name, label language, Telefon licence, light or dusk default, scoped
stylesheet or full migration); test two mock-ups with buyers before building it.
**Acceptance:** the owner names the pages in scope first. On those pages every figure
shows its week, source and confidence mark; no unconditional LIVE indicator remains;
one formatter renders each value once; new visual baselines are taken once the
design is approved (the current baseline covers only home, market, satellite and
traffic-light, and a redesign fails it by intent).

### WS-28 · Remaining equity-direction surfaces + the legal opinion
**Why:** WS-20 took down the signal generator's SHORT/LONG calls everywhere they were
shown, but other surfaces still put a direction or a per-company financial impact
next to a listed salmon share, and the agents that wrote the calls still exist.
`/api/legal/advice-boundary` publishes this list as `under_review`.
**Surfaces (measured 2026-10-17):** `GET /api/pairs/signals` and the pairs cards on
/signals and the dashboard (`DashboardLiveIntelligence`, `DashboardProduction`) —
paired positions on listed shares from the frozen `pairs_engine`; `GET
/api/sentiment/signals` and the /signals sentiment card — per-ticker sentiment on
MOWI/SALM/LSG/GSF; `GET /api/orders` — anonymous paper order history (one filled
SELL GSF on this box); the /trader Event Impact Simulator — per-company revenue and
stock-move estimates (`core/predictors/event_impact_model.py`); writers of
directional rows to `signals`, which run only with the agents service: the signal
generator, the market hedger (`agents/market_hedger_agent.py`, LONG/SHORT on listed
tickers — `/api/market/hedger-signals` now serves only `SALMON_SPOT`), the
prediction agent (`agents/prediction_agent.py`, per-share impact rationale) and the
bloom agent (`agents/bloom_agent.py`, SHORT); the execution agent acts only on
user-confirmed signals and confirm answers 410; the Streamlit `dashboard/app.py`
lists pending signals with confirm/reject (not deployed); the admin `signals` export
(`core/routers/admin_routes.py`, admin-only);
`frontend/src/components/TopBar.tsx` still polls `api.signals()` for a badge that is
now always hidden. Unrelated bug found on the way: the rule-based chat's forecast
branch imports `core.market.price_ensemble`, which does not exist, so it always
answers from its error path.
**Steps:** get the short legal opinion WS-20 asked for (MAR Art. 3(1)(34), MiFID II
perimeter); for each surface decide keep / reword / withdraw with counsel; withdraw
through `core/legal/equity_signals.py` so the advice boundary lists it; stop the
agents that write directional rows on listed securities from writing them before
the agents service runs.
**Acceptance:** a test per withdrawn surface in `tests/test_signals_takedown.py`
seeding the data it would show; `main.py --agents-only` starts no agent that writes
a directional row on a listed security; the opinion's conclusion recorded in
`docs/ADVICE_BOUNDARY.md` and `under_review` emptied accordingly.

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
| 16 | **Tests used to publish into the real index store** | Until WS-2 the publish tests stored the current week into the dev DB on every run; this box's 2026-W42 rows predate the lineage guard and the AI-LPI one claims `is_live: true`. Use the `observation_store` fixture for anything that writes observations; never read the dev box's published history as evidence of the agent. The rows store the defect values (AI-STI 100 severe; AI-LPI 55 claiming `is_live: true`) at method 1.0.0; since WS-19 (Alembic 020) they are marked `superseded_by='2.0.0'` and no longer count for any week. Never delete them. |
| 17 | **The test bootstrap migrates the dev DB** | `tests/conftest.py::_bootstrap_test_database` runs `alembic upgrade head` against `data/openclaw.db` at collection, so a new migration is applied to the dev DB by the first test run — write migrations to be safe on real data before running any test. |
| 18 | **The dev DB is in WAL mode** | Recent writes sit in `data/openclaw.db-wal`; `cp data/openclaw.db x.db` gives a stale copy (missing columns a migration just added). Copy with the SQLite backup API (`src.backup(dst)`). |

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



