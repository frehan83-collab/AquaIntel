# Contributing to OpenClaw / FishIntel

Welcome to the OpenClaw Aquaculture Intelligence Platform. This guide covers
the architecture, conventions, and workflows you need to contribute effectively.

---

## Architecture Overview

### Backend (Python / FastAPI)

| Path | Purpose |
|------|---------|
| `core/api.py` | Main app, middleware, WebSocket endpoints (~1,314 lines) |
| `core/routers/` | 19 APIRouter modules (auth, billing, lice, disease, market, etc.) |
| `core/market/` | 53 market intelligence engines |
| `core/predictors/` | ML prediction models (event impact, compound scenarios) |
| `core/async_db.py` | AsyncSession factory (use this, not sync Session) |
| `core/schemas.py` | Pydantic v2 response models |
| `core/cache.py` | TTL-based engine output cache |
| `core/auth.py` | JWT auth with bcrypt + 4-tier access control |

### Frontend (Next.js / React / TypeScript)

| Path | Purpose |
|------|---------|
| `frontend/src/app/` | 52+ pages (App Router, `"use client"`) |
| `frontend/src/components/` | 21+ shared components |
| `frontend/src/lib/api.ts` | API client with 100+ methods |

### Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Full-stack local dev (API, frontend, Postgres, Redis) |
| `nginx.conf` | Reverse proxy: `/api/*` to FastAPI, `/*` to Next.js |
| `alembic/` | 6 database migrations (TimescaleDB/PostgreSQL) |
| `deploy.sh` | Production deployment script |

---

## Key Patterns

### Adding a new API endpoint

1. Create or find the appropriate router in `core/routers/`.
2. Use `async with get_async_session() as s:` for DB access.
3. Add DataProvenance to the response.
4. Register the router in `core/api.py` if it is new.
5. Add the endpoint to `frontend/src/lib/api.ts`.
6. Write a test in `tests/test_routers.py`.

```python
# Example router endpoint
@router.get("/my-endpoint", response_model=MyResponse)
async def get_my_data():
    async with get_async_session() as s:
        result = await s.execute(select(MyModel))
        rows = result.scalars().all()
    return MyResponse(
        data=rows,
        provenance=DataProvenance(source="internal_db", freshness="live"),
    )
```

### Adding a new frontend page

1. Create `frontend/src/app/{route}/page.tsx` with `"use client"` directive.
2. Use existing components: `GlassCard`, `KPICard`, `DataTable`, `DataQualityBadge`.
3. Fetch data via `api.methodName()` from `@/lib/api`.
4. Add the route to `Sidebar.tsx`.
5. Create `loading.tsx` in the same directory for Suspense boundary.

### Adding a new engine

1. Create `core/market/{engine_name}.py`.
2. Use `structlog` for logging.
3. Add `DataProvenance` to all outputs.
4. Use `@cached(ttl=300)` for expensive computations.
5. Create a singleton instance at the module bottom.

```python
# core/market/my_engine.py
import structlog
from core.cache import cached
from core.schemas import DataProvenance

logger = structlog.get_logger(__name__)

class MyEngine:
    """One-line description of what this engine does."""

    @cached(ttl=300)
    def analyze(self, region: str) -> dict:
        logger.info("my_engine.analyze", region=region)
        # ... computation ...
        return {
            "result": value,
            "provenance": DataProvenance(source="my_source", freshness="daily"),
        }

my_engine = MyEngine()
```

---

## Running Tests

```bash
python -m pytest tests/ -v                    # All tests
python -m pytest tests/test_routers.py -v     # Router tests only
python -m pytest tests/test_market_engines.py -v  # Engine tests
python -m pytest tests/ -k "test_name" -v     # Single test by name
```

---

## Code Style

- **Python**: type hints on all function signatures; docstrings on classes and engines.
- **TypeScript**: strict mode enabled; no `explicit-any` (suppress only where unavoidable).
- **Commits**: descriptive messages covering what changed and why.
- **Secrets**: never hardcode credentials; use `.env` and `config/`.
- **Provenance**: every engine must include `DataProvenance` in its output.
- **Async**: always use `get_async_session()` from `core/async_db.py`, never sync `Session`.

---

## Frozen Modules (do not extend)

The following engines are frozen and should not receive new features or refactoring:

| Module | Reason |
|--------|--------|
| `pairs_engine.py` | Niche pairs trading; low adoption |
| `regime_detector.py` | Unproven HMM accuracy |
| `satellite_engine.py` | No CDSE credentials available |
| `self_evolve.py` | Speculative AI self-improvement concept |

---

## Project Layout

```
OpenClaw/
  core/
    api.py              # FastAPI app + middleware
    routers/            # 19 router modules
    market/             # 53 intelligence engines
    predictors/         # ML models
    async_db.py         # Async database sessions
    schemas.py          # Pydantic v2 models
    cache.py            # TTL cache
    auth.py             # JWT + access control
  frontend/
    src/app/            # 52+ Next.js pages
    src/components/     # 21+ shared components
    src/lib/api.ts      # API client
  tests/                # pytest suite
  alembic/              # DB migrations
  agents/               # Autonomous agent definitions
  docker-compose.yml    # Local dev stack
  nginx.conf            # Reverse proxy config
```

---

## Getting Started

```bash
# 1. Clone and install
git clone <repo-url> && cd OpenClaw
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env   # Fill in DB credentials, API keys

# 3. Run migrations
alembic upgrade head

# 4. Start the backend
uvicorn core.api:app --reload --port 8000

# 5. Start the frontend
cd frontend && npm install && npm run dev
```

---

## Questions?

Open an issue or check existing docs in `docs/` and `ADVANCED_ROADMAP.md`.
