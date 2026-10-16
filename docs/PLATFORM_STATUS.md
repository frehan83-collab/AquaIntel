# AquaIntel Platform Status — Complete Briefing for AI Assistant Handoff
## Date: March 29, 2026

---

## WHAT THIS IS

AquaIntel is a full-stack salmon aquaculture market intelligence platform — the goal is to become the undisputed market leader, materially superior to Manolin/Watershed, Kontali, and every other competitor. It combines real-time biological data (sea lice, bloom, disease), market intelligence (prices, equities, commodities), predictive ML models, and autonomous agents into a single platform serving farmers, buyers, traders, and institutional investors.

## CODEBASE SIZE

- **27,272 lines Python** backend
- **11,936 lines TypeScript/React** frontend
- **103 REST API routes** (FastAPI)
- **27 market intelligence engines** (core/market/*.py)
- **9 autonomous agents** + base class (agents/*.py)
- **21 frontend pages** (18 in sidebar, 4 hidden but accessible)
- **20 database tables** (SQLAlchemy + SQLite)
- **CLAUDE.md** exists at project root for Claude Code context

## TECH STACK

- **Backend**: Python 3.14, FastAPI, SQLAlchemy, uvicorn, structlog, httpx, numpy
- **Frontend**: Next.js 14, React, TypeScript, TailwindCSS (custom ocean palette), Framer Motion
- **Database**: SQLite with WAL mode
- **APIs consumed**: BarentsWatch (OAuth2), SSB (Statistics Norway), FRED (St. Louis Fed), Copernicus CMEMS, Yahoo Finance, WOAH WAHIS, Sernapesca Chile, MET.no
- **ML models**: XGBoost price ensemble, Stige lice predictor (Bayesian), Prophet+LSTM, GNN (optional torch_geometric), Causal engine (Granger + Transfer Entropy)

## ARCHITECTURE

```
AquaIntel/
├── main.py                    # Orchestrator — launches all agents + uvicorn
├── core/
│   ├── api.py                 # 103 REST endpoints (2,789 lines)
│   ├── models.py              # SQLAlchemy ORM (20 tables)
│   ├── market/                # 27 intelligence engines
│   │   ├── feed_cost_engine.py    # Production cost (learned-principles model)
│   │   ├── biomass_predictor.py   # Cohort B(t) = Σ N_c·w_c ≤ M(t) + Monte Carlo
│   │   ├── esg_scorer.py          # ESG scoring (100 companies, A+ to F)
│   │   ├── macro_intelligence.py  # 12 FRED macro series
│   │   ├── morning_brief.py       # Daily market digest (8 sections)
│   │   ├── global_supply.py       # Multi-country supply balance (7 nations)
│   │   ├── disease_alerts.py      # WOAH outbreak monitoring
│   │   ├── fiskeridir_data.py     # 8,333 official production records
│   │   ├── regime_detector.py     # Traffic light predictions (13 PAs)
│   │   ├── farm_graph.py          # 1,815 farms, 38,407 edges, GNN spread
│   │   ├── causal_engine.py       # Granger + Transfer Entropy (12-week lag found)
│   │   ├── salmon_price.py        # Yahoo Finance equities
│   │   ├── ssb_price_client.py    # SSB Table 03024 export prices
│   │   ├── ais_tracker.py         # AIS vessel intelligence (418 vessels)
│   │   ├── sentiment_engine.py    # News NLP (iLaks, Undercurrent News)
│   │   ├── pairs_engine.py        # Statistical pairs trading
│   │   ├── chile_monitor.py       # Chilean supply disruptions
│   │   ├── price_ml.py            # XGBoost price ensemble
│   │   ├── met_ocean.py           # MET.no sea temperature
│   │   ├── ocean_chemistry.py     # GLODAPv2 (needs CSV data file)
│   │   ├── ocean_currents.py      # CMEMS NorKyst800 (dataset ID broken)
│   │   └── (backtest, biomass_tracker, compute_queue, lice_gnn, ssb_exports, top50_engine)
│   ├── twin/                  # Digital twin + agent swarm
│   ├── predictors/            # Stige model, impact translator
│   └── bloom/                 # Copernicus satellite bloom monitoring
├── agents/                    # 9 autonomous agents
│   ├── data_ingest.py         # BarentsWatch polling (15 min)
│   ├── intelligence_agent.py  # Master scheduler (60s tick)
│   ├── bloom_agent.py         # Copernicus chlorophyll (1 hour)
│   ├── prediction_agent.py    # ML pipeline
│   ├── signal_generator.py    # Trading signals
│   └── (exposure_mapper, correlation_engine, market_hedger, historical_backfill)
├── execution/                 # Trade execution (paper + live stub)
├── compliance/                # Audit trail
├── frontend/
│   ├── src/app/               # 21 Next.js pages
│   ├── src/components/        # GlassCard, KPICard, Sidebar, TopBar, Maps
│   └── src/lib/api.ts         # Centralized API client
└── docs/                      # Research reports, competitive analysis
```

## LIVE DATA SOURCES (All verified working March 29, 2026)

| Source | What It Provides | Refresh | Status |
|--------|-----------------|---------|--------|
| BarentsWatch | Lice counts for 1,815 farms, AIS vessel positions | 15 min | WORKING |
| SSB Table 03024 | Norwegian salmon export prices (NOK/kg) | 6 hours | WORKING (81.34 NOK/kg) |
| FRED (12 series) | Soy, wheat, fishmeal, rapeseed oil, soybean oil, Brent crude, NatGas EU, NOK/USD, USD/EUR, global salmon, Norway interest rate, Norway CPI | 2 hours | WORKING (5/5 feed ingredients live) |
| Copernicus CMEMS | Satellite chlorophyll-a for algal bloom risk | 1 hour | WORKING (102k grid points) |
| Yahoo Finance | MOWI.OL, SALM.OL, LSG.OL, GSF.OL, BAKKA.OL + USD/NOK | 10 min | WORKING |
| Fiskeridirektoratet | 8,333 monthly cohort production records (2005-2026) | On startup | LOADED |
| WOAH WAHIS | Global fish disease outbreak notifications | 6 hours | WORKING |
| Sernapesca Chile | Chilean salmon production + ISA/SRS outbreaks | 1 hour | WORKING |
| MET.no | Sea temperature observations + 2.5-day forecast | On demand | WORKING |
| Fish Pool | REMOVED — fishpool.eu returns 404 since late 2025 | — | DELETED |

## CORE CALCULATION MODEL (PhD-Level, Verified)

Production costs use "Learned Principles" — structural ratios extracted from 17 years (2008-2024) of official Fiskeridirektoratet data, applied to live FRED commodity prices:

```
FRED ingredients (5 live commodities, NOK via Yahoo FX)
  × 1.86 (ingredient-to-delivered multiplier — accounts for processing, logistics)
  × FCR 1.30 (Feed Conversion Ratio — latest official, range 1.21-1.35)
  = Feed cost per kg salmon

Feed cost ÷ 0.397 (feed = 39.7% of total cost — 17-year structural ratio)
  = Total production cost per kg

Non-feed components allocated by learned ratios:
  smolt 13.0%, other_operating 31.3%, slaughter 7.2%, labour 5.8%,
  net_finance 1.4%, depreciation 1.2%, insurance 0.4%

SSB spot price (live) - Total production cost = Margin
```

**Verification**: Computed NOK 64.70/kg vs official 2024 value NOK 64.64/kg = 0.1% error.

**Key constants** (all in core/market/feed_cost_engine.py):
- LEARNED_FCR_LATEST = 1.30
- LEARNED_FEED_SHARE_OF_TOTAL = 0.397
- INGREDIENT_TO_DELIVERED = 1.86
- NATIONAL_MAB_TONNES = 947,943 (biomass_predictor.py)

## CURRENT LIVE METRICS (as of March 29, 2026)

- SSB salmon spot: **NOK 81.34/kg**
- Production cost (computed): **NOK 64.70/kg**
- Margin: **NOK 16.64/kg (20.5%)**
- Feed pressure index: **56.7/100**
- Energy cost index: **51.3/100**
- NOK/USD: **9.58**
- Fishmeal: **$2,010/tonne** (+54% YoY)
- Global salmon benchmark: **$9.21/kg**
- Causal lag (lice→price): **12 weeks** (Transfer Entropy, z=3.26)
- Active AIS vessels: **418**
- Bloom risk: **42 CRITICAL, 30 HIGH** (of 1,798 assessed)
- ESG scores: **100 companies** (top grade A+)
- Farm graph: **1,815 farms, 38,407 edges, 17 clusters**

## FRONTEND PAGES (18 in sidebar)

| Page | Route | Primary Function |
|------|-------|-----------------|
| Dashboard | / | Overview KPIs, sparklines, summary |
| Morning Brief | /brief | Daily 8-section market digest |
| Leaders & ESG | /leaders | Top 100 companies ranked + ESG grades |
| Algal Bloom | /bloom | Copernicus satellite bloom risk map |
| Lice Exposure Map | /exposure | Interactive map + traffic light + GNN |
| Production Costs | /feed-cost | Cost stack waterfall + 17-year trend + 5-year ingredients |
| Global Supply | /global-supply | 7-country supply balance with disruption alerts |
| Investor Intel | /investor | Portfolio exposure + ESG + equity cards |
| Market Terminal | /market | Equities, SSB prices, seasonal, exports, macro widget |
| Price & Predictions | /price-outlook | ML ensemble forecast cone + multi-horizon table |
| Scenarios | /scenarios | Monte Carlo scenario runner + histogram |
| Backtesting | /backtest | Historical signal performance |
| Causal Engine | /causal | Granger + Transfer Entropy lag discovery |
| Digital Twin | /twin | Simulation + biomass outlook + ocean chemistry |
| AI Chat | /chat | LLM-powered Q&A over platform data |
| Farm Advisory | /farmer | Per-locality treatment recommendations |
| Signals | /signals | Active trading signals + confirmation UI |
| Settings | /settings | System status, data sources, preferences |

Hidden: /esg, /predictions, /supply, /compliance (accessible but not in sidebar)

## COMPETITIVE POSITION

| Feature | Manolin/Watershed | Kontali | AquaIntel |
|---------|:-:|:-:|:-:|
| Lice prediction | Yes | No | Yes + GNN spread |
| Disease prediction | Yes | No | Yes + WOAH alerts |
| Market intelligence | No | Yes (analyst) | Yes (automated) |
| Price forecasting | No | No | Yes (ML ensemble) |
| Trading signals | No | No | Yes |
| ESG scoring | No | No | Yes (100 companies) |
| Feed cost tracking | No | No | Yes (5 FRED ingredients) |
| Production cost model | No | No | Yes (PhD-level, 0.1% accuracy) |
| Biomass prediction | No | Yes (analyst) | Yes (cohort + Monte Carlo) |
| AIS vessel intel | No | No | Yes (418 vessels) |
| Causal inference | No | No | Yes (12-week lag) |
| Global supply model | No | Partial | Yes (7 countries) |
| Macro intelligence | No | No | Yes (12 FRED series) |
| Daily digest | No | No | Yes (Morning Brief) |

## KNOWN ISSUES

1. "other" feed ingredient uses $2/kg default — no FRED series for astaxanthin/vitamins
2. CMEMS NorKyst800 ocean currents dataset ID returns 404 — needs updated ID
3. Causal engine needs 20+ weeks of price data to run — skips with backoff if insufficient
4. tigramite not installed — PCMCI skipped, Transfer Entropy used instead
5. GNN requires torch_geometric — optional, not in base requirements
6. GLODAPv2 ocean chemistry engine ready (727 lines) but needs glodap_arctic.csv data file

## MONETIZATION MODEL (from research)

4-tier SaaS pricing:
- Producer Basic: $3,000-8,000/year (small farmers)
- Producer Pro: $15,000-40,000/year (large producers)
- Market Intelligence: $25,000-75,000/year (traders, buyers)
- Institutional: $50,000-150,000/year (hedge funds, PE, banks)
- Enterprise deals: $200-500K/year (MOWI, SalMar)
- Target TAM: $5.5-6.5M ARR by Year 5

## KEY RULES FOR ANY AI WORKING ON THIS PROJECT

1. **LIVE DATA ONLY** — never hardcode NOK values. Use learned structural ratios + live FRED/SSB data.
2. **DELTA CHANGES ONLY** — never rewrite entire files. Use surgical edits.
3. **VERIFY AFTER EVERY CHANGE** — run python import test + npx tsc --noEmit.
4. **UPDATE CLAUDE.md** — after any structural change (new routes, pages, engines).
5. **Frontend conventions** — use api.*() from lib/api, { OcButton } named import, GlassCard/KPICard, escape quotes in JSX.
6. **Backend conventions** — lazy imports in endpoints, singleton pattern, circuit breakers, structlog logging.
7. **Every number must be traceable** — cite source (Fiskeridirektoratet, Mowi Handbook, FRED series ID, SSB table number).

## RESEARCH REPORTS AVAILABLE

- docs/RESEARCH_REPORT.md — 6-agent competitive analysis, monetization, ML roadmap
- docs/COMPETITIVE_ANALYSIS.md — Deep competitor profiles (Manolin, Kontali, Aquabyte, etc.)
- ADVANCED_ROADMAP.md — Feature prioritization matrix
- CLAUDE.md — Developer context file (auto-loaded by Claude Code)

## WHAT TO BUILD NEXT (Prioritized)

1. **Fix CMEMS ocean currents** — find the new dataset ID to restore real current vectors
3. **Sidebar link to ESG from Leaders page** — tab/toggle instead of separate page
4. **Mobile PWA** — 65%+ of aquaculture users are mobile-first
5. **Email/push alerts** — morning brief delivery, price spike notifications
6. **PostgreSQL migration** — SQLite is MVP-grade, production needs Postgres
7. **Authentication** — JWT auth for multi-user, tier-based feature gating
8. **Temporal Fusion Transformer** — replace Prophet+LSTM for 15-25% accuracy gain

