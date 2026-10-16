# Production truth

**Make the gaps detectable, then fix them.** AGENTS.md listed operational gaps that
stayed invisible until something broke. Each is now a check with a verdict, run by
`python scripts/verify_production_truth.py` (exit 1 on a critical failure, so a
deploy gate can block a deployment that would silently degrade the product).

## The truth gaps and their current state

| Gap | Was | Now |
|---|---|---|
| **Agents never ran in production** | production image ran `gunicorn core.api:app` only, so all 12 agents (ingest, forecasts, index publication) never executed | `docker-compose.prod.yml` declares a separate `agents` service running `python main.py --agents-only`; the verifier fails if that service is absent |
| **Model artifacts absent in CI/prod** | weights live in the gitignored `data/models/` | the verifier reports presence/absence honestly; compose mounts a `models` volume. Absence is *disclosed* (every forecast is the seasonal-naive fallback) rather than hidden |
| **DB vs migrations drift** | never checked | verifier compares `alembic_version` to the code head and fails on mismatch. **It immediately found this repo's dev DB sitting at `None`** (empty `alembic_version` from a `create_all`-built file); `tests/conftest.py` now stamps head for dev/test DBs while real deployments keep failing if they are behind |
| **PG/TimescaleDB unverified** | assumed | production must not be SQLite (rejected by `config/settings.py` *and* by the verifier); `docker/init-timescale.sql` creates the extension and the verifier reports the hypertable count as an explicit number |
| **Freshness unknowable** | no visibility | `core/market/freshness_monitor.py` + `GET /api/data-freshness`: per-source latest observation, staleness vs expected cadence, `unknown` when not measurable, and `synthetic_only` when a table holds only demo/seed rows |

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
[OK  ] alembic_head: at head 017
[OK  ] model_artifacts: 4 file(s) in data/models
[WARN] accuracy_artifacts: no published accuracy artifact — /api/accuracy reports
       'not yet published' (run scripts/publish_accuracy.py where real data exists)
[WARN] freshness_synthetic_only: sources backed only by synthetic rows: ssb_weekly_prices
```

Two warnings, both true and actionable — not suppressed, not dressed up.

## Still open (tracked, not claimed as done)

- **Hypertable conversion** is deliberately *not* automated: it needs a real time
  column and a correct chunk interval per table, and a wrong conversion silently
  degrades plans. The verifier reports the count so "not yet converted" is visible.
- **Model weights are still not shipped as a release artifact** — compose mounts a
  volume, but there is no build step that populates it yet.
- **No scheduler assertion** that the weekly index publication actually ran; that
  belongs with the freshness alerting work.
