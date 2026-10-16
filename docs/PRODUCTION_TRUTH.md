# Production truth

**Make the gaps detectable, then fix them.** AGENTS.md listed operational gaps that
stayed invisible until something broke. Each is now a check with a verdict, run by
`python scripts/verify_production_truth.py` (exit 1 on a critical failure, so a
deploy gate can block a deployment that would silently degrade the product).

## The truth gaps and their current state

| Gap | Was | Now |
|---|---|---|
| **Agents never ran in production** | production image ran `gunicorn core.api:app` only, so all 12 agents (ingest, forecasts, …) never executed — and, until WS-2, no agent published the indices at all | `docker-compose.prod.yml` declares a separate `agents` service running `python main.py --agents-only`; the verifier fails if that service is absent |
| **Model artifacts absent in CI/prod** | weights live in the gitignored `data/models/` | the verifier reports presence/absence honestly; compose mounts a `models` volume. Absence is *disclosed* (every forecast is the seasonal-naive fallback) rather than hidden |
| **DB vs migrations drift** | never checked | verifier compares `alembic_version` to the code head and fails on mismatch. **It immediately found this repo's dev DB sitting at `None`** (empty `alembic_version` from a `create_all`-built file); `tests/conftest.py` now stamps head for dev/test DBs while real deployments keep failing if they are behind |
| **PG/TimescaleDB unverified** | assumed | production must not be SQLite (rejected by `config/settings.py` *and* by the verifier); `docker/init-timescale.sql` creates the extension and the verifier reports the hypertable count as an explicit number |
| **Freshness unknowable** | no visibility | `core/market/freshness_monitor.py` + `GET /api/data-freshness`: per-source latest observation, staleness vs expected cadence, `unknown` when not measurable, and `synthetic_only` when a table holds only demo/seed rows |
| **Lice lineage unverifiable** (WS-1) | `lice_records` had no `source` column: demo seeds and reported rows were indistinguishable, so AI-LPI could never claim live | Alembic 019 + `core/source_lineage.py`: every row is `barentswatch` (ingest), `demo_seed` (seed) or `unverified` (pre-WS-1, never real). The freshness entry reports `verified_rows` / `unverified_rows` / `no_verified_rows`; the verifier fails (critical) when the column is missing, warns when it is nullable or has no default (a reconciled column 019 never repaired) and warns when a source holds no verified row |

## Production topology (`docker-compose.prod.yml`)

```
db      timescale/timescaledb:latest-pg16   (healthcheck: pg_isready)
api     gunicorn core.api:app -k uvicorn.workers.UvicornWorker
agents  python main.py --agents-only        ← the fix
web     frontend (Next.js)
volumes pgdata, artifacts (published accuracy artifacts), models (weights)
```

`FISHINTEL_ENV=production` + `POSTGRES_PASSWORD` + `FISHINTEL_JWT_SECRET` are
required (`:?` guards), so a misconfigured deploy fails at `up`, not at 3am.

## Running it

```bash
python scripts/verify_production_truth.py            # human-readable
python scripts/verify_production_truth.py --json     # machine-readable (CI gate)
python scripts/verify_production_truth.py --no-freshness
```

## Honest output (this repository, this environment)

```
[OK  ] compose_service_agents: declared
[OK  ] agents_entrypoint: uses `python main.py --agents-only`
[OK  ] alembic_head: at head 019
[OK  ] lice_source_column: lice_records.source present, NOT NULL with default (WS-1)
[OK  ] model_artifacts: 4 file(s) in data/models
[OK  ] accuracy_artifacts: 1 published artifact(s)
[OK  ] index_publication_current_week: 2026-W42 published for AI-STI, AI-LPI (method 1.0.0)
[OK  ] freshness_critical_unknown: all critical sources measurable
[WARN] freshness_synthetic_only: sources backed only by synthetic rows: ssb_weekly_prices
[WARN] freshness_no_verified_rows: sources holding no row with a verified source
       (synthetic or unverified only): lice_records
[INFO] freshness_counts: fresh=2 stale=0 dead=4 unknown=6
```

Two warnings, both true and actionable — not suppressed, not dressed up. The
second one is the honest state of a bulk-loaded development database after WS-1:
186,139 lice rows, of which 1,040 are provably demo and 185,099 have no row-level
proof of origin. Nothing was backfilled as real; they become `barentswatch` only
when a real ingest overwrites them.

## Lice lineage (WS-1)

`lice_records.source` is the only reliable way to tell a reported observation from
a seed: the demo seed's locality numbers (10001–10022) sit inside the real
BarentsWatch numbering range (the lowest real locality on the dev DB is 10029), so
locality must never be used as the test. The vocabulary lives in
`core/source_lineage.py` and every consumer projects it:

| Value | Written by | Counts as |
|---|---|---|
| `barentswatch` | `agents/data_ingest.py` (both upsert branches; the historical backfill reuses it) | verified |
| `demo_seed` | `core/demo_seed.py` | synthetic |
| `unverified` | server default; every pre-WS-1 row | unverified — never real |

A lice-derived value is **live** only when every row it used is verified, every
production area contributed rows without a fetch failure, the newest observation
week is the current or previous ISO week, and the newest row was fetched within
the weekly cadence — checked per production area as well as nationally, so one
stale area degrades the national view. Cached payloads re-evaluate this against
the current time on every hit. The quota tracker publishes that summary as `lineage`
on `/api/analytics/lice-quota/*` and `/api/analytics/lice-emission/*`, AI-LPI reads
it, and `/api/data-freshness` counts the whole table. A database that never ran
migration 019 (typically an empty `alembic_version`, where the chain aborts at 001)
fails the verifier's `lice_source_column` check; recover with `alembic stamp 018`
then `alembic upgrade head` — never stamp head directly.

## Still open (tracked, not claimed as done)

- **Hypertable conversion** is deliberately *not* automated: it needs a real time
  column and a correct chunk interval per table, and a wrong conversion silently
  degrades plans. The verifier reports the count so "not yet converted" is visible.
- **Model weights are still not shipped as a release artifact** — compose mounts a
  volume, but there is no build step that populates it yet.
- **Scheduler assertion (done in WS-2):** `index_publication_current_week` reads the
  store and warns when the current ISO week is not published; the `index_publisher`
  agent publishes it once per week. Paging a human on that warning is WS-9.
- **Lice ingest health** (WS-16): the dev box's last real lice rows arrived
  2026-04-07 and the 2026-10-12 tick inserted 0 rows for W42, so `lice_records` is
  `dead` and holds no verified row. WS-1 makes that visible; it does not fix the
  ingest.
- **Other lice consumers** (WS-14) still stamp live provenance without a lineage
  input (lice summary, decision engine, analytics, farm, notification, bloom, ASC,
  regulatory and supply routes). `core/source_lineage.py` is the helper they must
  call; converting them is a separate workstream.
