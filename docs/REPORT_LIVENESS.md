# Route Liveness Report

> Generated 2026-10-16 15:05 UTC by `scripts/probe_liveness.py`.
> Parameterless GET routes only. The weakest nested provenance governs a
> route's headline state, so the report is conservative.

## Summary

| State | Routes |
|---|---|
| `error` | 60 |
| `no_provenance` | 50 |
| `live` | 48 |
| `degraded` | 42 |
| `auth_401` | 11 |
| `http_422` | 5 |
| `http_5xx` | 2 |
| `simulated` | 1 |

**Probed:** 219 routes.

## Not claiming live

| Path | State | HTTP | Source | Reason |
|---|---|---|---|---|
| `/api/admin/audit-log` | auth_401 | 401 |  |  |
| `/api/admin/cache-stats` | auth_401 | 401 |  |  |
| `/api/admin/data-quality` | auth_401 | 401 |  |  |
| `/api/admin/export-summary` | auth_401 | 401 |  |  |
| `/api/admin/status` | auth_401 | 401 |  |  |
| `/api/audit` | auth_401 | 401 |  |  |
| `/api/billing/invoice-history` | auth_401 | 401 |  |  |
| `/api/billing/subscription-status` | auth_401 | 401 |  |  |
| `/api/cache/stats` | auth_401 | 401 |  |  |
| `/api/keys` | auth_401 | 401 |  |  |
| `/api/webhooks` | auth_401 | 401 |  |  |
| `/api/ais/harvest-intelligence` | degraded | 200 | BarentsWatch AIS vessel positions | no AIS positions ingested — vessel-derived signals are empty |
| `/api/ais/supply-intelligence` | degraded | 200 | BarentsWatch AIS vessel positions | no AIS positions ingested — vessel-derived signals are empty |
| `/api/anomaly/alerts` | degraded | 200 | BarentsWatch lice + PyOD anomaly detection | detector output — derived from the current lice series, not a reported regulatory finding |
| `/api/china/demand` | degraded | 200 | GACC/Comtrade estimates (SSB 08799 unavailable) | live Norwegian export series unavailable — using curated estimates |
| `/api/china/demand-impact` | degraded | 200 | GACC/Comtrade estimates (SSB 08799 unavailable) | live Norwegian export series unavailable — using curated estimates |
| `/api/china/demand-signals` | degraded | 200 | GACC/Comtrade estimates (SSB 08799 unavailable) | live Norwegian export series unavailable — using curated estimates |
| `/api/climate/projections` | degraded | 200 | Climate risk engine (CMIP-style projection over MET.no baseline) | forward projection over a warming scenario — a modelled estimate, not an observed measurement |
| `/api/contracts/hedge-signals` | degraded | 200 | Contract risk engine (forward curve + spot basis model) | derived contract-risk context over the forward curve — a model estimate, not a quoted contract price |
| `/api/farm-graph/summary` | degraded | 200 | Farm network graph (BarentsWatch lice + locality registry) | derived proximity/network graph over registered localities — a model artefact, not a reported figure |
| `/api/feed-supply-chain/summary` | degraded | 200 | BioMar/Skretting sustainability reports + IFFO + EUDR Reg 2023/1115 | model-based composition with approximate commodity prices — not a live feed |
| `/api/futures/basis` | degraded | 200 |  |  |
| `/api/futures/forward-curve` | degraded | 200 |  |  |
| `/api/futures/settlement` | degraded | 200 | SSB Table 03024 (proxy for FPI) | Fish Pool settlement data unavailable |
| `/api/futures/term-structure` | degraded | 200 |  |  |
| `/api/global/lice` | degraded | 200 | BarentsWatch lice (Norway) + DFO Canada | no country monitor returned features — this layer is empty |
| `/api/integrations/fishtalk/status` | degraded | 200 | Fishtalk 5 API | FISHTALK_API_KEY not configured |
| `/api/investor/event-impact/feed-shock` | degraded | 200 | Event impact model (scenario simulation) | modelled impact of a hypothetical event — a scenario estimate, not an observed market move |
| `/api/investor/event-impact/isa` | degraded | 200 | Event impact model (scenario simulation) | modelled impact of a hypothetical event — a scenario estimate, not an observed market move |
| `/api/investor/event-impact/traffic-light` | degraded | 200 | Event impact model (scenario simulation) | modelled impact of a hypothetical event — a scenario estimate, not an observed market move |
| `/api/lice/summary` | degraded | 200 | BarentsWatch Fishhealth API | 27 weeks stale |
| `/api/market/forward-curve` | degraded | 200 | SSB Table 03024 (synthesized) | forward curve is synthesized from historical seasonal factors applied to the current SSB spot — not a traded f |
| `/api/market/price-forecast` | degraded | 200 | SSB Table 03024 spot + salmon_price model | inputs are the SSB spot and the local lice database; the price path itself is a model estimate, not a quoted m |
| `/api/market/price-outlook` | degraded | 200 | SSB Table 03024 + price ensemble (ensemble_v1_rule) | ML tiers unavailable — rule-based forecast |
| `/api/market/price-outlook/multi` | degraded | 200 | SSB Table 03024 spot + price_ml ensemble | multi-horizon paths are model estimates (Monte Carlo + rule-based signals), not quoted forward prices |
| `/api/market/seasonal` | degraded | 200 | SSB Table 03024 (seasonal medians) | seasonal expectation derived from historical SSB medians — a comparison baseline, not a quoted price |
| `/api/ml/chronos/supply-forecast` | degraded | 200 | Amazon Chronos zero-shot | model unavailable — seasonal-naive fallback used (requested: Amazon Chronos zero-shot) |
| `/api/ml/moirai/model-comparison` | degraded | 200 | Salesforce MOIRAI-2 zero-shot | members computed from seasonal-naive fallback: moirai |
| `/api/ml/moirai/price-forecast` | degraded | 200 |  |  |
| `/api/ml/moirai/supply-forecast` | degraded | 200 | Salesforce MOIRAI-2 zero-shot | model unavailable — seasonal-naive fallback used (requested: Salesforce MOIRAI-2 zero-shot) |
| `/api/ml/timesfm/model-comparison` | degraded | 200 | Google TimesFM 2.5 zero-shot | members computed from seasonal-naive fallback: timesfm |
| `/api/ml/timesfm/price-forecast` | degraded | 200 |  |  |
| `/api/ml/timesfm/supply-forecast` | degraded | 200 | Google TimesFM 2.5 zero-shot | model unavailable — seasonal-naive fallback used (requested: Google TimesFM 2.5 zero-shot) |
| `/api/parametric/dashboard` | degraded | 200 | Parametric insurance engine (lice / bloom / temperature triggers) | derived trigger and payout model over internal lice/bloom data — an estimate, not a quoted insurance price |
| `/api/parametric/risk-profile` | degraded | 200 | Parametric insurance engine (lice / bloom / temperature triggers) | derived trigger and payout model over internal lice/bloom data — an estimate, not a quoted insurance price |
| `/api/ras/summary` | degraded | 200 | RAS land-based tracker (published project capacities) | aggregated from published project/company announcements — indicative capacity, not audited production |
| `/api/ras/timeline` | degraded | 200 | RAS land-based tracker (published project capacities) | aggregated from published project/company announcements — indicative capacity, not audited production |
| `/api/regulatory/traffic-light/all-scenarios` | degraded | 200 | Traffic-light simulator (hypothetical regulatory scenario) | modelled effects of counterfactual colour changes — scenario estimates, not announced regulatory decisions |
| `/api/regulatory/traffic-light/simulate` | degraded | 200 | Traffic-light simulator (hypothetical regulatory scenario) | modelled effect of a counterfactual colour change — a scenario estimate, not an announced regulatory decision |
| `/api/self-improvement/proposals` | degraded | 200 | Internal self-improvement audit log | proposals are derived from the platform's own audit trail — internal model suggestions, not external findings |
| `/api/sentiment/poll` | degraded | 200 | News feeds | poll returned no new articles |
| `/api/sentiment/summary` | degraded | 200 | News feeds | no articles analysed in the last 24h — sentiment buckets are empty |
| `/api/supply/demand-balance` | degraded | 200 | SSB 03024 + smolt pipeline + global supply + lice DB + china demand | fallbacks: china demand: live SSB exports unavailable (estimates used) |
| `/api/analytics/lice-quota/national` | error | None |  | timeout |
| `/api/benchmark/leaderboard` | error | None |  | timeout |
| `/api/benchmark/summary` | error | None |  | timeout |
| `/api/brief` | error | None |  | timeout |
| `/api/canada/farms` | error | None |  | timeout |
| `/api/canada/lice` | error | None |  | timeout |
| `/api/canada/lice-by-region` | error | None |  | timeout |
| `/api/canada/snapshot` | error | None |  | timeout |
| `/api/causal/granger` | error | None |  | timeout |
| `/api/causal/summary` | error | None |  | timeout |
| `/api/chile/production-history` | error | None |  | timeout |
| `/api/chile/snapshot` | error | None |  | timeout |
| `/api/climate/risk-scores` | error | None |  | timeout |
| `/api/competitiveness/origin-index` | error | None |  | timeout |
| `/api/compliance/asc/readiness-summary` | error | None |  | timeout |
| `/api/disease/resistance-map` | error | None |  | timeout |
| `/api/disease/treatments` | error | None |  | timeout |
| `/api/esg/scores` | error | None |  | timeout |
| `/api/esg/summary` | error | None |  | timeout |
| `/api/exposure/sites` | error | None |  | timeout |
| `/api/farm-graph/cascades` | error | None |  | timeout |
| `/api/farm-graph/clusters` | error | None |  | timeout |
| `/api/farm-graph/company-exposure` | error | None |  | timeout |
| `/api/farm-graph/map-data` | error | None |  | timeout |
| `/api/farms/biomass/national` | error | None |  | timeout |
| `/api/farms/offshore/lice-comparison` | error | None |  | timeout |
| `/api/faroe/farms` | error | None |  | timeout |
| `/api/faroe/snapshot` | error | None |  | timeout |
| `/api/federated/cohorts` | error | None |  | timeout |
| `/api/feed-cost/alerts` | error | None |  | timeout |
| `/api/feed-cost/composite-index` | error | None |  | timeout |
| `/api/feed-cost/enhanced-anchovy` | error | None |  | timeout |
| `/api/feed-cost/historical-prices` | error | None |  | timeout |
| `/api/feed-cost/history` | error | None |  | timeout |
| `/api/feed-cost/latest` | error | None |  | timeout |
| `/api/feed-cost/peru-anchovy` | error | None |  | timeout |
| `/api/feed-supply-chain/live` | error | None |  | timeout |
| `/api/global-supply` | error | None |  | timeout |
| `/api/iceland/exports` | error | None |  | timeout |
| `/api/iceland/farms` | error | None |  | timeout |
| `/api/iceland/production` | error | None |  | timeout |
| `/api/iceland/snapshot` | error | None |  | timeout |
| `/api/leaders/pa-leaderboard` | error | None |  | timeout |
| `/api/leaders/top100` | error | None |  | timeout |
| `/api/leaders/top30` | error | None |  | timeout |
| `/api/macro/snapshot` | error | None |  | timeout |
| `/api/market/biomass` | error | None |  | timeout |
| `/api/market/equity-prices` | error | None |  | timeout |
| `/api/market/eumofa/salmon-prices` | error | None |  | timeout |
| `/api/market/eumofa/trade-flows` | error | None |  | timeout |
| `/api/market/ssb-seasonal` | error | None |  | timeout |
| `/api/notifications/alerts` | error | None |  | timeout |
| `/api/notifications/alerts/rules/evaluate` | error | None |  | timeout |
| `/api/notifications/history` | error | None |  | timeout |
| `/api/satellite/pace/hab-risk` | error | None |  | timeout |
| `/api/satellite/products` | error | None |  | timeout |
| `/api/satellite/status` | error | None |  | timeout |
| `/api/scenarios/list` | error | None |  | timeout |
| `/api/scotland/farms` | error | None |  | timeout |
| `/api/scotland/snapshot` | error | None |  | timeout |
| `/api/farms/portfolio` | http_422 | 422 |  |  |
| `/api/harvest/simulate` | http_422 | 422 |  |  |
| `/api/ocean/norkyst/current` | http_422 | 422 |  |  |
| `/api/ocean/temperature` | http_422 | 422 |  |  |
| `/api/satellite/pace/chlorophyll` | http_422 | 422 |  |  |
| `/api/gnn/predict-all` | http_5xx | 503 |  |  |
| `/api/market/price-outlook/explain` | http_5xx | 503 |  |  |
| `/api/ais/harvest-signals` | no_provenance | 200 |  |  |
| `/api/ais/tracks` | no_provenance | 200 |  |  |
| `/api/ais/treatment-signals` | no_provenance | 200 |  |  |
| `/api/alerts` | no_provenance | 200 |  |  |
| `/api/alerts/preferences` | no_provenance | 200 |  |  |
| `/api/analytics/yoy-comparison` | no_provenance | 200 |  |  |
| `/api/auth/me` | no_provenance | 200 |  |  |
| `/api/auth/tiers` | no_provenance | 200 |  |  |
| `/api/chat/history` | no_provenance | 200 |  |  |
| `/api/chile/signals` | no_provenance | 200 |  |  |
| `/api/compliance/deadlines` | no_provenance | 200 |  |  |
| `/api/disclaimer` | no_provenance | 200 |  |  |
| `/api/farms/offshore` | no_provenance | 200 |  |  |
| `/api/federated/privacy-info` | no_provenance | 200 |  |  |
| `/api/feed-supply-chain/eudr-risk` | no_provenance | 200 |  |  |
| `/api/feed-supply-chain/scenarios` | no_provenance | 200 |  |  |
| `/api/health` | no_provenance | 200 |  |  |
| `/api/intelligence/health` | no_provenance | 200 |  |  |
| `/api/intelligence/summary` | no_provenance | 200 |  |  |
| `/api/localities/search` | no_provenance | 200 |  |  |
| `/api/market/feed-status` | no_provenance | 200 |  |  |
| `/api/market/hedger-signals` | no_provenance | 200 |  |  |
| `/api/market/prediction-history` | no_provenance | 200 |  |  |
| `/api/metrics` | no_provenance | 200 |  |  |
| `/api/metrics/prometheus` | no_provenance | 200 |  |  |
| `/api/notifications/alerts/rules` | no_provenance | 200 |  |  |
| `/api/notifications/thresholds` | no_provenance | 200 |  |  |
| `/api/ocean/currents/status` | no_provenance | 200 |  |  |
| `/api/ocean/waves/status` | no_provenance | 200 |  |  |
| `/api/orders` | no_provenance | 200 |  |  |
| `/api/pairs/all` | no_provenance | 200 |  |  |
| `/api/pairs/signals` | no_provenance | 200 |  |  |
| `/api/parametric/products` | no_provenance | 200 |  |  |
| `/api/parametric/triggers` | no_provenance | 200 |  |  |
| `/api/production/annual` | no_provenance | 200 |  |  |
| `/api/production/by-county` | no_provenance | 200 |  |  |
| `/api/production/monthly` | no_provenance | 200 |  |  |
| `/api/ras/companies` | no_provenance | 200 |  |  |
| `/api/rate-limit-info` | no_provenance | 200 |  |  |
| `/api/regime/alerts` | no_provenance | 200 |  |  |
| `/api/regime/company-risk` | no_provenance | 200 |  |  |
| `/api/regime/states` | no_provenance | 200 |  |  |
| `/api/satellite/anomalies` | no_provenance | 200 |  |  |
| `/api/sentiment/articles` | no_provenance | 200 |  |  |
| `/api/sentiment/signals` | no_provenance | 200 |  |  |
| `/api/signals` | no_provenance | 200 |  |  |
| `/api/tiers` | no_provenance | 200 |  |  |
| `/api/traceability/certificates` | no_provenance | 200 |  |  |
| `/api/treatment/efficacy-by-method` | no_provenance | 200 |  |  |
| `/api/webhooks/events` | no_provenance | 200 |  |  |
| `/api/twin/status` | simulated | 200 | simulated | digital twin state is a simulation of farm cohorts, not measured farm data — never treat it as reported biomas |

## Claiming live

| Path | Source |
|---|---|
| `/api/alerts/summary` | Multi-engine composite (lice + disease + bloom + price) |
| `/api/anomaly/scores` | BarentsWatch lice + PyOD anomaly detection |
| `/api/bio-risk/snapshot` |  |
| `/api/biomass/outlook` | Smolt model + Fiskeridirektoratet + BarentsWatch |
| `/api/biomass/scenarios` | Smolt model + Fiskeridirektoratet + BarentsWatch |
| `/api/bloom/alerts` | Copernicus CMEMS chlorophyll-a |
| `/api/bloom/chlorophyll` | Copernicus CMEMS chlorophyll-a |
| `/api/bloom/risk` | Copernicus CMEMS chlorophyll-a |
| `/api/chile/disease-history` | Sernapesca disease surveillance reports + WOAH notifications |
| `/api/chile/export-history` | Sernapesca export statistics + Chile customs (Aduana) |
| `/api/chile/farms` | Sernapesca aquaculture authority |
| `/api/chile/global-supply` | Sernapesca aquaculture authority |
| `/api/climate/heatwave-risk` | MET.no Frost + OceanForecast (Hobday et al. 2016) |
| `/api/compliance/asc/checklist` | ASC Farm Standard v1.0 specification |
| `/api/disease/alerts` | Mattilsynet + WOAH + Sernapesca |
| `/api/disease/by-company` | Mattilsynet + WOAH + Sernapesca |
| `/api/disease/norway` | Mattilsynet + WOAH + Sernapesca |
| `/api/disease/norway/geo` | Mattilsynet + WOAH + Sernapesca |
| `/api/efficacy/benchmarks` | Crowdsourced treatment outcomes (anonymized) |
| `/api/efficacy/by-region` | Crowdsourced outcomes, anonymized to PA level |
| `/api/efficacy/by-season` | Crowdsourced outcomes, seasonal analysis |
| `/api/efficacy/explore` | Crowdsourced treatment outcomes (anonymized to PA level) |
| `/api/efficacy/learned-profiles` | Crowdsourced treatment outcomes (learned profiles) |
| `/api/feed-cost/official-history` | Fiskeridirektoratet lonnsomhetsundersokelse 2008-2024 |
| `/api/global/bloom-risk` | Norway BloomRiskAssessment DB + Copernicus CMEMS chlorophyll |
| `/api/global/disease-geo` | Mattilsynet + WOAH + Sernapesca disease notifications |
| `/api/global/farms` | Iceland / Scotland / Faroe / Canada farm registries |
| `/api/gnn/status` | Lice GNN (PyTorch Geometric) |
| `/api/market/eumofa/trade-summary` | EUMOFA + Eurostat trade data + SSB Norwegian exports |
| `/api/market/export-destinations` | SSB Table 08799 (Statistics Norway) |
| `/api/market/exports` | SSB export statistics (Statistics Norway) |
| `/api/market/futures-curve` | SSB Table 03024 (Statistics Norway) |
| `/api/market/spot-price` | SSB Table 03024 (Statistics Norway) |
| `/api/market/ssb-price-history` | SSB Table 03024 (Statistics Norway) |
| `/api/ml/chronos/model-comparison` | Amazon Chronos zero-shot |
| `/api/ml/chronos/price-forecast` | Amazon Chronos zero-shot |
| `/api/ml/ensemble/price-forecast` | Ensemble: Chronos |
| `/api/ocean/forecast` | MET.no OceanForecast 2.0 |
| `/api/production/summary` | Fiskeridirektoratet production statistics (open data) |
| `/api/regulatory/traffic-light/current` | BarentsWatch lice data + PA classification rules |
| `/api/scotland/water-quality` | SEPA Time Series API |
| `/api/supply-forecast` | Smolt model + Fiskeridirektoratet + BarentsWatch |
| `/api/supply/cohort-timeline` | Smolt model + Fiskeridirektoratet + BarentsWatch |
| `/api/supply/smolt-forecast` | Smolt model + Fiskeridirektoratet + BarentsWatch |
| `/api/supply/summary` | Smolt model + Fiskeridirektoratet + BarentsWatch |
| `/api/traceability/dashboard` | Internal compliance database |
| `/api/traceability/eudr-status` | Internal compliance database |
| `/api/treatment/cost-comparison` | Treatment constants (Overton 2019) + cost model |

## `no_provenance` backlog by payload shape

| Payload | Routes | Fix path |
|---|---|---|
| `dict` | 20 | additive `data_provenance` key |
| `list` | 29 | needs a coordinated contract change (frontend auto-unwrap, e2e api-contracts, visual baselines) |
| other | 1 | inspect individually |


## Known limitations & backlog

- **Timeouts** are the bulk of `error`: they are network-bound upstreams
  (CMEMS/DFO/DNS-blocked hosts on this box), not necessarily broken in
  production. Re-run where the upstreams are reachable.
- **`no_provenance`** routes return data with no provenance envelope at all;
  each needs an audit against AGENTS.md rule 3 (source + freshness on every
  number shown to users).
- **HTTP 503 is used honestly** by model-backed routes (`torch_geometric not
  installed`, TFT weights missing) — degraded, not a bug.
- Parametrised routes (path parameters) are not probed; add fixtures before
  trusting coverage.


## Rule-3 provenance register + ratchet (added in the commercial hardening)

The provenance sweep is now enforced rather than remembered. `core/provenance_register.py`
holds the **formal exempt register** (prefix → category + written reason) and
`docs/provenance_baseline.json` freezes the non-exempt `/api` GET route inventory.

Current honest state (regenerate with `python scripts/provenance_ratchet.py`):

```
238 /api GET routes: 31 exempt, 207 baselined, 0 unregistered
```

### Exempt register (nothing here returns measured data)

| Prefix | Category | Reason |
|---|---|---|
| `/api/health` | infrastructure | liveness probe; returns no data |
| `/api/openapi.json` | infrastructure | schema document |
| `/api/auth/` | auth_and_billing | identity/session plumbing |
| `/api/billing/` | auth_and_billing | catalog and subscription state, not measured data |
| `/api/keys` | auth_and_billing | API-key management |
| `/api/webhooks` | auth_and_billing | webhook configuration |
| `/api/entitlements` | catalogue_and_meta | plan catalogue (prices/quotas), not data |
| `/api/tiers` | catalogue_and_meta | plan catalogue |
| `/api/disclaimer` | catalogue_and_meta | static legal text |
| `/api/meta/` | catalogue_and_meta | build/version metadata |
| `/api/legal/` | catalogue_and_meta | licence register and policy text |
| `/api/accuracy/method` | publication_metadata | artifact contract, not a measurement |
| `/api/accuracy/artifacts` | publication_metadata | artifact metadata (the artifact itself is the provenance) |
| `/api/indices/methodology` | publication_metadata | published method document |
| `/api/data-freshness` | operational | freshness metadata about other routes |
| `/api/admin/` | admin | admin operational endpoints (auth-gated) |
| `/api/cache/` | admin | cache administration (auth-gated) |
| `/api/audit` | admin | audit log (auth-gated, operational) |

### The ratchet (CI-enforceable)

```bash
python scripts/provenance_ratchet.py            # verify; exit 1 on drift
python scripts/provenance_ratchet.py --update   # freeze after a provenance decision
python -m pytest tests/test_provenance_ratchet.py -q
```

A new data route must **either** carry provenance via the reusable decorator:

```python
from core.market.provenance_envelope import with_provenance

@router.get("/api/example")
@cached(ttl=600)
@with_provenance("source", degraded_reason="it is a model estimate, not a measurement")
async def example(): ...
```

**or** be added to `EXEMPT` with a written reason. A route in neither fails the
test — so a new data route cannot ship without a deliberate provenance decision.

### Routes given provenance in this step (5)

| Route | Envelope |
|---|---|
| `/api/analytics/yoy-comparison` | degraded — computed from the ingested series; a YoY gap means the prior period is absent, not zero |
| `/api/treatment/efficacy-by-method` | degraded — aggregated from producer-reported outcomes, not a controlled trial |
| `/api/feed-supply-chain/eudr-risk` | degraded — model-based composition over published reports, not a live due-diligence feed |
| `/api/futures/basis` | engine provenance preserved (SSB synthesis, `is_live: false`) |
| `/api/futures/term-structure` | engine provenance preserved (SSB synthesis, `is_live: false`) |

The last two demonstrate the decorator's safe nesting: an engine that already sets
`data_provenance` wins, so the envelope never overwrites a more specific truth.

### Ratchet fix — anchored to the frozen contract (post-Step-8 hardening)

The full suite surfaced a real defect in the ratchet itself: it read the **live
FastAPI app**, so other test modules that register throwaway routes for error-path
coverage (`/api/test-not-found`, `/api/test-upstream-failure`) made the inventory
order-dependent and produced two false failures in the full run only.

`core/provenance_register.data_routes()` now reads **`docs/openapi.frozen.json`** —
the declared surface, and the same artifact the OpenAPI contract test uses. The
inventory is therefore deterministic and re-frozen deliberately:

```
237 /api GET routes: 33 exempt, 204 baselined, 0 unregistered
```

Tests: `tests/test_provenance_ratchet.py` 13 passed standalone; the mixed-context
re-run is noted in the session log (the route-liveness contract test performs live
socket probes and is slow/unavailable in a sandbox without network).



The register and baseline prove **a decision was recorded**, not that every one of
the 207 routes actually carries provenance today. The runtime measurement of that
remains `scripts/probe_liveness.py` (payload-shape classification). The ratchet
prevents silent erosion; the probe reports the live residue.

