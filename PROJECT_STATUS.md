# OpenClaw / FishIntel -- Project Status

> **Repository:** [github.com/frehan83-collab/OpenClaw](https://github.com/frehan83-collab/OpenClaw) (private)

Last updated: 2026-04-06

---

## Platform Stats

| Metric | Count |
|--------|-------|
| API routes | ~300 |
| Router modules | 24 |
| Market engines | 60 + 3 ML = 63 |
| Frontend pages | 63 |
| Shared components | 32+ |
| Database tables | 31 |
| DB migrations | 11 |
| Test functions | 370 (344 passing) |
| `api.py` lines | 1,405 |
| `api.ts` methods | 270+ |
| Next.js | 15.5.14 |
| React | 19.2.4 |
| FastAPI | 2.2.0 |

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Lice monitoring & analytics | Shipped | Real-time + historical |
| Disease surveillance | Shipped | Multi-region alerts |
| Market intelligence (53 engines) | Shipped | Spot, forward, FX, biomass |
| Billing & subscription tiers | Shipped | 4-tier access control |
| JWT auth + bcrypt | Shipped | Session management |
| WebSocket real-time alerts | Shipped | Price, lice, disease |
| Data provenance on all endpoints | Shipped | Source + freshness metadata |
| Scenario sandbox (compound sim) | Shipped | Multi-variable what-if |
| Notification system | Shipped | Email + in-app |
| MET.no weather forecast | Shipped | Norwegian coast coverage |
| Decision engine | Shipped | Traffic-light recommendations |
| YoY trend analysis | Shipped | 5-year rolling |
| Demo mode | Shipped | Synthetic data for trials |
| Pydantic v2 schemas | Shipped | Strict validation |
| CI/CD pipeline | Shipped | Docker + deploy script |
| API documentation (OpenAPI) | Shipped | Auto-generated from FastAPI |
| Efficacy marketplace | Shipped | Crowdsourced treatment benchmarks, validated input, seed data |
| Bio Risk Map time slider | Shipped | 8-week historical snapshots |
| WebSocket Command Centre | Shipped | Real-time streaming with fallback |
| Excel export | Shipped | SheetJS-based .xlsx from DataTable |
| Regional Heatmap | Shipped | PA-level disease/lice visualization |
| Decision feedback loop | Shipped | Marketplace outcomes improve recommendations |
| Satellite intelligence | Shipped | SST, chlorophyll, farm cluster analysis |
| Supply Chain Sankey | Shipped | SVG flow visualization on Global Supply |
| Admin dashboard | Shipped | Data quality monitoring + platform health |
| WCAG accessibility | Shipped | ARIA labels, skip-to-content, keyboard nav |
| Dark/light theme | Shipped | Toggle in TopBar, persisted to localStorage |
| Notification center | Shipped | Full history with severity/category filters |
| API caching (ETag) | Shipped | 5-tier Cache-Control + 304 Not Modified |
| Treatment cost comparison | Shipped | Interactive calculator with 7 methods |
| Company comparison | Shipped | Side-by-side radar chart + metrics |
| Webhook alerts | Shipped | Slack/Teams/generic, auto-disable on failure |
| Farm Portfolio | Shipped | Multi-farm risk overview with saved farms |
| API key management | Shipped | bcrypt-hashed keys, rate limiting, rotation |
| Batch data export | Shipped | CSV/JSON admin compliance export |
| Sidebar search | Shipped | Fuzzy search with Cmd+K shortcut |
| Keyboard shortcuts | Shipped | Vim-style navigation, Cmd+K, help modal |
| Custom alert rules | Shipped | User-defined thresholds with live evaluation |
| Changelog page | Shipped | Release notes with What's New indicator |
| i18n (NO/EN) | Shipped | Norwegian + English locale support |
| Audit logging | Shipped | Admin audit trail with filters |
| Bookmarkable filters | Shipped | URL-synced filter state across pages |
| Dashboard customization | Shipped | User-configurable widget layout |
| TimesFM 2.5 forecasting | Shipped | Google foundation model, XReg covariates, quantile head |
| Euronext salmon futures | Shipped | ESF forward curve, basis analysis, term structure |
| EUMOFA European market data | Shipped | EU salmon prices + trade flows |
| Decision explainability (SHAP) | Shipped | Bilingual factor importance (EN/NO) |
| Hybrid anomaly detection | Shipped | Isolation Forest + Z-score multivariate |
| Playwright E2E tests | Shipped | 16 browser tests (navigation + API) |
| Fiskeridirektoratet biomass API | Shipped | ArcGIS Open Data, locality-level standing biomass |
| Marine heatwave early warning | Shipped | SST anomaly per PA, Hobday (2016) framework |
| Treatment resistance tracker | Shipped | PA × method resistance matrix from Mattilsynet |
| ASC compliance dashboard | Shipped | Audit readiness scoring, May 2027 countdown |
| CSRD sustainability export | Shipped | EU CSRD-aligned reporting data package |
| Lice emission quota tracking | Shipped | Projected emissions per IMR methodology |
| Fishtalk 5 API integration | Shipped | Architecture-ready, awaiting credentials |
| Property-based testing | Shipped | Hypothesis tests for numerical engines |
| Next.js 15 + React 19 | Shipped | Performance upgrade, 63 pages build clean |
| Satellite biomass estimation | Planned | Blocked on CDSE credentials |

---

## API Endpoints by Domain

| Domain | Router | Approx. Endpoints |
|--------|--------|--------------------|
| Auth & users | `auth_routes.py` | 12 |
| Billing | `billing_routes.py` | 8 |
| Lice data | `lice_routes.py` | 15 |
| Disease | `disease_routes.py` | 12 |
| Market intel | `market_routes.py` | 35 |
| Farm management | `farm_routes.py` | 10 |
| Supply chain | `supply_routes.py` | 10 |
| Analytics | `analytics_routes.py` | 18 |
| ML predictions | `ml_routes.py` | 12 |
| Signals | `signals_routes.py` | 10 |
| Alerts | `alerts_routes.py` | 8 |
| Notifications | `notification_routes.py` | 8 |
| Decision engine | `decision_routes.py` | 8 |
| Digital twin | `twin_routes.py` | 10 |
| Traceability | `traceability_routes.py` | 8 |
| Bio Risk snapshots | `bloom_routes.py` (bio_risk_router) | 1 |
| Bloom/algae | `bloom_routes.py` | 6 |
| Country profiles | `country_routes.py` | 8 |
| Investor tools | `investor_routes.py` | 8 |
| Webhooks | `webhook_routes.py` | 5 |
| API keys | `apikey_routes.py` | 4 |
| Misc / health | `misc_routes.py` | 6 |

---

## Data Source Inventory

| Source | Engine(s) | Freshness |
|--------|-----------|-----------|
| Barentswatch (lice/disease) | lice_engine, disease_engine | Weekly |
| MET.no (weather) | weather_engine | 6-hourly |
| Fish Pool (spot/forward) | spot_engine, forward_engine | Daily |
| Nasdaq Salmon Index | nsi_engine | Daily |
| SSB (Statistics Norway) | export_engine, cost_engine | Monthly |
| Marine Harvest / Mowi reports | earnings_engine | Quarterly |
| USDA / FAO trade data | trade_flow_engine | Monthly |
| Currency APIs (FX) | fx_engine | Hourly |
| Internal PostgreSQL | Most engines | Live |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                   NGINX (port 80/443)                │
│                  ┌──────────┬──────────┐             │
│                  │ /api/*   │ /*       │             │
│                  v          v                        │
│           ┌──────────┐ ┌──────────┐                  │
│           │ FastAPI  │ │ Next.js  │                  │
│           │ Backend  │ │ Frontend │                  │
│           │250 routes│ │ 59 pages │                  │
│           └────┬─────┘ └──────────┘                  │
│                │                                     │
│        ┌───────┼───────┐                             │
│        v       v       v                             │
│   ┌─────────┐┌──────┐┌─────────┐                    │
│   │23 Router││Cache ││AsyncDB  │                    │
│   │ Modules ││Layer ││Sessions │                    │
│   └────┬────┘└──────┘└────┬────┘                    │
│        │                   │                         │
│   ┌────v────┐        ┌────v─────┐                   │
│   │53 Market│        │PostgreSQL│                   │
│   │ Engines │        │TimescaleDB                   │
│   └─────────┘        │31 tables │                   │
│                      └──────────┘                    │
└─────────────────────────────────────────────────────┘
```
