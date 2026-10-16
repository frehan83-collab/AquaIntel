# Route Liveness Report

> Generated 2026-10-16 14:52 UTC by `scripts/probe_liveness.py`.
> Parameterless GET routes only. The weakest nested provenance governs a
> route's headline state, so the report is conservative.

## Summary

| State | Routes |
|---|---|
| `no_provenance` | 65 |
| `live` | 53 |
| `error` | 52 |
| `degraded` | 30 |
| `auth_401` | 11 |
| `http_422` | 6 |
| `http_5xx` | 2 |

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
| `/api/china/demand` | degraded | 200 | GACC/Comtrade estimates (SSB 08799 unavailable) | live Norwegian export series unavailable — using curated estimates |
| `/api/china/demand-impact` | degraded | 200 | GACC/Comtrade estimates (SSB 08799 unavailable) | live Norwegian export series unavailable — using curated estimates |
| `/api/china/demand-signals` | degraded | 200 | GACC/Comtrade estimates (SSB 08799 unavailable) | live Norwegian export series unavailable — using curated estimates |
| `/api/feed-supply-chain/summary` | degraded | 200 | BioMar/Skretting sustainability reports + IFFO + EUDR Reg 2023/1115 | model-based composition with approximate commodity prices — not a live feed |
| `/api/global/lice` | degraded | 200 | BarentsWatch lice (Norway) + DFO Canada | no country monitor returned features — this layer is empty |
| `/api/integrations/fishtalk/status` | degraded | 200 | Fishtalk 5 API | FISHTALK_API_KEY not configured |
| `/api/investor/event-impact/feed-shock` | degraded | 200 | Event impact model (scenario simulation) | modelled impact of a hypothetical event — a scenario estimate, not an observed market move |
| `/api/investor/event-impact/isa` | degraded | 200 | Event impact model (scenario simulation) | modelled impact of a hypothetical event — a scenario estimate, not an observed market move |
| `/api/investor/event-impact/traffic-light` | degraded | 200 | Event impact model (scenario simulation) | modelled impact of a hypothetical event — a scenario estimate, not an observed market move |
| `/api/lice/summary` | degraded | 200 | BarentsWatch Fishhealth API | 27 weeks stale |
| `/api/market/eumofa/salmon-prices` | degraded | 200 | SSB Table 03024 + EU premium model | EUMOFA API unavailable, using SSB Norway price with EU market premiums |
| `/api/market/eumofa/trade-flows` | degraded | 200 | SSB exports + EU import share model | EUMOFA API unavailable, using SSB export stats with EU share estimates |
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
| `/api/esg/scores` | error | None |  | timeout |
| `/api/esg/summary` | error | None |  | timeout |
| `/api/farms/biomass/national` | error | None |  | timeout |
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
| `/api/futures/basis` | error | None |  | timeout |
| `/api/futures/forward-curve` | error | None |  | timeout |
| `/api/futures/settlement` | error | None |  | timeout |
| `/api/futures/term-structure` | error | None |  | timeout |
| `/api/global-supply` | error | None |  | timeout |
| `/api/health` | error | None |  | timeout |
| `/api/iceland/exports` | error | None |  | timeout |
| `/api/iceland/farms` | error | None |  | timeout |
| `/api/iceland/production` | error | None |  | timeout |
| `/api/iceland/snapshot` | error | None |  | timeout |
| `/api/intelligence/summary` | error | None |  | timeout |
| `/api/leaders/pa-leaderboard` | error | None |  | timeout |
| `/api/leaders/top100` | error | None |  | timeout |
| `/api/leaders/top30` | error | None |  | timeout |
| `/api/macro/snapshot` | error | None |  | timeout |
| `/api/market/biomass` | error | None |  | timeout |
| `/api/market/equity-prices` | error | None |  | timeout |
| `/api/notifications/alerts/rules/evaluate` | error | None |  | timeout |
| `/api/satellite/status` | error | None |  | timeout |
| `/api/scenarios/list` | error | None |  | timeout |
| `/api/scotland/farms` | error | None |  | timeout |
| `/api/scotland/snapshot` | error | None |  | timeout |
| `/api/scotland/water-quality` | error | None |  | timeout |
| `/api/farms/portfolio` | http_422 | 422 |  |  |
| `/api/harvest/simulate` | http_422 | 422 |  |  |
| `/api/ocean/norkyst/current` | http_422 | 422 |  |  |
| `/api/ocean/temperature` | http_422 | 422 |  |  |
| `/api/satellite/pace/chlorophyll` | http_422 | 422 |  |  |
| `/api/satellite/pace/hab-risk` | http_422 | 422 |  |  |
| `/api/gnn/predict-all` | http_5xx | 503 |  |  |
| `/api/market/price-outlook/explain` | http_5xx | 503 |  |  |
| `/api/ais/harvest-signals` | no_provenance | 200 |  |  |
| `/api/ais/tracks` | no_provenance | 200 |  |  |
| `/api/ais/treatment-signals` | no_provenance | 200 |  |  |
| `/api/alerts` | no_provenance | 200 |  |  |
| `/api/alerts/preferences` | no_provenance | 200 |  |  |
| `/api/analytics/yoy-comparison` | no_provenance | 200 |  |  |
| `/api/anomaly/alerts` | no_provenance | 200 |  |  |
| `/api/auth/me` | no_provenance | 200 |  |  |
| `/api/auth/tiers` | no_provenance | 200 |  |  |
| `/api/chat/history` | no_provenance | 200 |  |  |
| `/api/chile/signals` | no_provenance | 200 |  |  |
| `/api/climate/projections` | no_provenance | 200 |  |  |
| `/api/compliance/deadlines` | no_provenance | 200 |  |  |
| `/api/contracts/hedge-signals` | no_provenance | 200 |  |  |
| `/api/disclaimer` | no_provenance | 200 |  |  |
| `/api/exposure/sites` | no_provenance | 200 |  |  |
| `/api/farm-graph/cascades` | no_provenance | 200 |  |  |
| `/api/farm-graph/clusters` | no_provenance | 200 |  |  |
| `/api/farm-graph/company-exposure` | no_provenance | 200 |  |  |
| `/api/farm-graph/map-data` | no_provenance | 200 |  |  |
| `/api/farm-graph/summary` | no_provenance | 200 |  |  |
| `/api/farms/offshore` | no_provenance | 200 |  |  |
| `/api/federated/privacy-info` | no_provenance | 200 |  |  |
| `/api/feed-cost/official-history` | no_provenance | 200 |  |  |
| `/api/feed-supply-chain/eudr-risk` | no_provenance | 200 |  |  |
| `/api/feed-supply-chain/scenarios` | no_provenance | 200 |  |  |
| `/api/intelligence/health` | no_provenance | 200 |  |  |
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
| `/api/ras/summary` | no_provenance | 200 |  |  |
| `/api/ras/timeline` | no_provenance | 200 |  |  |
| `/api/rate-limit-info` | no_provenance | 200 |  |  |
| `/api/regime/alerts` | no_provenance | 200 |  |  |
| `/api/regime/company-risk` | no_provenance | 200 |  |  |
| `/api/regime/states` | no_provenance | 200 |  |  |
| `/api/regulatory/traffic-light/all-scenarios` | no_provenance | 200 |  |  |
| `/api/regulatory/traffic-light/simulate` | no_provenance | 200 |  |  |
| `/api/satellite/anomalies` | no_provenance | 200 |  |  |
| `/api/satellite/products` | no_provenance | 200 |  |  |
| `/api/self-improvement/proposals` | no_provenance | 200 |  |  |
| `/api/sentiment/articles` | no_provenance | 200 |  |  |
| `/api/sentiment/signals` | no_provenance | 200 |  |  |
| `/api/signals` | no_provenance | 200 |  |  |
| `/api/tiers` | no_provenance | 200 |  |  |
| `/api/traceability/certificates` | no_provenance | 200 |  |  |
| `/api/treatment/efficacy-by-method` | no_provenance | 200 |  |  |
| `/api/twin/status` | no_provenance | 200 |  |  |
| `/api/webhooks/events` | no_provenance | 200 |  |  |

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
| `/api/disease/treatments` | Mattilsynet + WOAH + Sernapesca |
| `/api/efficacy/benchmarks` | Crowdsourced treatment outcomes (anonymized) |
| `/api/efficacy/by-region` | Crowdsourced outcomes, anonymized to PA level |
| `/api/efficacy/by-season` | Crowdsourced outcomes, seasonal analysis |
| `/api/efficacy/explore` | Crowdsourced treatment outcomes (anonymized to PA level) |
| `/api/efficacy/learned-profiles` | Crowdsourced treatment outcomes (learned profiles) |
| `/api/farms/offshore/lice-comparison` | BarentsWatch lice data + offshore classification |
| `/api/faroe/farms` | Hagstova Føroya |
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
| `/api/market/ssb-seasonal` | SSB Table 03024 (Statistics Norway) |
| `/api/ml/chronos/model-comparison` | Amazon Chronos zero-shot |
| `/api/ml/chronos/price-forecast` | Amazon Chronos zero-shot |
| `/api/ml/ensemble/price-forecast` | Ensemble: Chronos |
| `/api/notifications/alerts` | BarentsWatch + SSB + MET.no |
| `/api/notifications/history` | ThresholdAlertEngine + AlertEngine |
| `/api/ocean/forecast` | MET.no OceanForecast 2.0 |
| `/api/production/summary` | Fiskeridirektoratet production statistics (open data) |
| `/api/regulatory/traffic-light/current` | BarentsWatch lice data + PA classification rules |
| `/api/sentiment/poll` | News feeds (22 new articles) |
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
| `dict` | 30 | additive `data_provenance` key |
| `list` | 34 | needs a coordinated contract change (frontend auto-unwrap, e2e api-contracts, visual baselines) |
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

