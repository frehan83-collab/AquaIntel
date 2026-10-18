# HANDOVER â€” takeover brief for the next coding module

> **Verified at commit `f04e79a` (branch `master`).** The WS-1 figures below were
> measured on the working tree before the WS-1 commit (2026-10-16, see Â§5):
> migrations at head `019`, fast gate 211 passed + 1 network skip, Â§6 traps 11â€“15.
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
> **WS-22 part 2 landed 2026-10-18:** competitiveness FX fallbacks, per-model
> `foundation_models_available`, newest-first disease list, and Mattilsynet merged
> into `/api/disease/alerts` with per-source provenance;
> `tests/test_ws22_data_claims.py` joined the fast gate.
> Every number below was measured, not copied from an older doc. Re-verify with the
> commands in Â§2 before trusting them.
>
> Read order: **this file** â†’ `AGENTS.md` (authoritative rules) â†’
> `PROJECT_STATUS.md` (what is shipped) â†’ `CHANGELOG.md` (why) â†’ the per-area docs
> named in Â§3.

---

## 1. Current state (measured at `f04e79a`)

| Dimension | Value |
|---|---|
| Platform version | `2.6.0` |
| OpenAPI surface | **352 paths** (`docs/openapi.frozen.json`; WS-29 added two, WS-34 one) |
| Tests | **1435 collected** (pytest --collect-only, 2026-10-18 after WS-28a/30-40) |
| Alembic migrations | **23** (head 023, WS-39) |
| Router modules | **38** (`core/routers/`) |
| Engine modules | **80** (`core/market/`, +`margin_bridge.py`, +`fx_rates.py`, +`company_facts.py`) |
| Frontend routes | **68** page files |
| Production topology | `docker-compose.prod.yml`: `api` + `agents` + `db` (TimescaleDB) + `web` |
| Last full-suite run | **1411 passed / 1 skipped / 13 xfailed / 10 xpassed / 0 failed** in 5m04s (2026-10-18, after WS-29b, WS-31b, WS-35–40) |

**What this session delivered** (all pushed): 10 commercial-hardening steps plus 3
follow-up fixes â€” see Â§3 for the doc to read per area.

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
  tests/test_regulatory_facts.py tests/test_lice_lineage_propagation.py \
  tests/test_ws23_backtest_honesty.py tests/test_public_claims.py \
  tests/test_decision_stale_data.py tests/test_ws22_data_claims.py \
  tests/test_margin_bridge.py -q
  # 476 passed + 1 skip (network), ~35s (after WS-29)

# the full suite (â‰ˆ4.5 min) â€” command runners time out at ~30s, so background it:
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
`pytest`); a Python traceback is swallowed by the pipeline â€” capture it with
`cmd /c "python script.py > out.txt 2>&1"` then read `out.txt`; `git push` writes
progress to stderr so a piped chain may report exit 1 even when the push succeeded â€”
always confirm with `git ls-remote origin refs/heads/master`. **On Windows under this
harness, pytest's `tmp_path` breaks** (trap 20): run it with `TMP`/`TEMP` pointed at a
writable workspace directory and a `sitecustomize.py` on `PYTHONPATH` that drops the
`0o700` mode from `os.mkdir`; otherwise every `tmp_path` fixture errors with
`PermissionError: [WinError 5]`.

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
| Margin bridge (price â†’ cost â†’ margin, levers) | `docs/MARGIN.md` | `core/market/margin_bridge.py`, `frontend/src/components/MarginBridge.tsx` |
| Roles to hire | `docs/roles/` | â€” |

## 4. Non-negotiables (AGENTS.md wins if anything here disagrees)

1. **Never fabricate data or accuracy.** A model fallback is `is_live: false`, always.
   No MAPE/coverage figure without a validated artifact.
2. **One entitlement definition** â€” `core/entitlements.py`. Never add a tier table
   (three had already drifted before this was fixed).
3. **Provenance on every data route**, or an exemption in
   `core/provenance_register.EXEMPT` **with a written reason**.
4. **Security invariants:** admin-only `/api/admin/*` + `/api/cache/*`; ownership
   checks against the **token** user id (never a body `user_id`); SSRF guard on
   outbound URLs at creation **and** dispatch; production refuses a weak JWT secret.
5. **Surgical diffs** + tests for every bugfix. Update `AGENTS.md`/`CHANGELOG.md` for
   structural changes.
6. **State gaps, never hide them.** Every check in this repo reports `unknown`/
   `degraded` rather than inventing a value â€” keep it that way, even when a dashboard
   would look nicer green.

## 5. Workstream backlog â€” pick these up in order

Each item is self-contained: goal â†’ files â†’ steps â†’ **acceptance criteria you can
test** â†’ traps.

**Where things stand (2026-10-18, after WS-29 and the WS-28a/30-35 round):**
- **Done:** WS-1, WS-2, WS-11, WS-19, WS-21, WS-14, WS-29 (the weekly margin bridge),
  WS-28a (the directional-write gate), WS-30 (ROI break-even), WS-31 (licensed FX +
  attribution, Yahoo removed), WS-32 (satellite honesty), WS-33 (bloom truth, Alembic
  021), WS-34 (bloom context) and WS-35 (reported company volumes), WS-22's
  stale-decision-card rule and its data-claim fixes, and both halves of WS-23. WS-21's
  entry lists its follow-ups.
- **Partly done:** WS-20 (left: one product name and the Desk/Operator price inversion,
  both owner decisions, plus the OpenAPI `info.description`) and WS-22 (the
  smolt-pipeline item is open; the company volume, brief bloom count and ROI defaults
  are done).
- **Waiting on the owner:** the WS-26 page-cut list, WS-27 layer 2, the WS-20
  decisions above, and the legal opinion that the rest of WS-28 waits on.
- **Next without an owner decision:** WS-29b's data step (obtain a realised feed figure;
  the mechanism ships), then WS-22's smolt pipeline, then WS-16, WS-24 and WS-25,
  in the order below. WS-31b is done (Yahoo removed from
  every data path); the only licence item left is negotiating NQSALMON/SISALMONI if a
  benchmark display is ever wanted.

### WS-32 · Satellite honesty — **DONE 2026-10-18**
**Why:** without CDSE credentials the engine fabricated every per-farm reading with
`np.random.default_rng(hash(locality_no))`, and with credentials a farm whose query
failed silently fell back to the same simulation; `is_live` was `bool(credentials)`.
The page turned those values into an "Action required" KPI. It was the only invented
measurement on the platform.
**Shipped:** `core/market/satellite_engine.py` (simulator deleted; no scene → no
reading; `n_readings_verified` / `n_readings_unverified` / `scene_dates` /
`missing_reason`; `is_live` from verified scenes; NDVI anomaly relabelled
`surface_scum_or_vegetation`; catalogue drops HAB-confirmation and cage-census and marks
the rest `validated: false`), provenance on all four `/api/satellite/*` routes, page
states "NO VERIFIED SCENE" / dated scenes, and the "what this shows / cannot show"
panel. 8 tests (`tests/test_satellite_honesty.py`).
**Acceptance met:** unconfigured scan → `n_readings: 0`, `is_live: false`, a named
reason, zero anomalies; configured with every query failing → same, with
`n_readings_unverified` = farms; one mocked scene → `is_live: true`, its date in
`scene_dates`, anomaly type `surface_scum_or_vegetation`.
**Council decision:** the proposed finer-grained 300 m per-farm OLCI layer was
**rejected for this session and not queued** — a cage is sub-pixel at 300 m, 52–90 % of
ocean-colour pixels are gap-filled (more at high latitude), and the 2019 bloom was
concentrated around 12 m, below what ocean colour sees. Building it would assert
farm-level certainty the science rejects.

### WS-33 · Bloom truth (freshness, trend, delivery) — **DONE 2026-10-18**
**Why:** `/bloom` crashed for every user on the response envelope; 196-day-old
chlorophyll wore a live badge with request-time freshness; `chl_a_trend` was computed
after the new row was committed, so it compared the value with itself (0.0 on all
123 045 rows); 842 alerts said `sent` with no channel configured; the bio-risk disease
count called a non-existent method inside `except: pass`; the brief counted every row
ever stored; and the stored `dataset_id` (Atl 1 km L3) described a different product
from the one the client fetches (global 4 km L4).
**Shipped:** one `_bloom_freshness()` + `_bloom_provenance()` pair (live only within
7 days, else degraded naming the date and age), `dataset_note` on a mixed store, the
alert log's provenance declaring itself a delivery record, the real Mattilsynet API for
the disease count with `status: unavailable` instead of a silent zero, the trend
computed against the previous **distinct** date with `None` when absent, notification
statuses `not_configured` / `sent`+`delivered_at` / `failed` / `dashboard` and a
"CHLOROPHYLL WATCH … not a toxicity measurement" message, the brief counting distinct
localities in the last week with the data age, the page unwrapping `.items`, showing the
served freshness, "n/a" for an unknown trend and the limits panel, and **Alembic 021**
(`delivered_at`; pre-fix alerts `legacy_unknown`; self-compared trends `NULL`; the
downgrade keeps both corrections). 17 tests (`tests/test_bloom_honesty.py`) plus a 021
migration test.
**Acceptance met:** a 196-day-old store returns 200 with `is_live: false` and the age in
the reason; a fresh one is live; no stored 0.0 trend remains after 021; a missing prior
observation yields `chl_a_trend: null` and no trend bonus; an unconfigured channel
records `not_configured` and never `sent`; the brief's count is distinct localities
within the week.
**Open:** the ingest still needs CMEMS credentials and an agents run (WS-16); until then
the page honestly says the data is stale.

### WS-34 · Bloom context (dated facts, no forecast) — **DONE 2026-10-18**
**Why:** the chlorophyll band alone cannot tell a farmer whether the region has killed
fish before, what the official advisory says, or what the instrument cannot see.
**Shipped:** `core/bloom/context.py` and `GET /api/bloom/context` — the IMR Algestatus
link with `checked_at` and an explicit "no API" note, three documented mortality events
with source URLs (2019 *C. leadbeateri* 8 M fish / NOK 2.4 bn potential sales value;
2025 *C. leadbeateri* + *Phaeocystis* >2 M fish / ≥NOK 300 M; March 2026
*Pseudochattonella* PO1 ~1.7 M fish), and five stated limits. The payload is degraded
by design (a dated link, not a feed) and is rendered on `/bloom` beside the band.
**Do not claim:** species-level prediction, a mortality probability, "72-hour warning",
an AUC for HAB risk, that gap-filled chlorophyll shows a bloom, or that a bloom will kill
fish. Sources and prices: [`docs/DATA_SOURCES_COST.md`](DATA_SOURCES_COST.md).

### WS-28a · No agent writes directional rows on listed shares — **DONE 2026-10-18**
**Why:** WS-20 took the surfaces down but four agents still wrote the rows (signal
generator, market hedger, prediction agent, bloom agent); they run only with the agents
service, so the calls would reappear the moment it started.
**Shipped:** `core/legal/equity_signals.DIRECTIONAL_WRITES_ENABLED = False` +
`may_persist_directional(instrument=...)`; each writer checks it and logs or audits the
skip; non-equity instruments are unaffected. 14 tests
(`tests/test_directional_writes_gate.py`).
**Still open (WS-28):** the remaining equity-direction *surfaces* (pairs, sentiment,
event impact, paper orders) and the legal opinion. This item only stops new writes.

### WS-30 · ROI calculator tells the truth — **DONE 2026-10-18**
**Why:** defaults produced 228x / 491x / 1 693x multiples from unproven uplifts; a
finance buyer reads that as a red flag, and it made the demo worse, not better.
**Shipped:** claim-like inputs default to **zero**; the processor's hard-coded 0.5 is
now `share_of_volume_affected`; each ICP reports `status`, `paid_back` and a
`break_even` (`input`, `value`, `feasible`, `benefit_needed_nok`) — the producer needs
1.31 % of treatments avoided for Operator to pay for itself at 18 treatments a year.
17 tests (`tests/test_gtm_roi.py`).

### WS-35 · Company volumes are reported facts — **DONE 2026-10-18**
**Why:** `top50_engine` computed annual production as `n_localities * 800` and shipped it
as a volume. Mowi read **113 600 t** against ~**332 000 t** harvested in Norway in 2025 —
a 3× understatement of the largest producer, on the desk an analyst opens first.
**Shipped:** `core/market/company_facts.py` — one row per reporting entity with year,
**scope** (Norway vs group; a Norway figure must never be read as a group figure), the
figure and a source URL. `production_volume_tonnes` is `None` when no fact is registered,
paired with a `volume_basis` block (`basis: reported | sub_entity | unknown`) that says
why; sub-entities do not repeat the group figure; unknown volumes sort last and serialise
as `null`, never `0` (which reads as a measurement). 11 tests
(`tests/test_company_volumes.py`).
**Acceptance met:** Mowi ASA reports 332 000 t / Norway / 2025 with a source URL; an
unregistered company reports `null` and names the retired multiplier as the reason it is
not estimated; `MOWI FEED AS` reports `sub_entity`, not the group harvest; the string
`* 800` no longer appears in any compute line of the engine.
**Open:** add rows for SalMar, Lerøy, Grieg, Bakkafrost and Måsøval as their 2025 figures
are verified (the module takes one row each; do not estimate between them).

### WS-31 · Licensed FX + attribution — **DONE 2026-10-18**
**Why:** Yahoo's API terms forbid deriving income from its data, and the platform
priced Norwegian costs from its USD/NOK. FRED's terms require a notice the site did not
show.
**Shipped:** `core/market/fx_rates.py` (Norges Bank official daily rates, observation
date attached, recorded fallback), wired into `feed_cost_engine` (and therefore the
margin bridge) and `competitiveness_engine`; `usd_nok_is_fallback` / reason / observation
date on the payload; the attribution footer gains Norges Bank, Mattilsynet and the FRED
notice and drops the Yahoo claim.
**WS-31b (same day) — Yahoo removed from every data path.** `rate_to_usd()` in the same
module resolves USD, EUR, GBP, DKK, SEK, ISK, CAD and PLN from Norges Bank (the per-100
convention for DKK/SEK/ISK handled once) through the official USD/NOK rate, and flags the
one currency with no licensed daily source (CLP, documented constant). Wired into
`competitiveness_engine` (every currency, with per-currency observation dates and
reasons), `euronext_futures` (EUR/NOK), `macro_intelligence` (NOK/EUR from Norges Bank,
USD/CNY from FRED `DEXCHUS`) and the feed engine (Yahoo commodity gap fill deleted).
`salmon_price.get_latest_prices()` now returns **only** the SSB spot: the Oslo equity
quotes are gone, and so is the fallback that *derived* share prices by multiplying the
salmon spot by fixed multiples — a fabricated market price; the pairs agent skips
explicitly instead of trading on it, and `/api/market/equity-prices` reports
`equity_quotes: "unavailable"` with a degraded provenance.
`tests/test_licensed_sources.py` (11) plus the WS-22 FX tests.
**Still open:** the two salmon benchmark indices (NQSALMON, SISALMONI) publish no price
or redistribution right — a negotiated agreement is required before either can appear in
a paid surface, and the synthetic forward curve must never be presented as a real one.

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

### WS-29 Â· The weekly margin bridge â€” **DONE 2026-10-18**
**Why:** the platform held both inputs that decide a producer's week â€” the live SSB
export price and the live FRED feed basket â€” and never turned them into money with the
assumptions named. `/feed-cost` showed a margin bar plus three rows whose units
disagreed (feed ingredient cost per kg of *feed* beside the price per kg of *salmon*),
no provenance, no change, no break-even. A buyer could not tell a model from a
measurement, or July's feed price from this month's.
**Shipped:** `core/market/margin_bridge.py` (method `1.0.0`, singleton
`margin_bridge`): price leg âˆ’ four grouped cost legs (feed, smolt+slaughter,
labour+other operating+insurance, depreciation+finance) per kg round weight; the
week-on-week price move and month-on-month feed move; break-even with the feed-leg
reduction and the FCR that would close it; five levers with formulas; an assumption
register; a `reconciliation` block against the feed engine's own total; a `validation`
block against the last audited realised feed cost. `GET /api/margin/bridge` and
`GET /api/margin/bridge/{locality_no}` (the farm endpoint adds the week's Â§ 8 limit and
a lice position that is `measured` only from verified, current rows â€” otherwise
`unknown` with the lineage reason). `feed_cost_engine.feed_index_change()` (weighted
month-on-month basket move; refuses a zero on thin data) and FRED observation dates on
`IngredientPrice`/`FeedCostSnapshot`/`get_latest()`. `decision_engine` now values lost
biomass at the live SSB spot instead of the `95.0` constant (`fish_value_nok_per_kg`,
`fish_value_source`, `fish_value_is_live`; a fallback degrades the card and a stale SSB
week is named). Frontend `MarginBridgePanel` on `/feed-cost` and on `/farmer-daily`
(per farm), replacing the old Margin Analysis card; ingredient rows show the
observation month; the page header and the FX KPI render the served provenance instead
of a hardcoded "live". 45 tests (`tests/test_margin_bridge.py`), `docs/MARGIN.md`.
**Review round closed (same day):** the change total now subtracts the feed *cost*
delta from the price delta (it added them), the margin leg's status follows the
headline quality, reconciliation reports `ok: null`/`applicable: false` for a
caller-supplied feed leg, validation names `compared: model|caller_inputs`, a constant
or stale-week valuation degrades the decision card, `PRICE_MAX_WEEKS_BEHIND` (one
definition in `ssb_price_client`) degrades both consumers past two weeks,
`usd_nok_is_fallback` is recorded and degrades the basket, the feed reason says
"oldest dated ingredient", and the frontend form is placeholder-seeded so Apply cannot
flip `modelled` to `measured` untouched.
**Found on the way:** the newest FRED "global price" point on this box is **2026-07**
(109 days old), while `/feed-cost` stamped the *fetch* time as the price date â€” a
three-month-old observation presented as live on the platform's flagship cost surface.
The bridge treats that as degraded and names the month (trap 21).
**Acceptance met:** the grouped legs re-add to the engine total (difference 0.01, `ok:
true`); the same payload reports `quality: modelled` by default and `measured` only
when both the price and the feed numbers are caller-supplied; a stale/undated/defaulted
basket degrades the leg with the month named; no volume means no NOK totals; live
payload on 2026-10-18 reads price 72.55 (W41), feed âˆ’29.39 (FRED 2026-07), cost 74.03,
margin âˆ’1.48, break-even 74.03, 5.0 % feed-cut or FCR 1.23 to close it.
**WS-29b — mechanism shipped, data still open.** The feed leg (29.39 NOK/kg salmon,
+14.5 % over the 2024 audited 25.67) looks high against market evidence — BioMar's
salmon-feed price fell below NOK 15/kg in Q1 2026 (iLaks, 2026-05-08) and realised feed
cost was ~25 NOK/kg in 2025 with −3.5 to −4.0 expected in 2026 (Fearnley via iLaks,
2025-08-18). If the 2026 realised figure is ~21.5, the model overstates the feed leg by
about a third. **The deltas, break-even relationship and levers are differential and
survive a level error; the level does not.**
**Shipped (2026-10-18):** `core/market/feed_anchor.py` reads an operator-registered
realised figure from `artifacts/feed_realised_prices.json` (template
`feed_realised_prices.example.json`; NOK per kg of *harvested salmon*, 10–60, year 2008+
and not in the future, stale after two years) and the bridge prefers it to the survey,
reporting `anchor_source`, `anchor_scope`, `anchor_is_registered` and `anchor_stale`. A
malformed file is ignored with a logged reason; with no anchor the note tells the
operator how to register one. `tests/test_feed_anchor.py` (10). Checked 2026-10-18: the
official 2025/2026 survey figures are not published, so none were added.
**Still open:** obtain a defensible realised figure (a design partner's aggregate, or a
licensed price series), recalibrate `INGREDIENT_TO_DELIVERED` (currently a 2024-derived
1.86) and/or replace the fixed 2.00 USD/kg "other" line, add the resulting artifact to
the accuracy registry, then bump `MARGIN_METHOD_VERSION`. Until then the level stays
`modelled`, and the validation block keeps printing the gap.
**Also open:** no premium gate was added for `/api/margin/*` â€” the paywall ladder is the
owner's WS-20/26 decision; the bridge is ungated like the other cost-desk routes.

#
#
#
 
W
S
-
3
9
/
4
0
 
·
 
D
o
c
u
m
e
n
t
s
 
s
o
l
d
 
a
s
 
r
u
n
s
,
 
n
u
m
b
e
r
s
 
c
h
e
c
k
e
d
 
—
 
*
*
D
O
N
E
 
2
0
2
6
-
1
0
-
1
8
*
*


*
*
W
h
y
:
*
*
 
c
h
a
t
 
c
a
n
n
o
t
 
p
a
y
 
f
o
r
 
i
t
s
e
l
f
 
(
U
S
D
 
0
.
0
0
8
2
 
a
 
q
u
e
s
t
i
o
n
)
 
a
n
d
 
a
 
t
o
k
e
n
 
m
a
r
k
u
p
 
i
s
 
a
 
m
a
r
g
i
n


g
r
a
b
 
t
h
a
t
 
m
o
d
e
l
-
p
r
i
c
e
 
d
e
f
l
a
t
i
o
n
 
e
x
p
o
s
e
s
 
w
i
t
h
i
n
 
a
 
y
e
a
r
;
 
m
e
a
n
w
h
i
l
e
 
t
h
e
 
r
e
s
e
a
r
c
h
 
s
h
o
w
s
 
c
i
t
a
t
i
o
n
s


d
o
 
n
o
t
 
e
n
f
o
r
c
e
 
f
a
i
t
h
f
u
l
n
e
s
s
,
 
s
o
 
t
h
e
 
t
h
i
n
g
 
w
o
r
t
h
 
s
e
l
l
i
n
g
 
i
s
 
a
 
*
c
h
e
c
k
e
d
 
d
o
c
u
m
e
n
t
*
.


*
*
S
h
i
p
p
e
d
:
*
*


-
 
`
c
o
r
e
/
b
i
l
l
i
n
g
/
c
r
e
d
i
t
s
_
c
a
t
a
l
o
g
.
p
y
`
 
—
 
t
h
r
e
e
 
p
a
c
k
s
 
o
f
 
r
u
n
s
 
(
N
O
K
 
1
,
4
9
0
/
1
0
,
 
3
,
9
0
0
/
3
0
,
 
1
1
,
9
0
0
/
1
0
0
)
,


 
 
m
a
r
g
i
n
 
s
t
a
t
e
d
 
a
g
a
i
n
s
t
 
t
h
e
 
m
e
a
s
u
r
e
d
 
m
o
d
e
l
 
c
o
s
t
.


-
 
`
c
o
r
e
/
l
l
m
/
c
r
e
d
i
t
s
.
p
y
`
 
+
 
A
l
e
m
b
i
c
 
*
*
0
2
3
*
*
 
(
`
c
r
e
d
i
t
_
l
e
d
g
e
r
`
)
 
—
 
a
p
p
e
n
d
-
o
n
l
y
,
 
`
g
r
a
n
t
`
/
`
s
p
e
n
d
`


 
 
w
i
t
h
 
`
I
n
s
u
f
f
i
c
i
e
n
t
C
r
e
d
i
t
s
`
,
 
a
n
 
u
n
r
e
a
d
a
b
l
e
 
l
e
d
g
e
r
 
r
e
p
o
r
t
e
d
 
a
s
 
u
n
k
n
o
w
n
 
(
n
e
v
e
r
 
f
r
e
e
)
.


-
 
`
c
o
r
e
/
l
l
m
/
w
o
r
k
b
e
n
c
h
.
p
y
`
 
—
 
t
h
r
e
e
 
g
r
o
u
n
d
e
d
 
d
o
c
u
m
e
n
t
s
;
 
`
m
o
d
e
:
 
"
d
i
g
e
s
t
"
`
 
w
h
e
n
 
n
o
 
m
o
d
e
l
 
i
s


 
 
r
e
a
c
h
a
b
l
e
,
 
a
n
d
 
t
h
a
t
 
c
o
s
t
s
 
n
o
 
c
r
e
d
i
t
.


-
 
`
c
o
r
e
/
l
l
m
/
c
l
a
i
m
_
c
h
e
c
k
.
p
y
`
 
—
 
e
v
e
r
y
 
d
i
g
i
t
 
i
n
 
a
n
 
a
n
s
w
e
r
 
m
a
t
c
h
e
d
 
t
o
 
t
h
e
 
f
a
c
t
s
;
 
u
n
m
a
t
c
h
e
d
 
o
n
e
s


 
 
n
a
m
e
d
,
 
b
a
d
g
e
d
 
a
n
d
 
c
a
v
e
a
t
e
d
.
 
W
i
r
e
d
 
i
n
t
o
 
c
h
a
t
 
a
n
d
 
w
o
r
k
b
e
n
c
h
.


-
 
`
c
o
r
e
/
r
o
u
t
e
r
s
/
w
o
r
k
b
e
n
c
h
_
r
o
u
t
e
s
.
p
y
`
 
—
 
c
a
t
a
l
o
g
,
 
r
u
n
,
 
c
r
e
d
i
t
s
 
s
t
a
t
u
s
,
 
c
r
e
d
i
t
 
c
h
e
c
k
o
u
t
.


-
 
`
d
o
c
s
/
A
I
_
P
R
I
C
I
N
G
.
m
d
`
 
—
 
t
h
e
 
p
r
i
c
i
n
g
 
r
e
s
e
a
r
c
h
 
a
n
d
 
t
h
e
 
d
e
c
i
s
i
o
n
s
.


*
*
M
e
a
s
u
r
e
d
:
*
*
 
d
o
c
u
m
e
n
t
 
≈
 
U
S
D
 
0
.
3
5
 
m
o
d
e
l
 
c
o
s
t
 
v
s
 
N
O
K
 
1
1
9
–
1
4
9
 
p
r
i
c
e
;
 
c
h
a
t
 
a
l
l
o
w
a
n
c
e
 
c
o
s
t
s


N
O
K
 
7
–
7
4
/
u
s
e
r
/
m
o
n
t
h
 
b
y
 
p
l
a
n
.


*
*
O
p
e
n
:
*
*
 
t
h
e
 
1
5
0
-
q
u
e
s
t
i
o
n
 
g
o
l
d
e
n
 
s
e
t
 
w
i
t
h
 
a
 
z
e
r
o
 
s
i
l
e
n
t
-
w
r
o
n
g
-
n
u
m
b
e
r
 
g
a
t
e
;
 
p
r
o
m
p
t
 
c
a
c
h
i
n
g
 
f
o
r


t
h
e
 
f
a
c
t
 
b
l
o
c
k
;
 
o
v
e
r
a
g
e
 
b
i
l
l
i
n
g
 
a
n
d
 
a
n
n
u
a
l
 
a
n
s
w
e
r
 
p
a
c
k
s
 
(
n
e
e
d
 
a
 
s
t
o
r
e
d
 
p
a
y
m
e
n
t
 
m
e
t
h
o
d
)
.




### WS-38 · Grounded, metered chat — **DONE 2026-10-18**
**Why:** chat was the only surface outside the honesty layer. `core/api.py` built its prompt
from a national lice average over **every** row (demo seeds included), a latest week with no
age, and a "traffic light: green < 0.2" sentence that is not how the Norwegian system works.
Nothing counted tokens per user against a USD 100/month budget, and the feature was in the
Desk plan (NOK 2,990) but not the Operator plan (NOK 4,900).
**Shipped:**
- `core/llm/grounding.py` — seven facts (verified-only lice + age, § 8 limit for the week,
  SSB price, margin bridge with feed month and quality, chlorophyll with scene date,
  traffic-light decision, dated US tariff), each with `as_of`/`source`/provenance, built
  concurrently, one engine's failure degrading only its own fact. The prompt forbids numbers
  outside the block and requires stale facts to be stated with their age.
- `core/llm/chat_service.py` — one answer path with `mode` ∈ {grounded, grounded_fallback,
  refusal, unavailable}; the fallback assembles the verified numbers deterministically so an
  outage never yields nothing, and says a model did not write it.
- `core/llm/usage.py` + Alembic **022** (`chat_usage`) — per-user, per-month meter of
  questions and tokens; unreadable meter is reported as unknown, never assumed.
- `core/routers/chat_routes.py` — `POST /api/chat`, `GET /api/chat/usage`,
  `POST /api/chat/save-alert`; allowance in `entitlements.Plan.chat_questions_per_month`
  (free 0, Operator 100, Desk 300, Enterprise 1000, Intelligence unlimited); chat opened to
  Operator in both the route allowlist and the page list.
- `/chat` rebuilt: allowance meter with reset date and model cost, per-answer provenance
  chips, "watch this", a locked state that names the plan and the upgrade.
**Measured:** one grounded answer = 1 070 in + 188 out tokens = **USD 0.0082**; the whole
100-question Operator allowance costs ~USD 0.8 of model spend.
**Open:** credit packs and a deep-analysis run (WS-39); an evaluation set for answer
accuracy (WS-40); anonymous trial questions (a marketing decision, deliberately not taken —
chat is a paid surface from Operator up).

### WS-37 · US duty is assessed on the customs value — **DONE 2026-10-18**
**Why:** `competitiveness_engine` computed `tariff_cost = production_cost * rate`. US duty
is assessed on the **transaction value** of the imported good — the price the importer
pays — so the engine understated the duty by the exporter's margin, and a trade-compliance
reader spots that immediately.
**Shipped:** the rate is charged to the best available declared value: the live SSB export
price for Norway (converted through Norges Bank), production cost elsewhere with a note
that the true duty is higher by the exporter's margin. Every row carries `tariff_base`,
`export_price_usd`, `tariff_at_export_price_usd` and a `duty_base_note` that states the
direction (on 2026-10-18 the export price is *below* the modelled cost, so the cost-base
figure was the higher of the two — the note says so rather than assuming); the snapshot
carries `tariff_basis`; `/competitiveness` marks export-price rows with `*` and prints the
basis under the table. `tests/test_tariff_basis.py` (6).
**Open:** a live export price for the other origins (Chile, Scotland, Faroe, Iceland,
Canada) would replace the cost-base proxy; until then those rows say so.

### WS-36 · The smolt pipeline is checked before it is used — **DONE 2026-10-18**
**Why:** `smolt_model` projects harvest from smolt releases x survival x yield, and the
forecast route served that projection with the label "Smolt model + Fiskeridirektoratet"
behind a live badge. On 2026-10-18 its 12-month total is **789 987 t against the module's
own 1.7 M t national production reference (0.46x)**, while SSB's weekly export volumes
imply about 120 000 t/month nationally — a reader could take a model output as supply.
**Shipped:** `SmoltModel.validation()` publishes `model_12m_tonnes`,
`reference_annual_tonnes`, `ratio_to_reference`, `deviation_pct`, `within_tolerance` and a
`measurement` string ("model projection ..., not reported supply");
`/api/supply/smolt-forecast` carries the block and **degrades** with the reason when the
ratio is outside +-30 %, instead of serving a live badge; `get_summary()` carries it too.
8 tests (`tests/test_smolt_validation.py`), including a calibrated branch so the check is
about the gap rather than a hard-coded verdict.
**Open:** calibrate the release/yield constants against Fiskeridirektoratet's reported
harvest (both the 1.7 M t reference and the 400 M smolt assumption are module constants);
until then the level stays flagged.

### WS-1 Â· Make the lice lineage verifiable â€” **DONE 2026-10-16**
**Shipped:** `core/source_lineage.py` â€” the one vocabulary for `lice_records.source`
(`barentswatch` / `demo_seed` / `unverified`; the `fiskeridir` marker proposed here
earlier was replaced because the only writer is the BarentsWatch Fishhealth API v2
client, so it is the system of record). Alembic **019**: `source VARCHAR(32) NOT NULL
DEFAULT 'unverified'`, NULL â†’ `unverified`, relabels **only** the demo key
(locality 10001â€“10022 Ã— the seed year 2025) as `demo_seed`, never a real source,
repairs a conftest-reconciled nullable column, batch-mode downgrade.
`agents/data_ingest.py` writes `barentswatch` on **both** upsert branches;
`core/demo_seed.py` writes `demo_seed`; `agents/historical_backfill.py` skips a week
only when its rows are **verified**. `lice_quota_tracker` publishes a row-level
`lineage` (same predicates as its data query, per PA and merged nationally, inside
the cached payloads, mirrored to `last_lineage`) and its provenance is degraded with
the reason when the lineage does not support live â€” including the single-locality
path. `indices._lice_lineage_note(lineage)` is row-level. `/api/data-freshness`
reports `verified_rows` / `unverified_rows` / `no_verified_rows`; the verifier adds
the **critical** `lice_source_column` check and the `freshness_no_verified_rows`
warn verdict. 20 tests (`tests/test_production_truth.py::TestLiceLineage`,
`tests/test_migrations.py`, `tests/test_indices.py`, `tests/test_market_engines.py`).
**Acceptance met:** `ix._lice_lineage_note()` is None after a compute whose window
is all `barentswatch`, every PA fetched and fresh (proved with stubbed lineage); on
this box it names "6997/6997 lice rows used carry no verified source â€¦ newest lice observation is 2026-W15, 27 weeks old â€¦ newest lice row was fetched 4604 h ago" with every PA listed; AI-LPI is live/degraded by that rule; the freshness entry shows
synthetic 1,040 / verified 0 / unverified 185,099, `no_verified_rows: true`.
**Deliberately not done:** no pre-WS-1 row was relabelled as real â€” audit logs record
only per-tick insert counts, which is not row-level proof. The tracker's year-wide
window (WS-15) and the dead ingest (WS-16) keep AI-LPI degraded here until a real
re-ingest; on a fresh production DB every row arrives as `barentswatch`.

### WS-2 Â· Publish the weekly indices on a schedule â€” **DONE 2026-10-16**
**Shipped:** `agents/index_publisher_agent.py` (`index_publisher`, the 13th agent,
started by `python main.py --agents-only`): hourly check; builds the digest and
stores one observation per ISO week when `index_publication.status()` says the week
is missing **and** `readiness()` approves (never a null value; only a live digest
within the first 72 h of the week; a disclosed degraded one after); never
double-publishes (a lost race is a duplicate); a failed or incomplete publication is
an error log, an `index_publication` audit row, `last_failure` in `health()` and a
raised tick. `status()` reads the store: latest week per index with value and
provenance, weeks behind, **interval in ISO weeks** (wall-clock gaps are
informational â€” they drift with the hourly tick), `degraded_current`,
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

### WS-3 Â· Ship model artifacts through the release path
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

### WS-4 Â· Timescale hypertables (deliberately manual today)
**Why:** `docker/init-timescale.sql` creates the extension only; conversion was left
manual because a wrong chunk interval silently degrades plans.
**Files:** `docker/init-timescale.sql`, a gated migration, `core/production_truth.py`.
**Steps:** convert only tables with a real timestamp column
(`lice_records.fetched_at`, `chlorophyll_readings.fetched_at`,
`index_observations.as_of`) with `migrate_data => true` in a guarded DO block; add
retention policies.
**Acceptance:** the verifier reports `hypertables >= 3` on PG, with a documented
rollback. **Traps:** `ssb_weekly_prices` has **no** timestamp column â€” do not convert.

### WS-5 Â· Durable quota ledger + metered billing
**Why:** counters are in-process per UTC day per worker, so a paying customer's
allowance is per-pod and overage invoicing is impossible.
**Files:** `core/tier_quota.py`, `core/models.py` (usage table),
`core/billing/stripe_catalog.py` (metered prices), `core/routers/entitlements_routes.py`.
**Steps:** persist (user, plan, day, count) with an upsert, read/write via the DB,
keep the env kill-switches, surface usage in `/api/entitlements/me`.
**Acceptance:** two simulated workers share one counter â€” a test proves the 429 fires
once across both.
**Traps:** keep anonymous traffic ungated; never count `/api/auth/*`, `/api/health`,
`/api/billing/*`.

### WS-6 Â· SSO / SAML / OIDC (enterprise blocker)
**Why:** enterprise deals stall on identity. `docs/roles/enterprise-security-engineer.md`
holds the four-part definition of done.
**Files:** `core/auth.py`, `core/routers/auth_routes.py`, `core/entitlements.py`
(group â†’ plan mapping), `core/models.py`.
**Steps:** OIDC/SAML login, SCIM-style provisioning, groupâ†’canonical-plan mapping
**without a new tier table**, central revocation, audit-log entries.
**Acceptance:** a provisioned user lands on the right plan via the existing
entitlement path, revocation removes access, and every change is in the audit log.
**Traps:** an IdP attribute must never grant `role=admin`; map only to
`core/entitlements.PLANS` keys.

### WS-7 Â· Per-tenant isolation + aggregation threshold
**Why:** producer-contributed data must never be de-anonymisable in a published index;
the licence register already records the n â‰¥ 5 obligation.
**Files:** `core/models.py`, `core/market/indices.py` (enforce, not just document),
`core/legal/data_licenses.py`, `core/routers/partner_routes.py`.
**Steps:** enforce the threshold in the compute path, scope queries per tenant, and
test that a 4-producer aggregate refuses.
**Acceptance:** 4 contributors â†’ refusal carrying the reason; 5 â†’ success.
**Traps:** the refusal message must not name the contributing partners either.

### WS-8 Â· More accuracy artifacts (and keep the registry honest)
**Why:** one artifact exists (`seasonal_naive_weekly_prices`, MAPE 13.42%, coverage
92.1%, n=208). A model artifact can be published only where weights/torch are
available; supply and lice surfaces have none yet.
**Files:** `scripts/publish_accuracy.py` (extend, do not fork),
`core/ml/accuracy_registry.py`, `core/market/price_ml.py` (`BACKTEST_ARTIFACT`
contract), `docs/ACCURACY.md`.
**Steps:** one artifact per surface you can genuinely measure; always set
`fallback_used` truthfully; omit `coverage_pct` if unmeasured.
**Acceptance:** `/api/accuracy` lists each new artifact; no surface displays a number
without one. **Traps:** the publisher refuses demo-only data â€” keep that, never add a
`--force` bypass.

### WS-9 Â· Freshness alerting + a scheduler assertion
**Why:** nothing pages when a source goes `dead`, and nothing proves the weekly
publication ran.
**Files:** `core/market/freshness_monitor.py`, an agent, `core/production_truth.py`.
**Steps:** alert on `critical_unknown` / `dead` / `synthetic_only` /
`no_verified_rows` (WS-1) and on `index_publication.status()["missing"]` (WS-2 â€” the
assertion exists; only the paging is missing); expose alert state on
`/api/data-freshness`; fold the lice observation-week age into the monitor (it reads
`fetched_at`, a write time).
**Acceptance:** a test simulating a missing current-week row fails with a named reason.

### WS-10 Â· Wire runtime provenance measurement into CI
**Why:** the ratchet proves a *decision* was recorded, not that provenance is actually
returned; 204 routes are baselined and the real residue is only known by probing.
**Files:** `scripts/probe_liveness.py` (payload-shape classification exists),
`docs/REPORT_LIVENESS.md`, CI.
**Steps:** probe a booted app in CI, publish `no_provenance` counts into the report,
fail when the count increases.
**Acceptance:** a deliberately provenance-free route makes CI fail naming it.

### WS-11 Â· Remove the last hardcoded tier table (frontend) â€” **DONE 2026-10-17 (with WS-20)**
**Why:** `frontend/src/app/billing/page.tsx` still carries its own `TIER_DETAILS`
feature/price lists while `/pricing` is catalog-driven â€” the same drift the backend
SSOT killed.
**Files:** `frontend/src/app/billing/page.tsx`, `frontend/src/lib/api.ts`
(`billingCatalog` exists), `frontend/src/types/api.ts`.
**Steps:** render from `api.billingCatalog()`, delete `TIER_DETAILS`, keep icons as a
presentation map keyed by plan key.
**Acceptance:** `grep -r TIER_DETAILS frontend/src` is empty; `tsc --noEmit` = 0;
changing a price in `core/entitlements.py` changes the page with no frontend edit.

### WS-12 Â· Enforce the data-licence register at runtime
**Why:** the register *records* that `fish_pool_futures` may not be publicly displayed
and Copernicus raw data may not be resold â€” but nothing enforces it. A register that
only documents is a liability.
**Files:** `core/legal/data_licenses.py` (`check_use` exists),
`core/routers/market_routes.py` + routes exposing licensed sources,
`core/provenance_register.py`.
**Steps:** gate affected routes on `check_use(source, "public_display" |
"resale_as_data_product")`; refuse with a structured payload naming the reason and the
register link (mirroring the entitlement upgrade payload).
**Acceptance:** a public futures display without a cleared licence returns a structured
refusal; with `classification_status="cleared"` it passes.
**Traps:** refuse and say why â€” never silently substitute a different number.

### WS-13 Â· Human-gated items (a module cannot close these)
Recorded so nobody pretends they are done: legal sign-off per `classification_status`
(fish-pool display licence, NLOD attribution wording, producer aggregation threshold),
the performance-fee decision, DPA completion + sub-processor register, penetration
test, SOC 2 Type I. Owners/conditions: `docs/ADVICE_BOUNDARY.md` Â§5â€“6,
`docs/roles/enterprise-security-engineer.md`.

### WS-14 Â· Propagate the lice lineage to every lice consumer
**Why:** WS-1 verified one index. 14+ consumers still stamp
`DataProvenance.live(... BarentsWatch ...)` on lice-derived payloads with no lineage
input â€” one verified index next to a dozen unverified live labels on the same table.
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
`/api/lice/summary` already degrades on staleness â€” merge, do not double-report.
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
**Shipped 2026-10-17 (partial â€” lice lineage propagation complete):** every
`lice_records` consumer in the original file list now derives provenance from the
rows it actually used. `core/source_lineage.py` gained the shared entry points
`summarise_rows` (row dicts â†’ lineage), `lineage_for(session, where)` (per-farm /
per-PA), `latest_week_lineage()` (roll-ups) and `provenance_for(lineage, label,
confidence)` (â†’ `DataProvenance.to_dict()`, degraded with the lineage note when the
rows do not support a live claim). Wired: `decision_engine`, `lice_routes`,
`supply_routes`, `analytics_routes`, `morning_brief`, `anomaly_engine`,
`biomass_predictor`, `bloom_routes`, `notification_routes`, `alerts_routes`,
`ml_routes`, `schemas`; then `asc_compliance`, `regulatory_reporter`,
`global_supply`, `welfare_scorer` (+ `/api/welfare/*`), `supply_demand_engine`
(+ `/api/supply/demand-balance`), all four `/api/treatment/*` endpoints,
`/api/esg/{scores,summary,company/*}` and `/api/leaders/*`. On this box (all
`lice_records` rows `demo_seed`/`unverified`, newest week 2026-W15) every one of
those routes now reports `is_live: false` with the lineage note in
`fallback_reason` and `freshness` = the ISO week's Monday â€” verified with a live
`TestClient` sweep, not by inspection. Two bugs surfaced and were fixed on the way:
the four `/api/treatment/*` endpoints called the `async` engine methods **without
`await`** (every call raised `'coroutine' object is not iterable` â†’ 500), and
`/api/regulatory/traffic-light/current` stamped request-time freshness on a
decision made on a fixed date (now `observed_at=decided_on`, undated â†’ degraded).
Three further laundering paths were closed in self-review: `/api/gnn/predict`
merged the model's `fallback_reason` with the lineage note instead of replacing it;
`/api/compliance/asc/readiness-summary` and `/api/welfare/pa/{pa}` now
`merge_lineages()` each farm's own lineage (a failed farm degrades the roll-up)
rather than borrowing `latest_week_lineage()`; and `/api/esg/scores` derives each
row's provenance from that row's lineage.
`tests/test_lice_lineage_propagation.py` (23 tests) pins the contract, the
observation-time freshness rule and one test per wired consumer;
`scripts/probe_lice_lineage.py` re-runs the live sweep. `docs/openapi.frozen.json`
was re-frozen (three response schemas gained the optional `lineage` field).
Gates 2026-10-17: `pytest tests/ -q` 1178 passed / 1 skipped / 13 xfailed /
10 xpassed (254.78s), `ruff check` clean on `core scripts tests`,
`scripts/provenance_ratchet.py` 204 baselined + 0 unregistered,
`scripts/verify_production_truth.py` 0 failures (4 known warnings),
`scripts/smoke_security.py` all checks passed, and `scripts/probe_lice_lineage.py`
printed 9/9 routes with `is_live: false` and a lineage reason.
**Still open in this item:** (a) the WS-16 clause â€” "a lice week below the
completeness threshold is never live" â€” cannot land until WS-16 defines the
threshold; do not invent one; (b) `is_live` from observation age on the remaining
non-lice visible routes (country snapshots other than Norway, and the frontend
badges listed above) is WS-26-dependent; (c) `canada_monitor` reads DFO Pacific
lice CSVs, not `lice_records`, so it keeps its own DFO provenance.

### WS-15 Â· Quota tracker window + AI-LPI magnitude
**Why:** `_get_pa_lice_data` filters `year == max(year)` only (it computes
`max(week)` and never uses it), so "latest" is a year-to-date average; and the
national utilisation reads **238,367 %** with every PA over quota â€” the emission
model's magnitude is implausible. A correct live badge on that number is a
credibility problem WS-1 cannot fix.
**Files:** `core/market/lice_quota_tracker.py` (`_get_pa_lice_data`,
`_estimate_farm_emission`, `PA_HYPOTHETICAL_QUOTA`), `core/market/indices.py`
(`INDEX_METHOD_VERSION` bump â€” revision policy), `docs/INDICES.md`.
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

### WS-16 Â· Lice ingest health (blocks any live AI-LPI)
**Why:** the last real lice rows arrived 2026-04-07; the 2026-10-12 tick logged
"0 new lice records for 2026-W42"; `lice_records` is `dead` with 0 verified rows.
**Files:** `agents/data_ingest.py`, `core/barentswatch.py`, `.env` (BarentsWatch
credentials), `core/market/freshness_monitor.py` (alerting â€” WS-9).
**Steps:** diagnose the 0-row tick (auth, endpoint, `hasReported` filter), fix it,
then let the backfill (which now skips only verified weeks) re-ingest 2020â†’now â€”
roughly 350 sequential POSTs; pace it if BarentsWatch rate-limits.
**Acceptance:** `/api/data-freshness` lice `fresh` with `verified_rows > 0`; AI-LPI
`is_live: true` once the window is all `barentswatch`, every PA current and fresh;
a test proving a 0-row tick raises an alert (WS-9). **Traps:** never relabel rows
by hand â€” the upsert is the only honest path to `barentswatch`. `fetched_at` is a
write time: the re-ingest bumps it on old weeks, which is why the lineage gates on
the observation week too â€” the freshness monitor still reads `fetched_at`, so it
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

### WS-17 Â· Accuracy publisher column bug
**Why:** `scripts/publish_accuracy.py::_db_series` selects `price_nok` but the
column is `price_nok_kg`; a bare `except` hides it, so its demo-row skip has never
actually run against the DB (the live-fetch path masked it).
**Files:** `scripts/publish_accuracy.py`, `tests/test_accuracy_registry.py`.
**Steps:** fix the column, narrow the except, import `SYNTHETIC_MARKERS` from
`core/source_lineage.py` instead of the local copy, regression test on a seeded
temp DB. **Acceptance:** `_db_series()` returns rows and reports
`skipped_synthetic` on a demo-seeded DB. **Traps:** never add a `--force` bypass.

### WS-18 Â· Stamped-but-unmigrated dev databases
**Why:** `data/openclaw.db` is stamped 018 but lacks 015's `ix_lice_year_week`:
the conftest stamps `create_all`-built DBs at head, so a migration whose DDL the ORM
does not declare (indexes, backfills) can be skipped silently.
**Files:** `tests/conftest.py`, `core/production_truth.py`, `core/models.py::init_db`.
**Steps:** a verifier check comparing migration-declared indexes with
`inspect(engine).get_indexes`; guard-create `ix_lice_year_week`.
**Acceptance:** the verifier reports index drift on this box before the fix and ok
after; `EXPLAIN` on `/api/lice/summary` uses the index. **Traps:** never fix by
stamping; 019 survives this because it is existence-guarded â€” new migrations must be.

### WS-19 Â· Guard the index history before any agent runs â€” **DONE 2026-10-17**
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
`tests/test_migrations.py::test_020_â€¦` â€” all 7 failed on the old code.
**Acceptance met:** AI-STI moves in its documented direction per component and
reads exactly 0 and 100 at Â±10 % momentum; no computation of any code calls the
lice-quota tracker; a real publisher tick (test, and once on a backup copy of this
box's DB) stores only AI-STI at 2.0.0 with no quota input â€” on this box it stores
nothing because AI-STI has no value ("no comparable prior period"). The two
2026-W42 rows are marked `superseded_by='2.0.0'` with their values intact.
Review fixes: the digest degrades when AI-STI does (the read rests on it alone)
and the supply panel follows the biomass tracker's lineage; the freshness monitor
ignores superseded rows (`SourceSpec.excluded_when_set`); GTM copy no longer sells
AI-LPI; `docs/openapi.frozen.json` re-frozen deliberately (two descriptions only â€”
response shapes had changed). **Left open:** no lice index is published (a rebuild
needs observable facts and verified lice rows â€” WS-16, then a new method version);
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

### WS-20 Â· Public honesty: landing page, API docs, plan ladder, one name â€” **PARTLY DONE 2026-10-17**
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
Anonymous `GET /api/signals` serves 50 SHORT signals on Grieg, LerÃ¸y, Mowi and SalMar
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

### WS-21 Â· Regulatory facts as dated, sourced data â€” **DONE 2026-10-17**
**Done:** `core/regulatory_facts.py` (decisions, dated capacity cuts, Â§ 8 limits by
region and week, dated US tariff rows) and its consumers; see CHANGELOG.
**Verification note:** every fact was researched on 2026-10-17 and checked by two
independent verifiers against primary sources: the regjeringen.no announcements and
the Lovdata capacity regulations (FOR-2017-12-20-2397, FOR-2020-02-04-105,
FOR-2022-06-07-972, FOR-2024-03-22-515, FOR-2026-08-20-1764), lakselusforskriften
Â§ 8/Â§ 10 on Lovdata, the Federal Register Section 301 notice 2026-15181 and HTSUS
0302.14/0304.41. Medium-confidence items: the cut start dates for 2022, 2024 and 2026
(in-force + 6 months, Â§ 9; 2020 is from LG-2021-80234) and the Faroes' US tariff (assumes
the Faroes are their own country of origin).
**Follow-ups (not done):** (1) still on a flat 0.5 limit: `treatment_optimizer.py`,
`core/valuechain/farmer_advisory.py`, `lice_quota_tracker.py` (risk level),
`core/ml/harvest_optimizer.py`, `supply_demand_engine.py`, `correlation_engine.py` â€”
route each through `regulatory_facts.lice_limit`; (2) the simulator models a colour as a
capacity level, not the next decision's step (red cuts again, yellow restores nothing),
and disagrees with `event_impact_model`; (3) the `/api/chat` system prompt and
`core/llm/rag.py` state lice-derived colours, an annual cadence and 0.2 as a reporting
threshold, and the rule-based chat crashes on a traffic-light question
(`core/api.py`, `states.items()` on a list); (4) a full municipality â†’ county table
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
in Nord-TrÃ¸ndelag and southwards, weeks 21-26 in Nordland, Troms and Finnmark;
lakselusforskriften Â§ 8) in both the decision engine and the reporter; the July 2026
tariffs (Norway 12.5%, Chile 12.5%, UK 10%; Faroes and Iceland outside the new
measure; Canada USMCA-exempt), each payload citing its `source_url`.

### WS-22 Â· Numbers buyers check â€” **STALE-DECISION + DATA-CLAIM FIXES DONE**
**Stale-decision rule shipped:** `core/market/decision_engine.py` dates the newest
count on the card (`_lice_observation_time` â€” the card's lineage via
`observation_time`, else its `current_year`/`current_week`) and refuses to
recommend a treatment when that count is older than `STALE_LICE_MAX_DAYS = 14`
(two BarentsWatch reporting periods): `action: "MONITOR"`, `urgency: "data_stale"`,
the age/week/rule in `reasoning`, `lice_predicted_next_week` withheld (same stale
rows), `data_stale` + `lice_data_age_days` on the payload, and zero costs (MONITOR
already zeroes ROI). An undatable count is stale, never fresh. Cards no longer act
on months-old rows; the treatment portfolio's `total_treatment_cost_nok` therefore
stops counting farms nobody refreshes. `tests/test_decision_stale_data.py` (5).
Remaining WS-22 items below are open.
**Data-claim fixes shipped 2026-10-18** (`tests/test_ws22_data_claims.py`, 21):
competitiveness records every FX rate that fell back and reports
`data_quality: partial_fallback` + `fx_fallbacks` + a degraded `data_provenance` (it
used to say `live` while priced with NOK/USD 0.093). Two silent fallbacks behind that
label were repaired too: both macro lookups imported `macro_intelligence_engine`,
which does not exist (the singleton is `macro_intelligence`), so NOK/USD always fell
back and the US spot was always the undated USD 8.50 constant; the spot fallback is
now tracked (`us_spot_fallback`) and degrades the payload. `/api/accuracy` derives
`foundation_models_available` from the library that loads each model
(`chronos-forecasting` / `timesfm` / `uni2ts` plus torch) with per-model
`installed`/`loaded`, never from `import torch` alone; `newest_first_cases()` sorts
the disease list by diagnosis date before the 20-row cap and the summary reports
`active_outbreaks_shown` against `active_outbreaks_total`; `_fetch_norway_alerts()`
queries Mattilsynet and emits **one alert per disease type with `cases` = active
localities** (one row per locality inflated `active_outbreaks` and `risk_level`),
`MattilsynetClient.last_fetch_ok` separates an empty answer from a failed one and
survives a cache hit, and `/api/disease/alerts` builds provenance from the sources
that answered (`sources` / `sources_failed`). `/api/disease/{norway,norway/geo,
treatments,by-company}` share `_mattilsynet_provenance()`: live only when Mattilsynet
answered **and** returned rows. The competitiveness and disease pages render the
served `data_provenance` instead of a hardcoded `quality="live"` badge.
**Honest limitation:** a case reported by both WOAH and Mattilsynet appears twice, so
`active_outbreaks` counts source reports, not unique epidemiological events.
**Still open here:** Mowi's 113,600 t (localities Ã— 800 in `top50_engine`), the smolt
pipeline and `biomass_current_tonnes`, the brief counting every stored bloom row, the
ROI defaults (228x / 491x / 1,693x), `api_calls_month` never incremented, and
`/api/ml/chronos/model-comparison` printing per-call metrics on demo rows.
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

### WS-23 Â· Accuracy against a strong baseline (contaminated backtest) â€” **DONE 2026-10-17 (weekly forecast log still open)**
**Takedown shipped:** no route prints an accuracy figure the registry does not
hold. `core/market/price_ml.py` never reads `data/models/price_backtest.json` for
display (`mape_backtest`/`band_trust` null; the statement points at
`/api/accuracy`), and loads conformal residuals only from an artifact declaring
`demo_rows_used: 0` **and** the served `model_version`; `/api/market/price-outlook`
stores at most one prediction per ISO week and horizon; `/api/market/prediction-history`
serves `mape_backtest: null`; the `/api/ml/*/model-comparison` routes withhold
their request-time MAPE/RMSE/coverage (`accuracy_registry.withhold_unregistered_metrics`);
the supply-demand path dropped its "~80% coverage" claim and serves its artifact
only when registered. `tests/test_accuracy_claims.py` (in the fast gate).
**Re-run shipped:** `scripts/backtest_price_ml.py` classifies every DB row through
`core/source_lineage` and refuses synthetic ones (counted in `demo_rows_used` /
`history_provenance`, artifact not written if any entered), scores a
horizon-matched carry-forward baseline on the same points, and runs a
Diebold-Mariano test per horizon. `scripts/publish_accuracy.py --from-backtest`
publishes `price_ensemble_walk_forward` + `carry_forward_weekly_prices` on one
window and exits 2 writing nothing on a missing artifact, `demo_rows_used != 0`,
a tier mismatch against `price_ensemble.model_version`, a missing baseline or
fewer than 30 points. Measured 2020W01â€“2026W40 (real rows only, 88 points at 4w):
4w MAPE 9.05% vs carry-forward 9.44%, DM p=0.0031 (model lower loss); 2w 6.40 vs
6.52 (p=0.32, not significant); 8w 12.83 vs 13.61 (p=0.0002). 80% band coverage
71.6% at 4w / 64.8% pooled. `tests/test_ws23_backtest_honesty.py` (16) pins the
loader refusals, the DM behaviour and every publisher refusal.
**Still open:** (a) the weekly forecast log, scored against carry-forward and
stored where tests cannot write; (b) serving exactly the backtested
configuration â€” the live outlook adds lice/supply signals the backtest holds
neutral (disclosed in the artifact `method`, so the claim is not overstated, but
the score still does not cover the served response); (c) the in-process
`PriceEnsemble.retrain()` sets residuals without a lineage declaration (its bands
then say so); (d) the 879 stored MAPE copies stay in `price_predictions`,
unserved; (e) `tests/test_entitlements.py` and
`tests/test_price_outlook_resilience.py` still call the outlook against the real
store (WS-24); (f) on Python 3.14 `predict()` reaches the TFT tier only inside a
running event loop (`asyncio.get_event_loop()` raises outside one).
**Why (history):** the price outlook printed "Backtested 4-week MAPE: 8.5%" from
`data/models/price_backtest.json` (2026-10-12). That run merged the database's SSB
rows over the real CSV, database winning (`load_ssb_series`), and all 52 database
rows are `demo_seed` (2025W01-W52) â€” trap 6. The figure was also copied into
`price_predictions` on every outlook request and served by
`/api/market/prediction-history`.
**Files:** `scripts/backtest_price_ml.py`, `scripts/publish_accuracy.py`,
`core/market/price_ml.py`, `core/routers/accuracy_routes.py`,
`tests/test_ws23_backtest_honesty.py`.
**Acceptance (met):** `/api/accuracy` lists carry-forward and the served model on
one window with the test result; no route prints an accuracy figure the registry
does not hold; a test that the backtest loader refuses `demo_seed` rows.
**Added 2026-10-17 (WS-20 review):** `/api/ml/chronos/model-comparison` returns
`mape`/`rmse`/`coverage_80` per model from a single holdout of `horizon` points
(`core/ml/chronos_baseline.py::compare_models`), on a series whose newest weeks are
the `demo_seed` DB rows. It is covered by the acceptance above: drop the figures or
label them as per-call diagnostics on real rows only.

### WS-24 Â· Test isolation for the dev database
**Why:** test runs wrote all 260 `design_partners` rows ("X", "Scorecard Co", "Recip
Co"), audit rows and price predictions into `data/openclaw.db`, the same trap the
WS-2 publish tests had. **Acceptance:** a full test run leaves the row counts of
`design_partners`, `audit_logs`, `price_predictions` and `index_observations` in the
dev DB unchanged.

### WS-25 Â· Cold starts off the request path
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

### WS-26 Â· Navigation cut (owner decides the list; do it early)
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

### WS-27 Â· Design identity (layer 1 now, layer 2 after the owner decides)
**Why:** one template (translucent gradient cards, KPI tiles, fade-ins, blurred
chrome; about 355 `GlassCard` and 260 `KPICard` tags) is repeated across the app, the
product shows two names, and the chrome claims "LIVE" on weekly data.
VALUE_ANALYSIS section 7 splits the fix in two. Layer 1, content conventions:
week-and-source stamps, a confidence mark on every figure, seasonal fans, 13-area
small multiples, editorial charts, one number formatter. Layer 2, the optional
"SjÃ¸kart" visual system: S-52 chart palette, a Norwegian display face, hairline
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

### WS-28 Â· Remaining equity-direction surfaces + the legal opinion
**Why:** WS-20 took down the signal generator's SHORT/LONG calls everywhere they were
shown, but other surfaces still put a direction or a per-company financial impact
next to a listed salmon share, and the agents that wrote the calls still exist.
`/api/legal/advice-boundary` publishes this list as `under_review`.
**Surfaces (measured 2026-10-17):** `GET /api/pairs/signals` and the pairs cards on
/signals and the dashboard (`DashboardLiveIntelligence`, `DashboardProduction`) â€”
paired positions on listed shares from the frozen `pairs_engine`; `GET
/api/sentiment/signals` and the /signals sentiment card â€” per-ticker sentiment on
MOWI/SALM/LSG/GSF; `GET /api/orders` â€” anonymous paper order history (one filled
SELL GSF on this box); the /trader Event Impact Simulator â€” per-company revenue and
stock-move estimates (`core/predictors/event_impact_model.py`); writers of
directional rows to `signals`, which run only with the agents service: the signal
generator, the market hedger (`agents/market_hedger_agent.py`, LONG/SHORT on listed
tickers â€” `/api/market/hedger-signals` now serves only `SALMON_SPOT`), the
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
| 2 | **SQLite drops tzinfo** | A datetime read back is naive â†’ `days_remaining` was always `None`. Coerce with an `_as_utc()` helper before comparing. |
| 3 | **SQLite returns ISO strings** | Timestamps come back as **strings**, so `isinstance(x, datetime)` is false and freshness read `unknown` for every source. Parse defensively (str/date/int/datetime). |
| 4 | **SSB week labels** | `get_price_history` returns `"week": "W42"` â†’ `int()` raises `ValueError`. Strip a leading `W`. |
| 5 | **Ratchet inventories** | Never derive a route inventory from the **live app**: other tests inject `/api/test-*` routes and break it. Use `docs/openapi.frozen.json`. |
| 6 | **Demo-seeded rows** | `ssb_weekly_prices` is `source='demo_seed'`; `lice_records.source` is `barentswatch` / `demo_seed` / `unverified` (WS-1). Never measure accuracy on synthetic rows; never claim `is_live` from `demo_seed` or `unverified`. |
| 7 | **Empty `alembic_version`** | A `create_all`-built dev DB has an empty version table; the verifier calls that drift. `tests/conftest.py` reconciles missing columns and stamps head for dev/test only. |
| 8 | **`--timeout` is unavailable** | No pytest-timeout plugin. Background long runs with `Start-Process ... -RedirectStandardOutput` and poll the file. |
| 9 | **PowerShell hides tracebacks** | Pipe to a file with `cmd /c "python x.py > out.txt 2>&1"`, then read `out.txt`. `git push` can exit 1 on success â€” confirm with `git ls-remote`. |
| 10 | **Contract + baseline re-freeze** | Any new route changes `docs/openapi.frozen.json` **and** the provenance baseline. Re-freeze deliberately (`freeze_openapi.py`, `provenance_ratchet.py --update`) â€” never just to make a failure disappear. |
| 11 | **Demo locality numbers live in the real range** | `DEMO_LOCALITIES` 10001â€“10022 sit inside BarentsWatch's 5-digit numbering (the lowest real locality on the dev DB is 10029; no real row shares a demo number today, but nothing reserves the range). Identify demo rows only by `source='demo_seed'`, never by locality. A first measurement here wrongly counted 10027/10029 as demo â€” re-measure before repeating a number. |
| 12 | **Column presence is not lineage** | `lice_records.source` existing says nothing about the rows â€” a demo-seeded CI database has the column too. Claim live only from `summarise_lineage` over the rows actually used. |
| 13 | **Empty `alembic_version` bricks the ingest** | A `create_all`-built DB whose chain aborts at 001 never runs 019, so every lice insert fails. Recover with `alembic stamp 018` then `alembic upgrade head` â€” never stamp head. The verifier's `lice_source_column` check catches it. |
| 14 | **The freshness monitor runs in a worker thread** | `fm.report()` uses `asyncio.to_thread`; an in-memory SQLite engine is empty in that thread. Test it with a file-backed engine. |
| 15 | **Long shell heredocs on this box** | Git-Bash `cat <<'EOF'` with a long Python body intermittently fails to parse. Write the patch to a file and run `python file.py`. |
| 16 | **Tests used to publish into the real index store** | Until WS-2 the publish tests stored the current week into the dev DB on every run; this box's 2026-W42 rows predate the lineage guard and the AI-LPI one claims `is_live: true`. Use the `observation_store` fixture for anything that writes observations; never read the dev box's published history as evidence of the agent. The rows store the defect values (AI-STI 100 severe; AI-LPI 55 claiming `is_live: true`) at method 1.0.0; since WS-19 (Alembic 020) they are marked `superseded_by='2.0.0'` and no longer count for any week. Never delete them. |
| 17 | **The test bootstrap migrates the dev DB** | `tests/conftest.py::_bootstrap_test_database` runs `alembic upgrade head` against `data/openclaw.db` at collection, so a new migration is applied to the dev DB by the first test run â€” write migrations to be safe on real data before running any test. |
| 18 | **The dev DB is in WAL mode** | Recent writes sit in `data/openclaw.db-wal`; `cp data/openclaw.db x.db` gives a stale copy (missing columns a migration just added). Copy with the SQLite backup API (`src.backup(dst)`). |
| 19 | **A swallowed `ImportError` makes a live path dead** | `competitiveness_engine.py` imported `macro_intelligence_engine`, which does not exist (the singleton is `macro_intelligence`), inside `try/except Exception` â€” so NOK/USD **always** fell back to 0.093 and the US spot **always** returned the undated 8.50 constant while the payload said `live`. When a `try` wraps a lazy import, assert the import name in a test (`test_ws22_data_claims.py::test_live_nok_rate_is_used_when_macro_answers`) or the fallback becomes permanent and invisible. |
| 20 | **`pytest tmp_path` on Windows under this harness** | `os.mkdir(path, 0o700)` (what pytest's basetemp does) creates a directory whose DACL excludes the signed-in user on this box (Python 3.14), so every `tmp_path` fixture errors at setup with `PermissionError: [WinError 5]` and the run reports `E` for a large slice of the suite. Workaround used here and NOT committed: put a `sitecustomize.py` on `PYTHONPATH` that forces `os.mkdir(path, 0o777, dir_fd=...)`, and point `TMP`/`TEMP` at a writable **workspace** directory (a fresh one: an already-broken `pytest-of-<user>` makes `make_numbered_dir` fail again). Diagnostic: a directory created by `os.mkdir(p, 0o700)` cannot be listed even by PowerShell (`icacls` reports access denied). |
| 21 | **A fetch time is not an observation date** | `feed_cost_engine.get_latest()` stamped `data_freshness.feed_prices` with the request time while the FRED "global price" series end **2026-07** â€” a three-month-old observation presented as current on the flagship cost surface. Any monthly/lagged source must carry the observation date (`IngredientPrice.observed_at`, `feed_prices_as_of`) and the payload must degrade with the month named (WS-29, `FEED_PRICE_MAX_AGE_DAYS`). Same rule as the lice lineage: freshness is when the data was *observed*. |
| 22 | **PowerShell string surgery re-encodes UTF-8 files** | Editing a UTF-8 source with `(Get-Content -Raw).Replace(...) \| Set-Content` silently rewrote the file in the console code page (one em dash became byte `0x97`) and every later tool failed with `E902 stream did not contain valid UTF-8`. Use the editor/`write` tool for code, or Python with `encoding="utf-8"`; never `Set-Content` on a file containing non-ASCII. Recovery: decode the bytes as UTF-8 and map the stray `0x80â€“0x9F` bytes back to their CP1252 punctuation. |
| 23 | **A column default is not a data source** | `chlorophyll_readings.dataset_id` defaulted to the Atlantic 1 km L3 product while the client fetches the global 4 km gap-free L4 one, so 613 141 stored rows described a dataset that was never read — and the two products are not interchangeable (resolution, gap-filling). Record the identifier the fetch actually used, never a model default; the bloom payload now groups stored ids and warns when they disagree with the client (WS-33). |

## 7. Definition of done for the next module

A takeover session is complete when:

1. The fast gate (Â§2) passes; if you added routes, both re-freezes were deliberate and
   the OpenAPI contract test passes.
2. Every bug found has a regression test; every honesty gap closed is **visible in an
   API response or a doc**, not only in code comments.
3. `CHANGELOG.md`, `PROJECT_STATUS.md`, `STATUS.md` and the relevant `docs/*.md` are
   updated â€” documentation is part of the deliverable.
4. No second source of truth was introduced (plans, provenance boundary, licence
   register, accuracy registry).
5. Anything unfinished is written as a numbered workstream in this file **with
   acceptance criteria**, never left as a silent gap.




