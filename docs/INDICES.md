# Named indices — AI-STI (AI-LPI v1.0 withdrawn), and Bio→Price Weekly

**Published method version: `2.0.0`** (`core.market.indices.INDEX_METHOD_VERSION`),
published 2026-10-17 (WS-19). Machine-readable copy: `GET /api/indices/methodology`.

## Why these exist

Named, versioned, publicly citable indices turn the platform's honesty layer
into a sales asset: a buyer can see the method, the weights, the source of every
component, and whether a source was degraded — before trusting a number. They are
also the *entry product*: the free Insight plan includes the published index.

| Index | Code | Question | Direction | Status |
|---|---|---|---|---|
| AquaIntel Salmon Transmission Index | `AI-STI` | How much supply tension is likely to transmit into salmon prices? | higher = more upward price pressure | published (`indices.PUBLISHED_INDICES`) |
| AquaIntel Lice Pressure Index | `AI-LPI` | How intense is national lice treatment pressure? | higher = more lice-driven risk and cost | **withdrawn** with method 2.0.0 (see below) |

AI-STI is 0–100, banded `minimal < low < moderate < elevated < severe`
(thresholds 20 / 40 / 60 / 80), and can reach both ends of the range: with both
momentum components at ±10 % year over year it reads 0 or 100
(`tests/test_indices.py::TestIndexGuard`).

## Method 2.0.0 — what changed and why (WS-19, 2026-10-17)

Method 1.0.0 read the lice-quota tracker's national utilisation in two places:
AI-STI's `quota_pressure` (weight 0.25) and both AI-LPI components. That
utilisation divides a lice count by constants labelled tonnes, for a tradable
quota regime that is still a proposal (Meld. St. 24 (2024–2025)) with no published
allocations: on the dev box it read **238,367 %** with all 13 areas over quota, which
alone drove AI-STI to 100 "severe". AI-LPI's `quota_headroom` was also inverted
(`100 − utilisation`, so more headroom raised the risk score), holding AI-LPI between
about 27 and 55 whatever the input.

- **AI-STI:** `quota_pressure` removed; `biomass_momentum` and `harvest_pressure`
  keep their 1.0.0 ratio (0.40 : 0.35), renormalised to 0.5333 / 0.4667.
- **AI-LPI v1.0: withdrawn.** The code still answers (`GET /api/indices/ai-lpi`,
  and it is listed on `GET /api/indices`) with `status: "withdrawn"`, `value: null`
  and the reason in `withdrawn` and in `provenance.fallback_reason`; it is never
  computed, never part of the publication set and never stored. A lice index may
  return only when rebuilt on observable facts (for example the biomass-weighted
  share of sites above the lice limit, weeks to the limit) on verified lice rows
  (WS-16), under a new method version.
- **No index reads the lice-quota tracker** (tested: a computation of every code,
  and a real publisher tick, call it zero times).
- **Stored 1.0.0 observations are superseded, not edited:** Alembic **020** adds
  `superseded_by`, `superseded_reason` and `superseded_at` to `index_observations`
  and marks every 1.0.0 row `superseded_by = '2.0.0'` with an index-specific reason;
  value, band, components and provenance are untouched and nothing is deleted.
  `GET /api/indices/{code}/history` returns every version with `superseded`,
  `superseded_by` and `superseded_reason`, and
  `methodology()["superseded_versions"]` lists the change. On the dev box the two
  2026-W42 rows (AI-STI 100, AI-LPI 55 claiming live — written by the test suite
  before the lineage guard, HANDOVER trap 16) are marked this way.

## How a value is computed

A **weighted mean of component scores**, with weights **renormalised over the
components whose source was actually available**. Anything dropped is named in
`components_missing` and forces `provenance.is_live = false` with a
`fallback_reason` — a degraded index is never presented as live (rule 1).

If **every** component is unavailable the index returns `value: null` and
`band: null` rather than a fabricated number.

### Lineage rule (WS-1)

Since method 2.0.0 **no published index reads `lice_records`**. The rule below
governed AI-LPI v1.0, still governs the lice-quota tracker's own payloads
(`/api/analytics/lice-quota/*`), and binds any rebuilt lice index. A component
built on `lice_records` carries the lineage of the rows **actually aggregated**,
not a check that a `source` column exists. It is live only when:

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

### AI-STI 2.0.0

| Component | Weight | Scoring | Source |
|---|---|---|---|
| `biomass_momentum` | 0.5333 | `clamp(50 − 5 × growth_pct, 0, 100)` — falling standing biomass tightens supply | Fiskeridir biomass (SSB) |
| `harvest_pressure` | 0.4667 | `clamp(50 − 5 × growth_pct, 0, 100)` — near-term harvest volume loosens supply | Fiskeridir biomass (SSB) |

Momentum prefers **year-over-year**; when a year-back period is missing the
previous available period is used and `raw.basis` reports which was used. Both
components come from one source: when it is unavailable AI-STI has **no value**
(`value: null`, never stored); when the biomass tracker falls back to its
historical-pattern estimate the value is **degraded** and says so. On the dev box
the tracker has no comparable prior period today, so AI-STI reads `null`.

### AI-LPI v1.0 — withdrawn (2.0.0)

v1.0 scored `emission_pressure` (0.55, `clamp((u − 40) × 1.5)`) and
`quota_headroom` (0.45, `clamp(100 − u)`) on the tracker's national utilisation
`u`. Both are withdrawn with it; see "Method 2.0.0" above.

## Revision policy

A published value is **immutable** for a given `(index_code, week, version)`
(enforced by a unique constraint on `index_observations`). Changing a weight,
a scoring formula or a source **bumps the method version**; the history keeps both
versions so a series break is visible instead of silently restated. Observations of
a withdrawn method are never edited or deleted: they are marked `superseded_by`
with the reason (Alembic 020) and stay in `GET /api/indices/{code}/history`.

## Bio→Price Weekly v1

`GET /api/indices/bio-price-weekly` — composes the published index (AI-STI) with a
supply panel (standing biomass, harvest, change %) and a price panel (live spot,
6-month forward slope) into one weekly digest with a `transmission.read` of
`elevated | balanced | loose | unknown`, an explicit `caveats` list, a `withdrawn`
block naming AI-LPI v1.0 and why, and a provenance block. No lice input enters the
read. `publish_week()` computes **and** stores the published index observations
(the weekly job), so history accumulates automatically.

Permalink `/indices#bio-price-weekly`. The read is deliberately described as a
descriptive read of leading indicators — **not** a causal claim and not advice.

## Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/indices` | public | Latest value of every index + method version; AI-LPI listed as `status: "withdrawn"` with no value |
| `GET /api/indices/ai-sti`, `/ai-lpi` | public | Stable permalink for one index (`/ai-lpi` answers the withdrawal) |
| `GET /api/indices/{code}/history?limit=` | public | Versioned, stored history, every version, with `superseded` / `superseded_by` / `superseded_reason` |
| `GET /api/indices/methodology` | public | The published method (this document, structured) |
| `GET /api/indices/bio-price-weekly` | public | The weekly digest |
| `POST /api/indices/publish` | **admin** | Compute + store this week's indices behind the same readiness gate as the agent; `force=true&reason=…` overrides the grace (never the null rule) and is audited |

## Publication schedule (WS-2)

Two paths write the weekly observation, and both go through the same gate:

- the `index_publisher` agent (started with the other agents by
  `python main.py --agents-only`, i.e. the production `agents` service) checks
  hourly; when a published index (`index_publication.INDEX_CODES` =
  `indices.PUBLISHED_INDICES`, AI-STI only since 2.0.0) is not yet stored for the
  current ISO week at the current method version it builds the digest (`build()`), gates it per index
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
disclosed, never hidden. A valid index is not withheld because another published
index's source is down. In practice an index is stored at the first hourly tick after Monday 00:00
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

## Honest limitations (2.0.0)

- **No lice index is published.** AI-LPI v1.0 is withdrawn; a rebuilt lice index
  needs observable facts and verified lice rows (WS-16) and a new method version
  (`methodology()["planned_components"]["next"]`).
- **AI-STI has two components from one source** (Fiskeridir biomass); when that
  source is unavailable it has no value, and when the tracker falls back to an
  estimate it is degraded.
- **Feed cost is not yet a component** of AI-STI (planned).
- Momentum components are sensitive to reporting revisions in the upstream
  source; `raw.basis` and the `period` are always published so a reader can judge.
- The weekly digest is published by the `index_publisher` agent; the scheduler
  assertion is the `publication` block on `GET /api/indices` and the verifier's
  `index_publication_current_week`. Paging a human when it is missing (webhook /
  notification) is WS-9.
- The lice-quota tracker's window is **every week of the latest year** and its
  utilisation compares a lice count with constants labelled tonnes (WS-15, superseded
  by WS-19): no index reads it any more; its own route still serves it.
- The freshness monitor (`/api/data-freshness`, source `index_observations`)
  counts only rows that are not superseded, so a withdrawn method's rows never make
  the store read "fresh"; the `publication` block on `GET /api/indices` (current
  method only) remains the authoritative weekly check.
