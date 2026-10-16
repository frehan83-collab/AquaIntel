# FishIntel / AquaIntel -- Project Status

> **Repository:** [github.com/frehan83-collab/AquaIntel](https://github.com/frehan83-collab/AquaIntel) (public)

Last updated: 2026-10-16 (commercial hardening — see docs/ENTITLEMENTS.md)

## Commercial hardening (in progress)

| Step | Status | Evidence |
|---|---|---|
| 1. Entitlement single source of truth | **Shipped** | `core/entitlements.py`, `docs/ENTITLEMENTS.md`, `tests/test_entitlements.py` (47 tests), Alembic 016, `/api/entitlements/{plans,me,check}` |
| 2. Money path (Stripe catalog → checkout → webhook → entitlement → gated route) | **Shipped** | `core/billing/{stripe_catalog,entitlement_sync}.py`, `docs/BILLING.md`, `tests/test_billing_money_path.py` (12 tests, no Stripe keys needed), public `/pricing` page, `GET /api/billing/catalog` |
| 3. Bio→Price Weekly + named indices (AI-STI, AI-LPI) | **Shipped** | `core/market/{indices,bio_price_weekly}.py`, `docs/INDICES.md`, `tests/test_indices.py` (20 tests), method v1.0.0 published at `/api/indices/methodology`, history in `index_observations` (Alembic 017), `/indices` page |
| 4. Accuracy & Method (published, versioned) | **Shipped** | `core/ml/accuracy_registry.py`, `scripts/publish_accuracy.py`, `docs/ACCURACY.md`, `tests/test_accuracy_registry.py` (27 tests), `artifacts/accuracy/` (tracked), `/api/accuracy` + `/accuracy` page. **No metric published yet** — environment has no real SSB data; the API says so rather than estimating |
| 5. Production truth (agents service, artifacts, PG/Timescale, freshness) | **Shipped** | `docker-compose.prod.yml` (separate `agents` service), `core/production_truth.py` + `scripts/verify_production_truth.py` (deploy-gating checks; found+fixed real `alembic_version` drift), `core/market/freshness_monitor.py` + `GET /api/data-freshness` (12 sources), `docker/init-timescale.sql`, `docs/PRODUCTION_TRUTH.md`, `tests/test_production_truth.py` (17 tests) |
| 6. Design-partner infrastructure (paid pilots, reciprocity) | Planned | |
| 7. Legal foundations (data-license register, advice boundary, DPA/AI Act) | Planned | |
| 8. Rule-3 provenance program (remaining routes + exempt register + ratchet) | Planned | |
| 9. GTM kit (ROI calculator, one-pager, demo) | Planned | |
| 10. Role definitions | Planned | |

**Plans / pricing (canonical):** Insight (free) → Operator (NOK 4,900) → Desk
(professional, NOK 2,990) → Enterprise (NOK 14,900) → Investor (NOK 24,900) →
Intelligence (NOK 39,900) + licensed Data & Assurance (EUR 25k–150k/yr).
The paywall is enforced for authenticated accounts on the curated premium outputs;
anonymous browsing is never gated.

---

## Platform Stats

| Metric | Count |
|--------|-------|
| API routes | 322 operations across 316 unique paths (measured 2026-10-16) |
| Router modules | 30 |
| Market/data engines | ~75 (incl. 3 ML foundation models) |
| Frontend pages | 63 (68 compiled routes) |
| Shared components | 43+ |
| Database tables | 31 |
| DB migrations | 15 |
| Test functions | 762 collected (739 passing, 13 xfail, 10 xpass) |
| i18n keys | ~600 (NO/EN) |
| Design tokens | 86 (Figma pipeline active) |
| Data source clients | 45+ |
| Historical data | SSB 26yr, FRED 35yr, MUR SST 44yr |
| Next.js | 16.4 |
| React | 19.1 |
| FastAPI | 2.2.0 (see core/version.py) |

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Lice monitoring & analytics | Shipped | Real-time + historical |
| Disease surveillance | Shipped | Multi-region alerts |
| Market intelligence (~75 engines) | Shipped | Spot, forward, FX, biomass |
| Billing & subscription tiers | Shipped | 4-tier access control |
| JWT auth + bcrypt + rate limiting | Shipped | Brute-force protection |
| WebSocket real-time alerts | Shipped | Price, lice, disease |
| Data provenance on all endpoints | Shipped | Source + freshness metadata |
| DataQualityBadge | Shipped | 24/65 pages show provenance |
| Scenario sandbox (compound sim) | Shipped | Multi-variable what-if |
| Notification system | Shipped | Email + in-app |
| MET.no weather forecast | Shipped | Norwegian coast coverage |
| Decision engine + SHAP explainability | Shipped | Bilingual factor importance |
| YoY trend analysis | Shipped | 5-year rolling |
| Demo mode | Shipped | Synthetic data for trials |
| CI/CD pipeline | Shipped | Docker + GHCR + Playwright E2E |
| API documentation (OpenAPI) | Shipped | Auto-generated from FastAPI |
| Efficacy marketplace | Shipped | Crowdsourced treatment benchmarks |
| Bio Risk Map time slider | Shipped | 8-week historical snapshots |
| WebSocket Command Centre | Shipped | Real-time streaming with fallback |
| Excel/CSV export | Shipped | SheetJS-based .xlsx from DataTable |
| Regional Heatmap | Shipped | PA-level disease/lice visualization |
| Satellite intelligence | Shipped | SST, chlorophyll, farm clusters |
| Supply Chain Sankey | Shipped | SVG flow visualization |
| Admin dashboard | Shipped | Data quality + platform health |
| WCAG accessibility | Shipped | ARIA labels, skip-to-content, keyboard nav |
| Dark/light theme | Shipped | Toggle + design token system |
| API caching (ETag + 5-tier) | Shipped | Cache-Control + 304 Not Modified |
| Treatment cost comparison | Shipped | 7 methods, interactive calculator |
| Company comparison (radar) | Shipped | Side-by-side metrics |
| Webhook alerts (Slack/Teams) | Shipped | Auto-disable on failure |
| Farm Portfolio | Shipped | Multi-farm risk overview |
| API key management | Shipped | bcrypt-hashed, rotation |
| Sidebar fuzzy search | Shipped | Cmd+K shortcut |
| Custom alert rules | Shipped | User-defined thresholds |
| i18n (NO/EN, ~600 keys) | Shipped | Locale-aware formatting |
| Audit logging | Shipped | Admin trail with filters |
| Dashboard customization | Shipped | Reorderable widget layout |
| TimesFM 2.5 + Chronos-2 + MOIRAI-2 | Shipped | 3 foundation models + ensemble |
| Euronext salmon futures | Shipped | ESF forward curve, basis, term structure |
| EUMOFA European market data | Shipped | Prices + trade flows |
| ASC compliance dashboard | Shipped | Readiness scoring, ProgressRing |
| CSRD sustainability export | Shipped | EU-aligned reporting |
| Lice emission quota tracking | Shipped | IMR methodology |
| Property-based testing (Hypothesis) | Shipped | 45+ property tests |
| Next.js 15 + React 19 + Compiler | Shipped | Automatic memoization |
| Figma API build pipeline | Shipped | sync_figma_tokens.py + CI verification |
| Design token system (86 tokens) | Shipped | CSS + TS + Tailwind + Figma Studio |
| Micro-interactions | Shipped | Flash-update, card-hover, alert-pulse |
| Content-shaped skeleton loaders | Shipped | 4 variants + shimmer animation |
| Empty states (ocean SVG) | Shipped | 5 variants with illustrations |
| US tariff impact analysis | Shipped | 15% Norway tariff modeling |
| EUDR compliance countdown | Shipped | Dec 2026 deadline tracking |
| MUR SST (44-year history) | Shipped | NASA JPL, 1km daily, 3-tier fallback |
| NorKyst v3 (800m currents) | Shipped | Replaces broken CMEMS NorKyst800 |
| NASA PACE HAB detection | Shipped | Hyperspectral phytoplankton species ID |
| SEPA Scotland water quality | Shipped | Time Series API for farming regions |
| Sernapesca Chile archive | Shipped | 23-year production/disease/export |
| Historical data fetchers | Shipped | SSB 26yr, FRED 35yr, Fish Pool 18yr |

---

## API Endpoints by Domain

| Domain | Router | Approx. Endpoints |
|--------|--------|--------------------|
| Auth & users | `auth_routes.py` | 12 |
| Billing | `billing_routes.py` | 8 |
| Lice data | `lice_routes.py` | 15 |
| Disease | `disease_routes.py` | 12 |
| Market intel | `market_routes.py` | 40 |
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
| Bloom/algae | `bloom_routes.py` | 7 |
| Country profiles | `country_routes.py` | 16 |
| Investor tools | `investor_routes.py` | 8 |
| Webhooks | `webhook_routes.py` | 5 |
| API keys | `apikey_routes.py` | 4 |
| Integrations | `integration_routes.py` | 4 |
| Admin | `admin_routes.py` | 12 |
| Feed cost | `feed_cost_routes.py` | 8 |
| Ocean/satellite | `ocean_routes.py` | 13 |
| AIS/regime/pairs/ESG/macro/contracts | `macro_routes.py` | 20 |
| Causal inference | `causal_routes.py` | 2 |
| RAS (land-based) | `ras_routes.py` | 3 |
| Misc (tiers/climate/competitiveness/supply/traffic-light) | `misc_routes.py` | 11 |

---

## Data Source Inventory

| Source | Client/Engine | Data | Freshness | History |
|--------|--------------|------|-----------|---------|
| BarentsWatch | barentswatch.py | Lice, disease, treatments | Weekly | 2012+ |
| SSB Table 03024 | ssb_price_client.py | Salmon prices NOK/kg | Weekly | 2000+ |
| FRED (12 series) | feed_cost_engine.py | Commodities, FX, macro | 2-hourly | 1990+ |
| MET.no | met_ocean.py | Sea temp forecast | 6-hourly | Real-time |
| Copernicus CMEMS | climate_risk_engine.py | SST, chlorophyll | Daily | 2016+ |
| NASA MUR SST | mur_sst_client.py | High-res SST (1km) | Daily | 1981+ |
| NorKyst v3 | norkyst_client.py | Norwegian coastal currents (800m) | Hourly | Archive |
| NASA PACE | nasa_pace_client.py | HAB species detection | Daily | 2024+ |
| Yahoo Finance | competitiveness_engine.py | Equities, FX | 10-min | 5yr+ |
| Fiskeridirektoratet | fiskeridir_biomass.py | Biomass, production | Monthly | 15yr+ |
| Mattilsynet | mattilsynet_client.py | Disease cases, treatments | Weekly | 5yr+ |
| WOAH WAHIS | disease_alerts.py | Global disease outbreaks | 6-hourly | Archive |
| Sernapesca | chile_monitor.py | Chilean production/disease | Monthly | 2003+ |
| SEPA Scotland | sepa_client.py | Water quality (temp, DO) | Hourly | Multi-year |
| Marine Scotland | scotland_monitor.py | Lice CSV, farm data | Weekly | Archive |
| DFO Canada | canada_monitor.py | Lice, mortality, health | Monthly | 2011+ |
| Statistics Iceland | iceland_monitor.py | Production, exports, MAB | 6-hourly | Archive |
| Hagstova Faroe | faroe_monitor.py | Harvest volumes | 6-hourly | Archive |
| EUMOFA | eumofa_client.py, eumofa_trade_client.py | EU salmon trade flows | Weekly | Multi-year |
| Euronext ESF | euronext_futures.py | Salmon futures | Daily | 2025+ |
| Fish Pool Index | price_feed_hub.py | Historical spot index | Weekly | 2006-2024 |

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
│           │340 routes│ │ 63 pages │                  │
│           └────┬─────┘ └──────────┘                  │
│                │                                     │
│        ┌───────┼───────┐                             │
│        v       v       v                             │
│   ┌─────────┐┌──────┐┌─────────┐                    │
│   │26 Router││Cache ││AsyncDB  │                    │
│   │ Modules ││Layer ││Sessions │                    │
│   └────┬────┘└──────┘└────┬────┘                    │
│        │                   │                         │
│   ┌────v────┐        ┌────v─────┐                   │
│   │~75 Data │        │PostgreSQL│                   │
│   │ Engines │        │TimescaleDB                   │
│   │+3 ML    │        │31 tables │                   │
│   └─────────┘        └──────────┘                    │
└─────────────────────────────────────────────────────┘
```
