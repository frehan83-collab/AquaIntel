# FishIntel Deployment Guide

> **Repository:** [github.com/frehan83-collab/OpenClaw](https://github.com/frehan83-collab/OpenClaw) (private)

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.12+ | Backend API and agents |
| Node.js | 20+ | Next.js frontend |
| PostgreSQL | 16 (optional) | SQLite works for dev; TimescaleDB recommended for production |
| Docker | 24+ (optional) | For containerized deployment |

## Quick Start (Local Development)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/openclaw.git
cd openclaw

# 2. Install Python dependencies
python -m pip install -r requirements.txt

# 3. Create environment file
cp .env.example .env
# Edit .env — at minimum set FISHINTEL_JWT_SECRET

# 4. Generate a JWT secret
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Paste the output into .env as FISHINTEL_JWT_SECRET

# 5. Initialize the database
python -c "from core.models import init_db; init_db()"

# 6. Start the backend (port 8000)
python main.py

# 7. In a separate terminal — install and start the frontend
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:3000
```

## Docker Compose Deployment

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with production values

# 2. Start all services
docker compose up -d

# Services:
#   - db (TimescaleDB):  localhost:5432
#   - fishintel (API):   localhost:8000
#   - fishintel-agents:  background agents (no ports)
#   - frontend (Next.js): localhost:3000
#   - nginx (proxy):     localhost:80 / :443
```

The `docker-compose.yml` includes:
- **db** -- TimescaleDB (PostgreSQL 16 with time-series extensions)
- **fishintel** -- Python/FastAPI backend (API only)
- **fishintel-agents** -- the 12 background agents (data ingest every 15 min,
  exposure mapping, correlation, signal generation, prediction, backfill,
  execution, compliance, bloom, hedging, self-evolve, intelligence) plus
  sentiment polling. Runs `python main.py --agents-only` with graceful
  SIGTERM shutdown (`stop_grace_period: 60s`). Restarting the API does not
  interrupt data ingest.
- **frontend** -- Next.js production build
- **nginx** -- Reverse proxy for TLS termination

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///data/openclaw.db` | Database connection string |
| `FISHINTEL_JWT_SECRET` | **Yes** | `change-me-in-production` | JWT signing secret (64+ chars) |
| `FISHINTEL_CORS_ORIGINS` | No | `localhost:3000,localhost:8000` | Comma-separated allowed origins |
| `BARENTSWATCH_CLIENT_ID` | No | -- | BarentsWatch API client ID |
| `BARENTSWATCH_CLIENT_SECRET` | No | -- | BarentsWatch API client secret |
| `STRIPE_SECRET_KEY` | No | -- | Stripe secret key for billing |
| `STRIPE_PUBLISHABLE_KEY` | No | -- | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | No | -- | Stripe webhook signing secret |
| `COPERNICUS_USERNAME` | No | -- | CMEMS username (marine.copernicus.eu) |
| `COPERNICUS_PASSWORD` | No | -- | CMEMS password |
| `SENTINEL_HUB_CLIENT_ID` | No | -- | Sentinel Hub OAuth client ID |
| `SENTINEL_HUB_CLIENT_SECRET` | No | -- | Sentinel Hub OAuth client secret |
| `LLM_PROVIDER` | No | `openrouter` | LLM backend: `anthropic`, `openai`, `openrouter` |
| `ANTHROPIC_API_KEY` | No | -- | Anthropic API key (if LLM_PROVIDER=anthropic) |
| `POSTGRES_PASSWORD` | No | `openclaw-dev-password` | PostgreSQL password (Docker only) |
| `PUBLIC_API_URL` | No | `http://localhost:8000` | API URL injected into frontend build |

## Production Checklist

- [ ] **JWT Secret** -- Generate a cryptographically secure secret (64+ characters). Never use the default.
- [ ] **CORS Origins** -- Set `FISHINTEL_CORS_ORIGINS` to your actual domain(s). Remove localhost entries.
- [ ] **Database** -- Use PostgreSQL/TimescaleDB in production. Set `DATABASE_URL` accordingly.
- [ ] **Stripe Keys** -- Configure all Stripe variables if billing is enabled.
- [ ] **HTTPS** -- Configure TLS certificates in the nginx container or use a reverse proxy.
- [ ] **Secrets in environment** -- Never commit `.env` to version control. Use a secrets manager in CI/CD.
- [ ] **Rate Limiting** -- Default is 200 req/min globally, 10/min login, 5/min register. Adjust in `core/api.py` if needed.
- [ ] **Backups** -- Set up automated PostgreSQL backups (pg_dump or WAL archiving).
- [ ] **Monitoring** -- The `/api/health` endpoint returns service status for uptime checks.
