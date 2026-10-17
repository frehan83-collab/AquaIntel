# FishIntel / AquaIntel -- Project Status

> **Repository:** [github.com/frehan83-collab/AquaIntel](https://github.com/frehan83-collab/AquaIntel) (public)

Last updated: 2026-10-17 (product value analysis — see docs/VALUE_ANALYSIS.md)

**Taking over coding? Read `docs/HANDOVER.md`** — verified state, gate commands, the
prioritised workstream backlog (WS-1 and WS-2 done; WS-3…WS-27 open, **start at WS-19**
per `docs/VALUE_ANALYSIS.md`) and the traps that cost real time.

## Commercial hardening (in progress)

| Step | Status | Evidence |
|---|---|---|
| 1. Entitlement single source of truth | **Shipped** | `core/entitlements.py`, `docs/ENTITLEMENTS.md`, `tests/test_entitlements.py` (47 tests), Alembic 016, `/api/entitlements/{plans,me,check}` |
| 2. Money path (Stripe catalog → checkout → webhook → entitlement → gated route) | **Shipped** | `core/billing/{stripe_catalog,entitlement_sync}.py`, `docs/BILLING.md`, `tests/test_billing_money_path.py` (12 tests, no Stripe keys needed), public `/pricing` page, `GET /api/billing/catalog` |
| 3. Bio→Price Weekly + named indices (AI-STI, AI-LPI) | **Shipped** | `core/market/{indices,bio_price_weekly}.py`, `docs/INDICES.md`, `tests/test_indices.py` (20 tests), method v1.0.0 published at `/api/indices/methodology`, history in `index_observations` (Alembic 017), `/indices` page |
| 4. Accuracy & Method (published, versioned) | **Shipped + populated** | `core/ml/accuracy_registry.py`, `scripts/publish_accuracy.py`, `docs/ACCURACY.md`, `artifacts/accuracy/seasonal_naive_weekly_prices.json` (**real**: MAPE 13.42%, MAE 11.60 NOK/kg, coverage 92.1%, n=208, window 2021W42..2026W41, `fallback_used: true`), `tests/test_accuracy_registry.py` (34 tests), `/api/accuracy` + `/accuracy` page |
| 5. Production truth (agents service, artifacts, PG/Timescale, freshness) | **Shipped** | `docker-compose.prod.yml` (separate `agents` service), `core/production_truth.py` + `scripts/verify_production_truth.py` (deploy-gating checks; found+fixed real `alembic_version` drift), `core/market/freshness_monitor.py` + `GET /api/data-freshness` (12 sources), `docker/init-timescale.sql`, `docs/PRODUCTION_TRUTH.md`, `tests/test_production_truth.py` (17 tests) |
| 6. Design-partner infrastructure (paid pilots, reciprocity) | **Shipped** | `core/routers/partner_routes.py` (admin-gated), `design_partners` + `partner_metrics` (Alembic 018), `docs/DESIGN_PARTNERS.md` (runbook + per-ICP success metrics), `tests/test_partner_pilots.py` (18 tests); pilots grant real entitlements via `entitlement_sync` |
| 7. Legal foundations (data-license register, advice boundary, DPA/AI Act) | **Shipped** | `core/legal/{data_licenses,performance_fee}.py`, `docs/ADVICE_BOUNDARY.md`, `/api/legal/*` (licences, use-check, advice boundary, AI Act, performance fee), `tests/test_legal.py` (18 tests). Honest state: **8 sources registered, 0 legally cleared**; perf-fee deferred by default and unadvertised |
| 8. Rule-3 provenance program (remaining routes + exempt register + ratchet) | **Shipped** | `core/provenance_register.py` (18 exempt entries with reasons), `docs/provenance_baseline.json` (237 routes → 33 exempt / 204 baselined / 0 unregistered after the f04e79a re-anchoring), `scripts/provenance_ratchet.py` (exit 1 on drift), `core/market/provenance_envelope.py::with_provenance`, 5 more routes given provenance, `tests/test_provenance_ratchet.py` (13 tests) |
| 9. GTM kit (ROI calculator, one-pager, demo) | **Shipped** | `core/gtm/roi.py` (4 ICPs; invents no market value — every line publishes its formula and flags assumptions), `/api/gtm/roi` + `/api/gtm/kit`, `docs/GTM_SECURITY_ONE_PAGER.md` (with an explicit "not in place yet" table), `docs/GTM_DEMO_SCRIPT.md`, `docs/GTM_LINKEDIN_PACK.md`, `docs/GTM_EVENTS.md`, `tests/test_gtm_roi.py` (12 tests) |
| 10. Role definitions | **Shipped** | `docs/roles/{commercial-lead,enterprise-security-engineer,product-designer-field}.md` + `docs/roles/README.md` — postable as-is, with quarterly targets, first-30-days plans and "what we will not ask you to do" |
| WS-1. Lice lineage verifiable (`lice_records.source`) | **Shipped** | `core/source_lineage.py` (one vocabulary: `barentswatch` / `demo_seed` / `unverified`), Alembic 019 (never backfills a real source), `lice_quota_tracker` row-level `lineage` + degraded provenance, `indices._lice_lineage_note()` row-level, `/api/data-freshness` `verified_rows`/`unverified_rows`/`no_verified_rows`, verifier `lice_source_column` (critical) + `freshness_no_verified_rows`, 20 tests. Honest state on the dev box: 0 verified rows → AI-LPI degraded until the ingest is healthy (WS-16) |
| WS-2. Weekly index publication scheduled | **Shipped** | `agents/index_publisher_agent.py` (13th agent: hourly check, one observation per index per ISO week behind a readiness gate the admin endpoint shares; a failure is logged, audited and exposed in health — paging is WS-9), `core/market/index_publication.py` (`status()`, `readiness()`), `publication` block on `GET /api/indices`, verifier `index_publication_current_week` + `index_publication_interval`, 29 tests |

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
| DB migrations | 19 (head 019) |
| Test functions | 1053 collected (1029 passing, 1 skipped, 13 xfail, 10 xpass — measured 2026-10-16) |
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
