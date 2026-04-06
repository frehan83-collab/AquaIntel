# OpenClaw — Lice-Impact Arbitrage Bot

A production-grade multi-agent system that monitors Norwegian salmon farm lice levels and generates conditional trading signals for MOWI, SALM (SalMar), and LSG (Lerøy) equities on Oslo Børs.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    OpenClaw Orchestrator                      │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ Data Ingest  │→│ Exposure     │→│ Correlation Engine  │ │
│  │ Agent (15m)  │  │ Mapper (1h)  │  │ (15m)              │ │
│  └─────────────┘  └──────────────┘  └─────────┬───────────┘ │
│                                                │             │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────▼───────────┐ │
│  │ Compliance   │  │ Execution    │←│ Signal Generator    │ │
│  │ Agent (1h)   │  │ Agent (30s)  │  │ (15m)              │ │
│  └─────────────┘  └──────┬───────┘  └─────────────────────┘ │
│                          │                                   │
│              ┌───────────▼───────────┐                       │
│              │  Paper / Live Broker  │                       │
│              └───────────────────────┘                       │
└──────────────────────────────────────────────────────────────┘
         │                              │
    ┌────▼────┐                   ┌─────▼─────┐
    │ FastAPI │                   │ Streamlit  │
    │  REST   │                   │ Dashboard  │
    └─────────┘                   └────────────┘
```

## Quick Start

### 1. Prerequisites
- Python 3.11+
- BarentsWatch API credentials

### 2. Get BarentsWatch API Access
1. Go to https://www.barentswatch.no/minside/
2. Log in with ID-porten (BankID/MinID)
3. Navigate to "Mine klienter" → "Opprett ny klient"
4. Select scope: `api` (for fishhealth access)
5. Copy the Client ID and Client Secret

### 3. Setup

```bash
# Clone and install
cd OpenClaw
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your BarentsWatch credentials

# Initialize database
python -c "from core.models import init_db; init_db()"
```

### 4. Run

```bash
# Full system (agents + API)
python main.py

# API only
python main.py --api-only

# Dashboard only
streamlit run dashboard/app.py

# Run backtest
python scripts/run_backtest.py
```

### 5. Docker

```bash
cp .env.example .env
# Edit .env
docker-compose up -d
```

- API: http://localhost:8000
- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs

## How It Works

### Data Pipeline
1. **Data Ingest Agent** polls BarentsWatch Fishhealth API every 15 minutes
2. Fetches per-locality lice counts, sea temperatures, and disease reports
3. **Exposure Mapper** links localities to companies (MOWI, SALM, LSG)

### Signal Generation
4. **Correlation Engine** computes weighted impact scores:
   - Lice severity (avg adult female lice vs 0.5 threshold)
   - Breadth (% of sites above regulatory limit)
   - Trend (acceleration of lice levels)
   - Estimated harvest reduction risk
5. **Signal Generator** converts scores to SHORT/LONG signals

### Execution (Consent-Required)
6. Signals appear on dashboard as **pending**
7. User reviews rationale and clicks **Confirm** or **Reject**
8. Only confirmed signals are executed (paper trading by default)
9. Full audit trail maintained

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/signals` | GET | List trading signals |
| `/api/signals/confirm` | POST | Confirm a signal for execution |
| `/api/signals/reject` | POST | Reject a signal |
| `/api/lice/summary` | GET | Latest lice data summary |
| `/api/orders` | GET | Order history |
| `/api/audit` | GET | Audit trail |
| `/api/disclaimer` | GET | Legal disclaimer |

## Backtesting

Run historical backtests with Monte Carlo simulation:

```bash
python scripts/run_backtest.py
```

Or use the dashboard Backtest page for interactive analysis.

## Monetization

- **Performance Fee**: 20% of profits (tracked in `performance_fees` table)
- **Premium Signal Tier**: Real-time alerts, SMS/email notifications
- **Free Tier**: Delayed signals, dashboard access only

## Compliance

- **No auto-execution**: Every trade requires explicit user consent
- **GDPR**: No personal data stored
- **NLOD**: BarentsWatch data properly attributed
- **Audit Trail**: Immutable log of all actions
- **Disclaimer**: Clear regulatory warnings

## Project Structure

```
OpenClaw/
├── agents/                 # Multi-agent modules
│   ├── base.py            # Base agent class
│   ├── data_ingest.py     # BarentsWatch polling
│   ├── exposure_mapper.py # Company-locality mapping
│   ├── correlation_engine.py  # Impact scoring
│   └── signal_generator.py    # Trading signals
├── backtest/
│   └── engine.py          # Backtesting + Monte Carlo
├── compliance/
│   └── compliance_agent.py # Audit, fees, GDPR
├── config/
│   ├── settings.py        # Pydantic settings
│   └── logging_config.py  # Structured logging
├── core/
│   ├── api.py             # FastAPI REST endpoints
│   ├── barentswatch.py    # BarentsWatch OAuth2 client
│   └── models.py          # SQLAlchemy ORM models
├── dashboard/
│   └── app.py             # Streamlit dashboard
├── execution/
│   ├── execution_agent.py # Order management
│   └── paper_broker.py    # Paper trading simulator
├── openclaw/
│   └── manifest.yml       # OpenClaw deployment config
├── scripts/
│   └── run_backtest.py    # Standalone backtest runner
├── tests/
│   ├── test_backtest.py
│   └── test_paper_broker.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── main.py                # Orchestrator entry point
├── requirements.txt
└── README.md
```

## License

Proprietary. Data from BarentsWatch under NLOD 2.0.
