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

### Lineage rule (WS-1)

A component built on `lice_records` carries the lineage of the rows the quota
tracker **actually aggregated** (its latest-year window per production area), not
a check that a `source` column exists. The index is live only when:

- every used row has `source = 'barentswatch'` (a reported BarentsWatch observation);
- every production area contributed rows and none failed to fetch;
- the newest used **observation week** is the current or previous ISO week — per
  production area too, so one stale area degrades the national view;
- the newest used row was *fetched* within the 168 h cadence (a secondary gate:
  `fetched_at` is a write time that a re-ingest of an old week bumps).

Anything else lands in `lineage_notes` with counts (for example
"6997/6997 lice rows used carry no verified source … newest lice observation is 2026-W15, 27 weeks old … newest lice row was fetched 4604 h ago")
and forces `provenance.is_live = false`. Rows written before WS-1 are `unverified`
and can only become verified when a real ingest overwrites them — a demo-seeded
database and a bulk-loaded one are therefore both honestly degraded. The same
block is published as `lineage` on `/api/analytics/lice-quota/national`.

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
| `POST /api/indices/publish` | **admin** | Compute + store this week's indices behind the same readiness gate as the agent; `force=true&reason=…` overrides the grace (never the null rule) and is audited |

## Publication schedule (WS-2)

Two paths write the weekly observation, and both go through the same gate:

- the `index_publisher` agent (started with the other agents by
  `python main.py --agents-only`, i.e. the production `agents` service) checks
  hourly; when an index is not yet stored for the current ISO week at the current
  method version it builds the digest (`build()`), gates it per index
  (`index_publication.readiness()`) and stores the ready ones (`store_digest()`);
- `POST /api/indices/publish` (admin) calls `publish_week()`, which applies the
  same gate and answers 409 naming the withheld indices; `force=true` with a
  `reason` overrides the grace only, never the null rule, and writes an
  `index_publication_forced` audit row.

Restarts never double-publish (the unique constraint on `index_observations` is
the second line of defence; losing that race is reported as a duplicate).
`GET /api/indices` carries a `publication` block (latest stored week per index with
its value and provenance verdict, weeks behind, the ISO-week steps between
consecutive observations with `interval_ok` — `None` until there are two —
`skipped_weeks`, `degraded_current`, `within_grace`; the wall-clock `gaps_days` are
informational), and the production-truth verifier's `index_publication_current_week`
/ `index_publication_interval` warn with the week and the missing or skipped indices
(a wait inside the grace with last week stored is reported as info, not a fault).

**When in the week, and what gets stored.** An observation is immutable for its
(index, week, version), so the first computation of a week must not lock in an
artefact of missing inputs. Readiness is decided per index: an index with no value
is never stored (the store itself refuses it, whoever writes); within the first
72 h of the ISO week only a live value is stored; after that a degraded value (a
source still down) is stored with its provenance saying why — a source outage is
disclosed, never hidden. A valid AI-STI is not withheld because AI-LPI's source is
down. In practice an index is stored at the first hourly tick after Monday 00:00
UTC at which its value is live, or at the first tick on or after Thursday 00:00 UTC
if it has a (degraded) value by then; an index that has no value all week is never
stored and its week appears as a skipped week (never backfilled). The observation
therefore reflects upstream data published through the previous week. A skipped
week is two consecutive stored observations more than one ISO week apart; the
wall-clock gap between `as_of` stamps is reported for information only, because it
drifts with the hourly tick. A failed or incomplete publication is an error log, an
`index_publication` audit row and `last_failure` in the agent's health, and the
tick raises so the orchestrator counts it — never silence. Paging a human on that
state is WS-9.

## Honest limitations (v1.0)

- **AI-LPI uses the emission-quota framework as a proxy** for treatment pressure;
  it is not a direct adult-female lice count series. A count series is planned for
  v1.1 (see `methodology()["planned_components"]`).
- **Feed cost is not yet a component** of AI-STI (v1.1).
- **Sea-temperature anomaly is not yet a component** of AI-LPI (v1.1).
- Momentum components are sensitive to reporting revisions in the upstream
  source; `raw.basis` and the `period` are always published so a reader can judge.
- The weekly digest is published by the `index_publisher` agent; the scheduler
  assertion is the `publication` block on `GET /api/indices` and the verifier's
  `index_publication_current_week`. Paging a human when it is missing (webhook /
  notification) is WS-9.
- **AI-LPI claims live only through the lineage rule above.** On the development
  database it is degraded (0 of 6,997 rows in the window are verified and the
  newest row is six months old); on a fresh production database every row arrives
  as `barentswatch` and it goes live as soon as the window is complete and fresh.
- The tracker's window is **every week of the latest year** (it computes the latest
  week but does not use it) and its utilisation magnitude is implausible — both
  recorded as WS-15 in `docs/HANDOVER.md`; a correct live badge would not make that
  number credible.
