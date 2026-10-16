# Changelog

All notable changes to FishIntel / AquaIntel. Format follows the spirit of
Keep a Changelog; versions come from `core/version.py` (single source of truth).

## [2.6.0] — commercial hardening (in progress)

### Step 10 — role definitions, usable immediately
- **Three roles written to be posted as-is** in `docs/roles/`: **Commercial Lead
  (salmon trading networks)** — owns recruiting and converting 5–8 paid 90-day
  pilots, with explicit first-quarter targets and a blunt honesty requirement;
  **Enterprise & Security Engineer (SSO + SOC 2 path)** — owns SSO/SAML/OIDC,
  SOC 2 Type I→II readiness, per-tenant isolation and the production gaps
  (`docs/PRODUCTION_TRUTH.md` "Still open"), with the four-part definition of done
  for SSO; **Product Designer (field & mobile)** — owns the one-handed operator
  loop and honest offline capture, with the degraded-state design mandate.
- Each role states what success looks like in the first quarter as measurable
  targets, what the person needs, what the first 30 days are, and — deliberately —
  **what we will not ask them to do** (hide degraded data, advertise the deferred
  performance fee, write advice framing).
- `docs/roles/README.md` indexes the roles and gives the shared pre-call reading
  list plus the hiring filter: comfort with refusing to claim what we have not
  measured.

### Step 9 — GTM kit (ROI calculator in code, honest sales assets)
- **ROI calculator as real code**, not a slide: `core/gtm/roi.py` computes the case
  for four ICPs (producer, processor, desk, insurer) from formulas it publishes,
  and it **invents no market value** — every figure is either an input the customer
  supplied (`inputs_supplied`) or a clearly labelled assumption
  (`assumptions_used`), each line carrying its own `formula` and `inputs_used`.
  `GET /api/gtm/roi?icp=` shows the default case with the assumptions marked;
  `POST /api/gtm/roi` recomputes with the customer's numbers. `not_included` states
  that integration effort and unverified revenue are out of scope, and the
  disclosure says the platform asserts no market value.
- `GET /api/gtm/kit` lists the assets and the **live proof points** a seller can
  open on a call (`/api/indices`, `/api/accuracy`, `/api/data-freshness`,
  `/api/billing/catalog`, `/api/legal/data-licenses`).
- **Security & architecture one-pager** (`docs/GTM_SECURITY_ONE_PAGER.md`): data
  handling, tenancy/IDOR, SSRF guard, provenance — followed by an explicit
  **"what is NOT in place yet"** table (SSO, SOC 2, pen test, HA, per-tenant
  isolation). It states the principle: the rule that stops us inventing a MAPE stops
  us inventing a certification.
- **3-minute demo script** (`docs/GTM_DEMO_SCRIPT.md`): timed, with the exact words
  for the current "accuracy not yet published" state and a rehearsed objection table.
- **LinkedIn pack** (`docs/GTM_LINKEDIN_PACK.md`): three repeatable formats for a
  domain expert (not marketing), posting rules (never post a number you cannot
  link; never recommend), and eight seed topics.
- **Event playbook** (`docs/GTM_EVENTS.md`): AquaNor/NASF readiness checklist
  (8/4 weeks out), booth kit, the 90-second stand pitch, the 72-hour follow-up
  rule, and a "what NOT to do" list.
- **Tests:** `tests/test_gtm_roi.py` (12) — every line states its formula/inputs and
  is flagged as an assumption, defaults are reported as assumptions while supplied
  inputs are not, the maths is reproducible against hand-computed values, the module
  is checked not to embed upstream market series, validation of unknown ICPs/inputs
  and months, and the endpoint shapes.


- **The provenance boundary is now enforced, not remembered.** New
  `core/provenance_register.py` holds the **formal exempt register** (prefix →
  category + written reason; 18 entries across infrastructure, auth/billing,
  catalogue/meta, publication metadata, operational and admin) and
  `docs/provenance_baseline.json` freezes the non-exempt `/api` GET inventory:
  **238 routes → 31 exempt, 207 baselined, 0 unregistered**.
- **A ratchet so nothing can ship unnoticed:** `scripts/provenance_ratchet.py`
  (exit 1 on drift) plus `tests/test_provenance_ratchet.py`. A new data route must
  either carry provenance or be added to `EXEMPT` with a reason — a route in neither
  fails the gate, and the baseline is re-frozen only via an explicit `--update`.
- **A reusable pattern instead of per-route churn:**
  `core/market/provenance_envelope.py::with_provenance(source, degraded_reason=...)`.
  It attaches `data_provenance` to dict payloads, forces `is_live: false` when a
  degraded reason is given, leaves an existing (engine-set) envelope untouched, and
  passes non-dict results through.
- **Five more real routes carry provenance:** `/api/analytics/yoy-comparison`,
  `/api/treatment/efficacy-by-method`, `/api/feed-supply-chain/eudr-risk` (all
  honest degraded envelopes naming why they are not measurements) and
  `/api/futures/basis`, `/api/futures/term-structure` — where the decorator
  correctly *preserved* the engine's own more specific provenance
  ("SSB Seasonal Synthesis", `is_live: false`) rather than overwriting it.
- **Honest scope:** the register proves a decision was recorded, not that all 207
  baselined routes carry provenance today — the runtime measurement stays in
  `scripts/probe_liveness.py` (payload-shape classification), which the report
  documents. The ratchet prevents silent erosion; the probe reports the live
  residue.
- Docs: `docs/REPORT_LIVENESS.md` now carries the exempt register table, the
  ratchet commands and the list of routes given provenance in this step.


- **Data-licence register** `core/legal/data_licenses.py`: one entry per source with
  `allowed_uses`, `resale_allowed`, `attribution_required`, `ai_training_allowed`
  and named risks. Eight sources registered (Fiskeridir lice, SSB prices, Copernicus,
  NASA MUR SST, Fish Pool/Euronext futures, producer-contributed data, EUDR
  submissions, research literature).
- **It refuses to invent legal conclusions**: every entry defaults to
  `classification_status="pending_legal_review"`, and `check_use()` returns
  `allowed: false` (with `requires_legal_signoff: true`) for any use that has not
  been signed off — even when the licence would permit it. `compliance_summary()`
  therefore reports the honest state: **8 registered, 0 cleared**, and names exactly
  which sources may not be resold (that list is what blocks the Data & Assurance
  tier; `fish_pool_futures` is flagged as blocking any public futures display).
- **Signals-vs-advice boundary** published as structured data with a reusable
  `SIGNAL_DISCLOSER` string for every signal surface, explicit "what we are not"
  clauses and jurisdiction notes.
- **EU AI Act transparency notes** for the three AI systems actually in use
  (forecasting, RAG assistant, anomaly scoring) with per-system transparency,
  human-oversight and limitation-disclosure fields, an honest
  "limited-risk — pending legal confirmation" classification, and the prohibited
  practices we do not use.
- **DPA/GDPR scaffold** (roles, data categories, sub-processors, retention,
  transfers, rights, breach, AI-Act annex) plus the open questions for counsel.
- **Performance-fee deferral as an enforced flag** (`core/legal/performance_fee.py`,
  `FISHINTEL_PERFORMANCE_FEE_ENABLED` default off): the five conditions to enable it,
  the three things prohibited while deferred, and a test asserting **no plan
  advertises a performance fee**.
- **New endpoints:** `/api/legal/data-licenses` (+ `/{source}`), `/use-check`,
  `/advice-boundary`, `/ai-act`, `/performance-fee`.
- **Tests:** `tests/test_legal.py` (18) — register completeness (no duplicate keys,
  every use in the vocabulary, and every source behind a published index traceable
  to a licence entry), nothing cleared without a reviewer, uncleared-but-permitted
  uses refused, unknown source/use handling, resale conflict visibility, the
  deferral default and switch, and all endpoint shapes.
- Docs: `docs/ADVICE_BOUNDARY.md` (boundary, AI Act, DPA template, licences,
  performance fee, and what still needs a human).


- **Pilots are real entitlements, not flags.** `POST /api/admin/partners/{id}/onboard`
  grants a canonical plan through `core.billing.entitlement_sync.activate()` for a
  90-day window, so what a design partner sees is exactly what a paying customer
  gets. No new tier was added — `core/entitlements.py` stays the single plan table
  (rule 8).
- **Two new tables** (Alembic 018): `design_partners` (company, ICP, country, plan
  granted, window, status, paid/monthly price, reciprocity terms) and
  `partner_metrics` (name/value/target/unit/note).
- **Admin surfaces** (`Depends(require_admin)`): create, list (with `by_status` and
  `by_icp` funnel counts and the 5–8 pilot target), detail with the full metric
  history and the allowed status transitions, onboard, metrics, reciprocity, status.
- **Success-metric scorecards**: latest observation vs latest target per metric with
  a computed `achieved` flag — the evidence a pilot conversion is argued from.
- **Status machine enforced** (`prospect → onboarded → active → converted`, with
  `churned` and re-onboarding paths); an illegal transition is a 409, an unknown
  status a 422, and onboarding without an owning user a 422.
- **Data reciprocity** is captured *before* onboarding (dataset names, cadence,
  agreement reference, restrictions) — the mechanism that turns partner data into
  a moat rather than a one-way giveaway.
- **Tests:** `tests/test_partner_pilots.py` (18) — admin gating (anonymous and
  non-admin rejected), create validation, plan-alias normalisation (`pilot` →
  `professional`), onboarding without an owner rejected, onboarding granting a
  *real* entitlement (asserts `User.tier` changed), metric scoring, reciprocity
  requirements, and the status state machine.
- **A real bug found by the tests:** `days_remaining` was always `None` because
  SQLite returns datetimes naive, so the awareness check failed — fixed with a
  coercion helper (same class of bug that hit the freshness monitor).
- Docs: `docs/DESIGN_PARTNERS.md` — the runbook, the status machine and the
  per-ICP success metrics that decide conversion.


- **Agents are a first-class production service.** `docker-compose.prod.yml`
  declares `api` + `agents` (`python main.py --agents-only`) + `db` (TimescaleDB)
  + `web`, with required-secret guards (`:?`) so a misconfigured deploy fails at
  `up`. Previously the production image ran API-only and all 12 agents (ingest,
  forecasts, index publication) silently never executed.
- **`core/production_truth.py` + `scripts/verify_production_truth.py`** turn the
  documented gaps into checks with verdicts: production env + JWT secret length,
  agents service present, DB dialect/reachability/**migration head**, model +
  accuracy artifacts, and per-source freshness. Exit 1 on a critical failure, so it
  can gate a deploy.
- **It immediately caught a real drift:** this repository's dev DB had an EMPTY
  `alembic_version` (`DB at None, code head 017`). `tests/conftest.py` now
  reconciles missing ORM columns *and* stamps head for `create_all`-built dev/test
  DBs, while real deployments keep failing if they are behind. Re-run now reports
  `alembic_head: at head 017` with 0 failures.
- **TimescaleDB:** `docker/init-timescale.sql` creates the extension (plus helping
  indexes for the freshness queries). Hypertable conversion is deliberately *not*
  automated — it needs a real time column and a correct chunk interval, and a wrong
  conversion silently degrades plans; the verifier reports the count so "not yet
  converted" stays visible.
- **Per-source freshness dashboard:** `core/market/freshness_monitor.py` monitors
  12 sources (lice, SSB prices, export volumes, chlorophyll, bloom, futures,
  supply, price predictions, harvest timing, published indices, treatment outcomes,
  EUDR) with latest observation, staleness vs expected cadence and a concrete
  refresh hint. `GET /api/data-freshness` (public) and `/sources`. **A real bug was
  found by running it:** SQLite returns timestamps as ISO **strings**, so every
  source reported `unknown` until coercion was added.
- **Synthetic-data disclosure:** a source whose table holds only demo/seed rows is
  reported as `synthetic_only` — the dev DB's `ssb_weekly_prices` (52 demo rows) is
  correctly flagged rather than presented as live data.
- **Tests:** `tests/test_production_truth.py` (17) — agents declared in prod compose
  and the API-only topology flagged as a critical failure, production secret rules,
  alembic head = 017, artifact absence declared not hidden, freshness statuses,
  missing-table → unknown, synthetic-only flagging, timestamp coercion and the
  endpoints.
- Docs: `docs/PRODUCTION_TRUTH.md`; AGENTS.md known-gaps register updated.


- **`core/ml/accuracy_registry.py`** is the artifact store that makes the honesty
  rule operable: JSON artifacts under **`artifacts/accuracy/`** (tracked in git,
  deliberately not under the gitignored `data/`), validated against a published
  schema on both write *and* read — invalid artifacts are reported, never skipped.
- **`scripts/publish_accuracy.py`** produces a genuine artifact from a real
  walk-forward evaluation (seasonal-naive baseline on SSB weekly prices), with the
  prediction interval calibrated on the first 70% of year-back pairs and coverage
  measured **out-of-sample** on the remaining 30%.
- **A real honesty trap was found and closed:** the environment could not reach
  SSB, and the only locally persisted `ssb_weekly_prices` rows (52 of them) carry
  `source='demo_seed'` — i.e. synthetic. Publishing a MAPE from those would have
  fabricated an accuracy claim, so the script now filters on source, reports how
  many synthetic rows it ignored, and **exits non-zero writing nothing** when only
  synthetic data exists. Consequently `GET /api/accuracy` honestly returns
  `published: false` and names the command that fixes it.
- **New endpoints:** `GET /api/accuracy` (published metrics or an explicit
  not-yet-published statement), `/api/accuracy/method` (the artifact contract,
  evaluation protocol and prohibited practices), `/api/accuracy/artifacts/{id}`
  (verbatim, for audit).
- **Fallback disclosure is machine-readable**, not fine print: the response states
  the seasonal-naive fallback policy, whether foundation models are actually
  available (`torch` present) and whether a legacy gitignored `data/` artifact
  exists — noting that only the published registry may back a public claim.
- **Frontend:** public `/accuracy` page rendering published metrics, the
  not-published state with the publish command, and the fallback disclosure.
- **Tests:** `tests/test_accuracy_registry.py` (27) — schema validation (including
  each invalid-field class), publish/read-back, invalid files reported not hidden,
  empty registry claims nothing, the synthetic-source guard, determinism of the
  walk-forward maths on a known series, and every endpoint's honesty behaviour.
- Docs: `docs/ACCURACY.md`.


- **`AI-STI` (AquaIntel Salmon Transmission Index)** and **`AI-LPI` (AquaIntel Lice
  Pressure Index)** are published, versioned (method `1.0.0`) and reproducible:
  weighted component scores with published weights and scoring formulas, explicit
  component-level source attribution, and a **renormalising** aggregation — a
  component whose source is unavailable is named in `components_missing` and
  forces `provenance.is_live = false`. If *every* component is unavailable the
  index returns `value: null` instead of a fabricated number.
- **Sources are real:** Fiskeridir/SSB standing biomass and harvest (momentum vs
  year-over-year, with `raw.basis` when a year-back period is missing) and the lice
  emission-quota framework (`lice_quota_tracker.national_emission_overview`).
- **Bio→Price Weekly v1** (`core/market/bio_price_weekly.py`,
  `GET /api/indices/bio-price-weekly`): composes both indices with a supply panel
  and a live price panel into a weekly digest with an explicit
  `transmission.read`, a `caveats` list and a provenance block. `publish_week()`
  computes **and stores** both observations.
- **History is durable and immutable:** new `index_observations` table (Alembic
  017) with a unique constraint on `(index_code, week, version)`, so a published
  value cannot be silently restated and a method change is visible as a new
  version.
- **New endpoints:** `GET /api/indices`, `/ai-sti`, `/ai-lpi`,
  `/{code}/history`, `/methodology`, `/bio-price-weekly`, and admin
  `POST /api/indices/publish` (stable public permalinks `/indices/ai-sti`,
  `/indices/ai-lpi`).
- **Frontend:** public `/indices` page showing value, band, per-component weight
  and score, source, method version and a live/degraded badge with the degradation
  reason — the honesty layer made visible to a buyer.
- Docs: `docs/INDICES.md` publishes the full method, weights, bands, revision
  policy and limitations (including what is deliberately *not* yet a component).
- **Tests:** `tests/test_indices.py` (20) — method/version/weights contract, bands,
  per-component traceability, honest degradation (partial and total), idempotent
  history publishing, stable permalinks, 404 for unknown indices, and the digest's
  caveat/provenance coupling.


- **One catalog, one entitlement write.** `core/billing/stripe_catalog.py` derives
  the Stripe Products/Prices from `core/entitlements.py` (idempotent
  create-or-find), and `core/billing/entitlement_sync.py` is the single place a
  billing event becomes an entitlement — used by the real webhook **and** the
  mock path, so a paid plan cannot land differently depending on the door.
- **`stripe_billing.TIER_PRODUCTS` was a *third* tier table** (it drifted from
  `core/auth.py` and `core/valuechain/subscription.py`); it is now derived from
  the SSOT too.
- **Mock mode is explicit, never silent.** Without `STRIPE_SECRET_KEY` the catalog
  serves deterministic `price_mock_<plan>` ids with `"mock": true`, checkout
  returns a mock URL, and `POST /api/billing/webhook/mock` completes the chain
  (refused in production, token-guarded when `FISHINTEL_MOCK_BILLING_TOKEN` is
  set). The pricing page shows a banner instead of pretending prices are live.
- **Server-side plan resolution.** The webhook resolves the plan from the **price
  id** first, then metadata; both `aquaintel_plan` and the legacy `openclaw_tier`
  are read and written, so existing Stripe objects keep working.
- **New endpoints:** `GET /api/billing/catalog` (public pricing model),
  `POST /api/billing/webhook/mock`; checkout now accepts `?plan=<canonical key>`
  (legacy `?tier=` still works) and 400s on non-self-serve plans.
- **Public pricing page** `frontend/src/app/pricing/page.tsx` driven entirely by
  `/api/billing/catalog` (no hardcoded feature list), plus `api.billingCatalog()`
  and `api.billingCheckout()`.
- **Fixed a production-blocking schema drift:** the dev DB was missing
  `subscriptions.stripe_customer_id` (present in migration 002 but never applied
  to this box). `tests/conftest.py` now reconciles missing ORM columns
  automatically (the manual PRAGMA/ALTER loop AGENTS.md documents), and prints
  what it added — this is what makes the money-path tests deterministic.
- **Tests:** `tests/test_billing_money_path.py` (12) proves the full chain —
  catalog → checkout → webhook → entitlement → **the previously-blocked premium
  route now returning non-402** — plus persistence, cancellation → free,
  non-self-serve rejection, auth requirement and mock-token enforcement. No Stripe
  credentials required.
- Docs: `docs/BILLING.md`; `.env.example` gains the mock-billing vars and a note
  that the catalog is auto-created.


- **New `core/entitlements.py`** is the only definition of plans, prices, quotas,
  features and the paywall boundary. `core/auth.TIERS` and
  `core/valuechain/subscription.TIERS` are now *projections* of it.
  Before: `/api/tiers` imported **both** tables and served a merged,
  self-contradictory payload, and `intelligence` (present in one table only)
  silently ran on the **free** quota while priced at NOK 39,900/month.
- **7 canonical plans** — Insight (free), Operator, Desk (professional),
  Enterprise, Investor, Intelligence, plus the licensed Data & Assurance tier.
  The monthly limit is **derived** from the enforced per-day quota
  (`api_calls_per_day × 30`), removing the drift source. Legacy keys are kept for
  issued tokens/Stripe metadata; aliases (`premium`, `pro`, `pilot`, `growth`,
  `licence`, `market`, `institutional`, …) resolve via `normalize_plan()`.
- **Paywall enforced** for authenticated accounts on a curated
  `PREMIUM_PREFIXES` set (price outlook/forecast, futures, AIS, supply balance,
  contracts, event impact, harvest optimizer, feed supply chain, ensemble,
  compound scenarios, premium indices) → **402 + actionable upgrade payload**
  (`current_plan`, `suggested_plan`, `upgrade_url`). Anonymous browsing stays
  open — that is the funnel, and it is now the documented policy rather than an
  accident.
- **Gating and quota have independent kill-switches**
  (`FISHINTEL_ENFORCE_ROUTE_GATING`, `FISHINTEL_ENFORCE_QUOTAS`). The first
  implementation nested gating inside the quota switch, so a suite-wide
  `ENFORCE_QUOTAS=0` silently disabled the paywall — caught by the new tests and
  restructured.
- **New endpoints**: `GET /api/entitlements/plans` (public pricing model),
  `/me` (caller's plan, usage, upgrade path), `/check?path=` (UI affordances).
- **Alembic 016** normalises legacy tier strings in `users`, `subscriptions`,
  `api_keys` and `performance_fees` to canonical keys, so a row holding
  `"premium"` cannot silently fall back to the free quota.
- **Tests**: `tests/test_entitlements.py` (47 tests) proves the two projections
  agree, the monthly figure is derived, both tier endpoints agree, `intelligence`
  has its own quota, alias resolution, the paywall policy, the 402/429 payloads
  and the kill-switches. The assertions in `tests/test_tier_quota.py` that
  *pinned the conflict* were replaced.
- Docs: `docs/ENTITLEMENTS.md` (model, policy, endpoints, enforcement, migration,
  known limitations).



### Added
- `scripts/probe_liveness.py` — walks every parameterless GET route in-process
  and records the provenance it ACTUALLY returns (live / degraded / simulated /
  no_provenance / error). Writes `docs/REPORT_LIVENESS.md` +
  `docs/liveness_report.json`. Measurement, not assertion: 219 routes probed.
- `tests/test_route_liveness_contract.py` — deterministic guards for every bug
  the audit found (no network required).

### Fixed (crashes the audit surfaced — 6 defect classes across 9 endpoints, none covered by the suite)
- `core/routers/billing_routes.py` (x4): called `get_current_user(creds)` while
  the signature is `(request, credentials)`, so `credentials` stayed a `Depends`
  object — every billing endpoint raised AttributeError instead of returning 401.
- `compliance/compliance_agent.py`: `/api/audit` read non-existent
  `AuditLog.event_type` / `actor` / `detail` (500). Maps `action` / `user_id` /
  `details`.
- `core/routers/analytics_routes.py`: `/api/self-improvement/proposals` queried
  `AuditLog.event_type` and read `l.detail` (500).
- `core/routers/alerts_routes.py`: `/api/parametric/risk-profile` never awaited
  the async engine, returning a coroutine (500).
- `core/market/lice_quota_tracker.py`: queried `Locality.company`, which does not
  exist (the column is `owner_company`) — every production area silently
  returned an empty list.
- `core/market/efficacy_marketplace.py`: PostgreSQL-only
  `EXTRACT(... FROM ...)` raw SQL raised OperationalError on SQLite, so
  `/api/efficacy/*` failed in dev and CI.

### Fixed (honesty — AGENTS.md rules 1 and 3)
- `core/market/fiskeridir_biomass.py`: `_generate_fallback()` produced
  `random.uniform` placeholders with `report_year` set, so `is_live` was True and
  `get_national_summary()` reported `DataProvenance.live(..., confidence=0.95)`
  for randomly generated data presented as "Fiskeridirektoratet". Fallback
  records are now flagged `is_synthetic` and provenance is `simulated`
  (confidence 0.0) unless the ArcGIS feed really answered.
- `core/market/biomass_tracker.py`: `fetch_biomass_data()` ALWAYS returned the
  hardcoded historical-pattern estimate while its docstring claimed it fetched
  from Fiskeridirektoratet. It now prefers the real ArcGIS client and records
  which path ran; `/api/market/biomass` emits honest provenance (never `live`,
  because its supply metrics are model estimates).

### Fixed (frontend)
- `frontend/src/lib/api.ts`: the client sent NO `Authorization` header and
  nothing read the token stored at login, so user-scoped routes (billing, API
  keys, webhooks) and the per-user tier quota were unreachable from the UI. The
  stored JWT is now attached, and a 401 clears a stale token and routes to
  `/login` once. Keys exported as `AUTH_TOKEN_KEY` / `AUTH_USER_KEY`.
- `/market` gains a Biomass Supply Tracker card that labels its derived figures
  as estimates and renders the backend's own provenance reason.

### Changed (provenance coverage sweep — AGENTS.md rule 3)
- The liveness audit found **90 routes returning data with no provenance envelope
  at all**. This increment fixes the highest-value cluster: **10 `/api/market/*`
  routes** (`price-forecast`, `seasonal`, `exports`, `price-outlook/multi`,
  `futures-curve`, `ssb-price-history`, `ssb-seasonal`, `export-destinations`,
  `spot-price`, `forward-curve`) and the shared `core/market/price_feed_hub.py`
  they call. Live is claimed only when SSB actually returned rows
  (`DataProvenance.from_records`); model paths (forecasts, synthesized forward
  curves, seasonal baselines) are `degraded` with an explicit reason.
- `not covered here`: `hedger-signals` / `prediction-history` return bare arrays
  pinned by e2e contracts (`api-contracts.spec.ts`), so adding an envelope needs
  a coordinated contract change; `feed-status`, `/api/health`, `/api/metrics`,
  `/api/auth/*`, `/api/tiers`, `/api/disclaimer` are plumbing/config where a
  provenance envelope is not meaningful. The remaining backlog is listed in
  `docs/REPORT_LIVENESS.md`.


### Changed (provenance coverage sweep, increment 2 — ais / sentiment / production)
- 5 more dict-returning routes now carry provenance: `/api/ais/harvest-intelligence`
  and `/api/ais/supply-intelligence` (live only when AIS positions were actually
  ingested), `/api/sentiment/summary` and `/api/sentiment/poll` (live only when
  articles were analysed), and `/api/production/summary` (Fiskeridirektoratet
  open data). Additive keys only; a shared `_ais_provenance` helper reuses the
  `from_records` primitive.
- `scripts/probe_liveness.py` now records each response's payload shape, so the
  remaining backlog is classified rather than guessed: of the 72 provenance-less
  routes, **41 are dict-shaped** (fixable with an additive key) and **30 are
  list-shaped** (a bare array cannot carry an envelope — that is a coordinated
  contract change: frontend auto-unwrap, `e2e/api-contracts.spec.ts`, and the
  Linux-generated visual baselines the repo forbids regenerating on Windows).
- Measured: `no_provenance` 83 → 72, `live` 43 → 46, `degraded` 21 → 27.
  (Counts also move with network availability — 57 rows timed out this run.)


### Changed (provenance sweep, increment 3 — global / parametric / investor / ocean)
- 10 more dict-returning routes now carry provenance. `/api/global/{farms,lice,
  bloom-risk,disease-geo}` share a `_global_geo_provenance` helper (live only when
  at least one country monitor actually contributed a GeoJSON feature — these
  routes swallow per-source failures). `/api/ocean/forecast` is live only when
  MET.no returned forecast points. `/api/parametric/{dashboard,risk-profile}` and
  the three `/api/investor/event-impact/*` routes are `degraded` with explicit
  reasons (derived trigger/payout models and modelled counterfactuals are
  estimates, not quoted prices or observed market moves).
- `not covered here`: `/api/parametric/triggers` turns out to return a bare
  **list** (the probe had classified it as a dict), so it joins the list-shaped
  backlog along with `/api/ocean/currents/status` and `/api/ocean/waves/status`
  (client-status metadata, where a provenance envelope would be meaningless).
- Measured: `no_provenance` 72 → 65, `live` 46 → 53, `degraded` 27 → 30.

### Changed (provenance sweep, increment 4 — the remaining additive half + a latent bug)
- 12 more dict-returning routes carry provenance, closing the additive half of
  the backlog: `/api/farm-graph/{summary,map-data}`, `/api/ras/{summary,timeline}`,
  `/api/regulatory/traffic-light/{simulate,all-scenarios}`, `/api/climate/projections`,
  `/api/contracts/hedge-signals`, `/api/twin/status`, `/api/feed-cost/official-history`,
  `/api/anomaly/alerts`, `/api/self-improvement/proposals`. Model artefacts
  (networks, projections, scenarios, contract risk, detectors) are `degraded` with
  explicit reasons; the **digital twin** is honestly `simulated` (it is a
  simulation of farm cohorts, not measured data); official Fiskeridirektoratet
  series use `from_records`.
- **Bug found while probing**: `core/market/climate_risk_engine.py` queried
  `BloomRiskAssessment.sst`, but the column is `sst_value` — every climate
  projection silently degraded. Fixed.
- Measured: `no_provenance` 65 → **50**, `degraded` 30 → 42, `simulated` 1.
  (`live` reads 53 → 48 only because 60 rows timed out this run vs 52 — network
  variance, not a regression.)
- Known remaining dialect gap (documented, not fixed): the same function groups by
  SQLite-only `func.strftime("%Y-%m", ...)`, which will not compile on the
  PostgreSQL production target.

### Changed (docs truth pass)
- `PROJECT_STATUS.md`: measured counts (322 operations / 316 unique paths, 762
  tests) and real frontend versions (Next 16.4, React 19.1).
- `docs/NEXT_STEPS_PLAN.md`: clone path `AquaIntel` -> `FishIntel`.
- `docs/RESEARCH_SYNTHESIS.md`: the sync-`Session` claim is marked RESOLVED
  (0 core files import `sqlalchemy.orm.Session`).
- `docs/DEPLOYMENT.md` + `docker-compose.staging.yml`: agents run as a SEPARATE
  service (staging parity); single-container deployments otherwise never ingest
  data.


## [2.3.0] — 2026-10-13 (post-review hardening session)

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

### Fixed (NEW finding — /trader typing + feed composite fiction, slice 10)
- `/trader` was fully `any` (16); typed against the real endpoints.
  `priceOf` gained a small structural `CurvePointLike` type.
- **Feed-cost composite KPI was dead**: the page read
  `feedIndex.composite_index` / `.alert` — the real payload
  (`feed_cost_engine.compute_composite_index`) emits `current_index` /
  `current_date` / `volatility_alert` / `volatility_12m`. KPI now renders
  `current_index` + a volatility-alert delta.
- New client types for five previously-untyped APIs:
  `MarketSpotPrice`, `MarketForwardCurve` (+`ForwardCurvePoint`),
  `FeedCostCompositeIndex`, `EventImpactResult` (+`EventCompanyImpact`),
  `SavedScenario`; `signals()` now returns `Signal[]` (a dead
  `{signals}` fallback removed from the trader + chat pages).
- `SentimentSummary` gained the real `signals` key (`SentimentSignalRow`).
- `/trader` fully typed (16 `any`s → 0, eslint-disable removed);
  error rendering uses an `"error" in result` discriminator; dead
  `predicted_price` / `pt.label` aliases removed.
- Regression nets: 5 backend tests (`TestTraderContracts` incl. a
  save/list/delete scenario round-trip) + 4 e2e contract assertions
  (spot-price, forward-curve, composite-index real keys,
  event-impact/isa envelope). tsc clean, eslint 0 errors (6 pre-existing
  warnings), visual 4/4, targeted tests 12 passed, ruff clean, build green.

### Fixed (NEW finding — /competitiveness type fiction, slice 9)
- `CompetitivenessIndex`/`CompetitivenessOrigin` were fiction
  (`production_cost_nok_kg`, `freight_cost`, `tariff_usd_percent`,
  `total_cif_usd_kg`, `competitiveness_vs_norway`, `insights` on the
  origin row — none of these exist). The real payload (from
  `competitiveness_engine._to_dict`) carries `us_spot_usd_kg`,
  `data_quality: "live" | "stale_fallback"`, `fallback_value`,
  `source_date` and origins with `rank/flag/currency/local_cost_per_kg/
  fx_rate_to_usd/production_cost_usd/tariff_pct/tariff_cost_usd/
  freight_usd/total_delivered_usd/margin_usd/margin_pct`. Rewritten.
- `competitivenessTariffScenario` was untyped; added
  `CompetitivenessScenarioResponse` (`scenario_origins` with
  scenario_rank/delivered_cost_usd/rank_change/baseline_rank) and
  annotated the client.
- Scenario row also read a nonexistent `o.origin` (falling back to
  `o.country`) — now reads `o.country` directly.
- `/competitiveness` fully typed (15 `any`s → 0, eslint-disable removed;
  `DataTable` columns typed as `Column<CompetitivenessOrigin>`).
- Regression nets: 2 backend tests (`TestCompetitivenessContract`) + 2 e2e
  contract assertions (origin-index real keys incl. old-fiction
  must-not-exist, tariff-scenario re-ranking). Local verification:
  tsc clean, eslint 0 errors, visual 4/4, targeted tests 7 passed,
  ruff clean, build green. Warnings are pre-existing only.

### Fixed (NEW finding — /investor typing + GlobalSupply fiction, slice 8)
- The `GlobalSupply` type was fiction (`countries[].production_2025_kt`,
  `total_global_kt` — neither exists in the payload) while the page and
  KPI strip read the real `balance`, `supply_deficit_pct`,
  `norway_premium_pct`, `global_salmon_usd_kg`. Rewritten to match
  `global_supply_engine.to_dict` (incl. `GlobalSupplyCountry`).
- `DiseaseCompanyCounts` keys are lowercase (`isa`/`pd`) but the investor
  page read uppercase `ISA`/`PD` — **disease counters always rendered
  "Clear"** even when outbreaks existed. Page now reads `isa`/`pd`.
- `equityPrices`, `regimeStates`, `esgScores` were untyped; added
  `EquityPriceResponse` and `RegimeState` types (real shapes from the
  routes) and annotated the client; `esgScores` now returns
  `EsgCompanyScores`.
- `/investor` fully typed (18 `any`s → 0, eslint-disable removed);
  `DashboardSupply` is now an alias of the corrected `GlobalSupply`
  (the dashboard layer used to re-patch the fiction with optional
  overrides).
- Regression nets: 5 backend tests (`TestInvestorContracts`) + 5 e2e
  contract assertions (global-supply, disease by-company lowercase keys,
  regime states, equity prices, esg scores).
- Local verification: tsc clean, eslint 0 errors, visual 4/4,
  test_routers 56 passed, ruff clean, build green.

### Fixed (NEW finding — /brief + anomaly contract fiction, slice 7)
- `MorningBrief` / `BriefSection` types were fiction (`title`, `key_risks`,
  `market_sentiment`, `sections[].items[]`, `section_num`) while the real
  response model is `{generated_at, greeting, market_mood, top_insight,
  sections[{title, icon, headline, detail, sentiment, value}]}`. The page
  itself already read the real keys — now the types match it.
- `AnomalyScores` type was fiction (`lice_zscore`/`lice_risk`/
  `mortality_risk`/`sst_anomaly`) — the real payload is
  `{composite_score, risk_level, n_anomalies, summary, anomalies[],
  component_scores{}}` (no consumer read the fictional keys).
- `/brief` page fixes that fell out of typing:
  - the Early Warning card read `anomalyData.breakdown` (nonexistent) →
    the **Key Risks bars never rendered**; now uses the real
    `component_scores`;
  - source attribution read a nonexistent `anomalyData.sources` array →
    now derives from the real `anomalies[].source`;
  - `FeedCostLatest` type said `trend` while the payload emits
    `margin_trend` (the Feed Pressure delta never showed) — corrected.
- `/brief` fully typed (21 `any`s → 0, eslint-disable removed);
  `ScoredSection` documents the page-local `_priority` field.
- Regression nets: 2 backend tests (brief response-model keys, anomaly
  component breakdown) + 3 e2e contract assertions (brief, anomaly,
  feed-cost incl. documented 404).
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  test_routers 51 passed, ruff clean, build 68/68.

### Fixed (NEW finding — /feed-supply-chain typing + hand-rolled provenance, slice 6)
- `/api/feed-supply-chain/summary` now carries the platform
  **DataProvenance** shape: it used to hand-roll
  `{source, freshness: "model_based", confidence, note}` — no `is_live`,
  no `fallback_reason`. It is honestly **degraded** (model-based
  composition with approximate commodity prices — never live), with the
  reason attached; the page footer keeps reading source/confidence.
- `/feed-supply-chain` fully typed (24 `any`s → 0, eslint-disable
  removed): new `FeedSupplyChainSummary` / `FeedCompositionRow` /
  `FeedScenarioRow` / `FeedEudrRisk` / `FeedSankey{Node,Link}` types;
  `api.feedSupplyChainSummary` typed.
- Two real display bugs fixed while typing:
  - the cost-breakdown list called `.sort()` **on the state array**
    during render, mutating the payload and re-ordering the stacked bar /
    legend above it — now sorts a copy;
  - the Sankey component read a nonexistent `data.stages` array (so stage
    labels never rendered) — labels now derive from the backend's
    documented staging (origin → ingredient → feed mill → farm).
- Regression nets: backend test pins the standardized provenance
  (`is_live: false` + `fallback_reason` + `schema_version`) and the
  payload keys; e2e assertion against the real backend.
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  test_routers 49 passed, ruff clean, build 68/68.

### Fixed (NEW finding — /disease contract fiction + permanently-green PA displays, slice 5)
- `/disease` typed and corrected against the real Mattilsynet payloads:
  - The **ISA/PD KPI counters were always 0** — they matched `disease ===
    "ISA"`/`"PD"` while the API sends display names ("Infectious Salmon
    Anaemia (ISA)"). Now matched on the display names (case-insensitive).
  - **The PA 1–13 status grid and the PA heatmap could never colour a
    cell**: the outbreak payload identifies cases per *locality* and
    exposes no production-area field, so both rendered a permanently
    "Clear"/0 picture. The grid is replaced by a real **"Active Cases by
    Disease"** breakdown (from the payload's `by_disease` counts) and the
    heatmap by an explicit *Unavailable* card that states why (no PA field
    in the source) — no invented PA data.
  - Global alert rows read `a.date` (real key `report_date`) — the date
    never rendered; also `a.type` (nonexistent) removed.
  - Outbreak rows read `c.disease_type`/`c.locality`/`production_area`
    (none exist) — now the real `disease`/`locality_name`.
  - Types corrected/added: `DiseaseNorway`, `DiseaseOutbreak`,
    `DiseaseAlerts`/`DiseaseAlertRow`, `DiseaseTreatments`/
    `DiseaseTreatmentReport`; the `YoYComparison` type was fiction
    (`{current: number[], delta_pct}`) → real per-week
    `{current_year: [{week, value}], previous_year, two_years_ago}`.
  - `api.diseaseAlerts/diseaseTreatments/yoyComparison` now typed; page
    eslint-disable removed (0 `any`).
- Regression nets: 4 new backend-backed `api-contracts.spec.ts`
  assertions (norway `by_disease`+outbreak keys, alerts `report_date`,
  treatments rows, yoy week/value series).
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  routers + api_routes green, build 68/68.

### Fixed (NEW finding — disease/leaders/compare contract fiction, slice 4)
- **`/api/disease/by-company` envelope corrected** (same class as
  smolt-forecast): `data_provenance` used to be injected INTO the
  per-company map — a provenance object appearing as if it were a company
  (and consumers summing over it). Now
  `{companies: {name: {total, isa, pd, other, localities}}, count,
  data_provenance}`. Consumers updated: dashboard count, `/disease`
  (its company list was silently EMPTY — it read `byCompany.companies` as
  an array and `c.company` which never existed), `/leaders`, `/investor`,
  `/compare`.
- **`LeaderEntry` type corrected**: it described a nonexistent shape
  (`company_name`/`lice_avg`/`production_tonnes`/`lice_percentile`/
  `esg_score`/`verdict`) while the real `/api/leaders/top100` rows are
  `name`/`avg_lice`/`performance_score`/`production_volume_tonnes`/… —
  `/compare` now consumes the real typed rows.
- **`/compare` fully typed** (29 `any`s → 0, eslint-disable removed):
  typed company selector props, ESG cache (`EsgCompanyScore`), disease map
  (`DiseaseCompanyCounts`), radar datasets; fixed the ESG radar/score
  reading `total_score` (the real key is `total` — the ESG radar dimension
  silently fell back to 0.5 for every company).
- New `EsgCompanyScore` type + typed `api.esgCompany`.
- Regression nets: backend test pins the disease envelope (incl. "no
  provenance object masquerading as a company") + e2e assertion against
  the real backend.
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4,
  test_routers 48 passed, ruff clean.

### Fixed (NEW finding — /price-outlook + /scenarios contract fiction, same class as A1/A2)
- `/price-outlook` sub-sections read invented fields; typed the page and
  corrected them:
  - Prediction Track Record read `date`/`actual`/`error_pct` — real rows
    (`PricePrediction`) have `created_at`/`current_spot_nok`, so every row
    showed "Actual: 0" and a garbage error %. Now reads the real keys and
    computes the error against the real actual.
  - "Price Drivers Explained" read `explanation`/`factors`/`drivers` — the
    TFT route returns `top_drivers[{feature, importance}]`, so the block
    never rendered. Now wired to the real keys (attention importance).
  - Multi-horizon table read `change_pct`/`predicted_price` — rows carry
    neither; the Change column showed 0.0% for every horizon. Now derived
    from the payload's `current_spot_nok`.
  - `PriceOutlook.scenarios` type said `Record<string, number[]>` while the
    engine emits percentile floats (p10…p90) — corrected; scenario bar
    width now comes from a typed helper.
  - `PriceOutlook` direction is `"up"|"down"|"flat"` — the page compared
    against `"bullish"`/`"bearish"` (dead branches) and passed the numeric
    `signals.combined` where a string was expected; both corrected.
- `/scenarios` local view models (`OutlookResult`/`HorizonPoint`) described
  the same fictional fields with `(h as any)` casts throughout; rebuilt on
  the real typed payloads with boundary normalisation (multi rows mapped to
  a typed view model; `confidence_interval` derived from real `bands.p80`).
  Also fixed: the biomass scenario cards read `mab`/`utilization`/
  `harvest_delta` (fiction) and multiplied the already-percentage
  `utilization_pct` by 100 (would have shown 8210%); now shows National MAB,
  Utilization and Forecast Biomass from the real keys.
- Regression nets: 4 new backend-backed `api-contracts.spec.ts` assertions
  (multi horizon rows, prediction-history list + real row keys, explain
  `top_drivers` incl. the documented 503 degraded path, futures-curve
  `price_nok` rows).
- Local verification: tsc clean, eslint 0 errors, visual baselines 4/4.

### Fixed (NEW finding — /market page contract fiction, same class as the supply fix)
- `frontend/src/app/market/page.tsx` was consuming **six** endpoints
  through invented shapes; each mismatch produced a silent-empty widget
  or a permanently-skeletoned section:
  - `/api/market/hedger-signals` returns a LIST → page read
    `{signals:[…]}` (always empty). Now consumes the list; the badge maps
    the real `direction` (HEDGE/UNHEDGE) and the bar shows real
    `strength` (0-1).
  - `/api/market/export-destinations` returns `destinations` as a DICT
    keyed by country code → page read a list (`.length` undefined →
    eternal skeleton). Converted at the boundary with computed share_pct
    from real `total_tonnes`/`total_nok_millions`.
  - `/api/ais/harvest-intelligence` real shape is
    `total_vessels/summary/harvest_signals_72h/…` → the old
    `AISHarvestIntel` type (active_vessels/recent_signals) was fiction and
    the whole AIS card rendered empty. Type corrected to
    `AISHarvestIntelligence`; card now shows Vessels Tracked, Harvesting
    Now, Treating Now, Supply Pressure + real 72h signal rows.
  - `/api/sentiment/summary` real shape (`avg_sentiment_24h`,
    `sentiment_trend`, `articles_24h`) → `SentimentSummary` type was
    fiction; card showed "Neutral / 0 articles" forever. Fixed type + card
    (score, trend, article count).
  - `/api/macro/snapshot` and `/api/macro/series/{name}`: `MacroSnapshot`
    (series/unit/source) and `MacroSeries` types were fiction; corrected
    to the real `{indices, benchmarks, yoy_changes, alerts: string[]}`
    and `{name, data:[{date,value}]}` shapes; the market Macro widget and
    dashboard types now compile against reality.
  - `SSBPriceHistory` type said `price_nok_kg/week:number` while the route
    emits `price_nok/week:"W13"` — corrected.
- AIS dashboard consumers updated: `DashboardAIS` no longer extends the
  fictional type (real `AISHarvestSignalRow[]` union, honest
  `vessel`/`farm_name` fields in the top-vessel line).
- Regression nets: 6 new backend-backed `api-contracts.spec.ts`
  assertions pin every corrected shape (price_nok rows, destinations
  dict, hedger list, AIS keys, sentiment keys, macro keys incl. the
  documented 404 degraded path).
- Local verification: tsc clean, eslint 0 errors, visual baselines
  re-verified (the /market baseline renders unchanged under the stubs).

### Fixed (NEW finding during the L5 migration — supply-forecast contract fiction)
- `/api/supply/smolt-forecast` returned a **bare list** (the old
  `isinstance(result, dict)` provenance guard could never fire) while the
  frontend type, the api-docs sample and the page all described *three
  different fictional shapes* — the smolt section silently rendered
  "No data" against the real backend. The route now returns the
  documented envelope `{pipeline[], horizon_months, total_harvest_tonnes,
  data_provenance}` (OpenAPI re-frozen, 2-line description-only diff;
  in-repo consumers verified).
- Same defect class on `/api/supply/cohort-timeline` (bare list, no
  provenance) → now `{cohorts[], count, data_provenance}`.
- `frontend/src/app/supply-forecast/page.tsx`: reads the real fields —
  the cohort volume column showed "—" for every row because it read a
  `projected_harvest_tonnes` key that cohorts don't have (now
  `harvest_tonnes`); removed other fictional fields (`intake_month`,
  `expected_harvest`, `monthly_projections`, `smolt_releases`).
- The header badge was hardcoded `source="Smolt Model" quality="live"`
  → now provenance-driven from the payload (no claim when the fetch
  fails).
- The page is fully typed (state + maps, eslint-disable removed) via new
  `SmoltPipelinePoint` / `SmoltForecastResponse` / `SmoltCohortRow` /
  `SmoltCohortTimeline` / `SmoltDemandBalance` / `SupplySummary`
  interfaces; the fictional `SmoltForecast` type is gone.
- Regression nets: backend tests pin the envelopes + pipeline point keys
  (test_routers, test_api_routes); e2e `api-contracts.spec.ts` asserts
  the envelopes against the real backend; new
  `frontend/e2e/supply-forecast-contract.spec.ts` (stubbed, no backend)
  pins that the page renders real pipeline rows, the cohort volume
  column, and a payload-driven badge — and shows no badge at all when
  the payloads fail.

### Changed (review L5/L7/L8 — bounded slices of the backlog item)
- **L5 (typing slice):** new `ChinaDemand*` interfaces in
  `frontend/src/types/api.ts` (snapshot / signals / impact / suppliers /
  momentum, incl. the `is_live` contract) mirroring the engine payloads;
  `api.chinaDemand*` client methods are now typed;
  `frontend/src/app/china-demand/page.tsx` dropped its `any` state/maps
  and eslint-disable entirely (typed state + `?? 0` narrowing helpers),
  plus removed an unused `ProvenanceWrapped` import in `api.ts`. The
  remaining ~460 `any` usages elsewhere stay on the backlog.
- **L7 (observability slice):** verified the Prometheus endpoint — it
  exists whenever the (locked) instrumentator dependency is installed,
  which is true in CI and the Docker image; new `tests/test_metrics.py`
  asserts `/api/metrics/prometheus` serves text/plain metrics and stays
  out of the frozen OpenAPI contract (skips locally if the dependency is
  absent). The china-demand snapshot log now carries the `live` flag.
- **L8 (dependency-drift note):** `requirements.txt` gained an explicit
  policy header: `>=` bounds are for local dev, `requirements.lock` is
  the reproducible set used by Docker/CI, and the exact `uv pip compile`
  command to re-generate the lock after changing the file.

### Added (review L4 — provenance contract net for the R10 bug class)
- Shared records-based provenance helper
  `core.market.data_provenance.from_records(records, ...)`: live only
  when raw records were actually returned (never on derived/rounded
  values that can legitimately be 0) — `_china_provenance` is the first
  consumer; future domains with the same "records or estimates" shape
  should reuse it instead of pasting `DataProvenance.live(...)`.
- New `tests/test_provenance_contract.py` (8 tests): recursive payload
  walker that FAILS whenever a payload with `is_live: false` contains a
  "LIVE" string anywhere — pinned on the degraded engine snapshot, the
  degraded supplier-breakdown rows, and all three degraded
  `/api/china/*` route payloads (the R10 bug left nested engine claims
  asserting LIVE while the route said degraded) — plus the helper's
  live/degraded/None semantics.

### Fixed (review L6 — docs/PLATFORM_STATUS.md was UTF-16)
- Renormalized to UTF-8 (no BOM, LF endings; 24,862 → 12,658 bytes) so
  grep/diff tooling works on it. Content unchanged.

### Fixed (review M7 + L2 — stale CHANGELOG claim + dead code)
- CHANGELOG R10 entry corrected: the badge ships `role="img"` (not
  `role="status"`) and the `title` fallback was removed in the M4 fix —
  annotated as a dated correction instead of silently rewriting history.
- `ChinaDemandEngine.get_top_suppliers` deleted (dead code, zero callers;
  the supplier breakdown is already part of `get_snapshot` via
  `/api/china/demand`).
- `get_supply_impact` docstring no longer claims "Uses LIVE SSB price
  data" unconditionally — it documents the degraded paths and that
  honest provenance is attached by the route layer.

### Fixed (review M5 — degraded snapshots pinned the platform for the full TTL)
- `ChinaDemandEngine.get_snapshot` split into a cache probe
  (`_cached_snapshot_if_fresh`) + `_fetch_snapshot_locked`:
  - **Negative-cache TTL:** degraded snapshots (no SSB 08799 records)
    now cache for 10 minutes instead of the full 2-hour data TTL, so
    recovery after an SSB outage takes minutes.
  - **Single-flight:** a lazily-created per-event-loop `asyncio.Lock`
    prevents concurrent cold calls from double-fetching the upstream
    (with a post-acquire cache re-check).
- New `tests/test_china_demand_cache.py` (5 tests, fake fetcher — no
  network): degraded TTL expiry + recovery to LIVE, LIVE keeps the 2h
  TTL, TTL ordering, and both single-flight cases (concurrent cold calls
  fetch exactly once, degraded fetch included).

### Changed (repo hygiene — review H3 + M6)
- Untracked the `.hypothesis` cache (5,178 files; already in `.gitignore`,
  so CI/repo weight drops without losing anything — the local cache stays
  on disk for pytest runs). `chore(repo)` commit `be3cea8`.
- PR #2 ("Session 38: Wire welfare/NorKyst/PACE endpoints + ErrorBoundary
  sweep", branch `claude/happy-curie`) closed as **superseded** with a
  documented evidence comment: 6-month-old conflicting branch (`mergeable:
  CONFLICTING`, master 96 commits ahead, every file in its 90-file diff
  rewritten since) whose headline features already exist in master —
  welfare SWIM scores (`/api/welfare/score/{pa}` in farm_routes), NorKyst800
  v3 (`/api/ocean/norkyst/current`) and NASA PACE
  (`/api/satellite/pace/chlorophyll`) in ocean_routes, and the
  JWT-fail-fast/auth hardening in `core/auth.py`.
- Stale remote branches deleted: `claude/happy-curie` (closed PR #2) and
  `claude/cool-cray` (PR #1, merged). Remote now tracks only `master`.

### Fixed (review M4 — DataQualityBadge mislabels + tooltip duplication)
- `qualityFromProvenance` now maps by provenance STATE, never by
  confidence thresholds: `is_live` → "Live", `source === "simulated"` →
  "Simulated", everything else → "Degraded". Previously a degraded
  payload with confidence < 0.4 was falsely labelled "Synthetic" (violet
  badge); low-confidence degraded fallbacks now say "Degraded" (server
  states: `core/market/data_provenance.py`). "Synthetic" stays reachable
  only via the explicit `quality` prop.
- Removed the native `title` attribute that duplicated the custom
  group-hover/group-focus-within tooltip (one tooltip, keyboard
  accessible); `role="img"` + `aria-label` WCAG semantics kept.
- Visible `focus-visible` ring added for the keyboard-focusable badge.
- Regression-pinned in `frontend/e2e/china-demand-honesty.spec.ts`
  (degraded stub deliberately uses confidence 0.3: badge must read
  "Degraded", never "Synthetic"; no `span[role="img"][title]` elements;
  focus-ring class present; live stub → "Live").

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
- `DataQualityBadge` now carries WCAG semantics: `role="img"` with an
  `aria-label` (quality, confidence, source, note) — every existing
  consumer inherits the improvement. (Correction, 2026-10-13: this entry
  originally said `role="status"` plus a `title` fallback; the shipped
  implementation used `role="img"`, and the title fallback was later
  removed as a duplicate tooltip in the M4 fix — see the post-review
  session entry at the top of this file.)
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
  `aquaintel_tour_completed`; the first-visit wizard otherwise intercepts pointer
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
