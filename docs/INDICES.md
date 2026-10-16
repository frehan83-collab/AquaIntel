# Named indices — AI-STI & AI-LPI, and Bio→Price Weekly

**Published method version: `1.0.0`** (`core.market.indices.INDEX_METHOD_VERSION`).
Machine-readable copy: `GET /api/indices/methodology`.

## Why these exist

Two named, versioned, publicly citable indices turn the platform's honesty layer
into a sales asset: a buyer can see the method, the weights, the source of every
component, and whether a source was degraded — before trusting a number. They are
also the *entry product*: the free Insight plan includes both.

| Index | Code | Question | Direction |
|---|---|---|---|
| AquaIntel Salmon Transmission Index | `AI-STI` | How much supply tension is likely to transmit into salmon prices? | higher = more upward price pressure |
| AquaIntel Lice Pressure Index | `AI-LPI` | How intense is national lice treatment pressure? | higher = more lice-driven risk and cost |

Both are 0–100, banded `minimal < low < moderate < elevated < severe`
(thresholds 20 / 40 / 60 / 80).

## How a value is computed

A **weighted mean of component scores**, with weights **renormalised over the
components whose source was actually available**. Anything dropped is named in
`components_missing` and forces `provenance.is_live = false` with a
`fallback_reason` — a degraded index is never presented as live (rule 1).

If **every** component is unavailable the index returns `value: null` and
`band: null` rather than a fabricated number.

### AI-STI v1.0

| Component | Weight | Scoring | Source |
|---|---|---|---|
| `biomass_momentum` | 0.40 | `clamp(50 − 5 × growth_pct, 0, 100)` — falling standing biomass tightens supply | Fiskeridir biomass (SSB) |
| `harvest_pressure` | 0.35 | `clamp(50 − 5 × growth_pct, 0, 100)` — near-term harvest volume loosens supply | Fiskeridir biomass (SSB) |
| `quota_pressure` | 0.25 | `clamp((national_utilisation_pct − 50) × 1.6, 0, 100)` — quota saturation forces future biomass cuts | `lice_quota_tracker` (lice emission quota framework) |

Momentum prefers **year-over-year**; when a year-back period is missing the
previous available period is used and `raw.basis` reports which was used.

### AI-LPI v1.0

| Component | Weight | Scoring | Source |
|---|---|---|---|
| `emission_pressure` | 0.55 | `clamp((national_utilisation_pct − 40) × 1.5, 0, 100)` | `lice_quota_tracker` |
| `quota_headroom` | 0.45 | `clamp(100 − national_utilisation_pct, 0, 100)` — little headroom left before mandatory cuts | `lice_quota_tracker` |

## Revision policy

A published value is **immutable** for a given `(index_code, week, version)`
(enforced by a unique constraint on `index_observations`). Changing a weight,
a scoring formula or a source **bumps the method version**; the history keeps both
versions so a series break is visible instead of silently restated.

## Bio→Price Weekly v1

`GET /api/indices/bio-price-weekly` — composes both indices with a supply panel
(standing biomass, harvest, change %) and a price panel (live spot, 6-month
forward slope) into one weekly digest with a `transmission.read` of
`elevated | balanced | loose | unknown`, an explicit `caveats` list, and a
provenance block. `publish_week()` computes **and** stores both index
observations (the weekly job), so history accumulates automatically.

Permalink `/indices#bio-price-weekly`. The read is deliberately described as a
descriptive read of leading indicators — **not** a causal claim and not advice.

## Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/indices` | public | Latest value of every index + method version |
| `GET /api/indices/ai-sti`, `/ai-lpi` | public | Stable permalink for one index |
| `GET /api/indices/{code}/history?limit=` | public | Versioned, stored history |
| `GET /api/indices/methodology` | public | The published method (this document, structured) |
| `GET /api/indices/bio-price-weekly` | public | The weekly digest |
| `POST /api/indices/publish` | **admin** | Compute + store both indices (weekly job) |

## Honest limitations (v1.0)

- **AI-LPI uses the emission-quota framework as a proxy** for treatment pressure;
  it is not a direct adult-female lice count series. A count series is planned for
  v1.1 (see `methodology()["planned_components"]`).
- **Feed cost is not yet a component** of AI-STI (v1.1).
- **Sea-temperature anomaly is not yet a component** of AI-LPI (v1.1).
- Momentum components are sensitive to reporting revisions in the upstream
  source; `raw.basis` and the `period` are always published so a reader can judge.
- The weekly digest is generated on request or by the weekly job; there is no
  scheduler assertion yet that it *was* published this week (tracked with the
  data-freshness dashboard work).
