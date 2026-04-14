# FishIntel Data Acquisition Strategy
**Date:** 2026-04-14 | **Purpose:** What premium data to buy, costs, and ROI

---

## Executive Summary

FishIntel currently integrates **15+ free/open data sources** covering 80% of needs. But **5 critical gaps** keep us from being the Bloomberg of salmon:

| Gap | Impact | Fix Cost/yr | Revenue Unlock |
|-----|--------|-------------|----------------|
| Real-time spot prices | Traders blind between SSB weekly updates | $5-15K | $200K+ ARR |
| Live futures/forward curve | Synthetic curve = low confidence | $6-24K | $150K+ ARR |
| Vessel AIS tracking | Harvest intelligence invisible | $2.4-8K | $100K+ ARR |
| Per-farm water quality | Farmers can't optimize | Partnership | $300K+ ARR |
| Feed ingredient streaming | Week-delayed commodity data | $0.3-3.6K | $50K+ ARR |

**Total minimum investment: ~$14K/year** to unlock ~$800K+ in addressable revenue.

---

## TIER 1: BUY NOW ($14K/year total, massive ROI)

### 1. Datalastic AIS Vessel Tracking — EUR 2,388/yr ($2,600)
| | |
|---|---|
| **Provider** | [datalastic.com](https://datalastic.com/pricing/) |
| **Data** | Real-time satellite + terrestrial AIS for wellboats, treatment barges, harvest vessels |
| **Plan** | Starter: EUR 199/mo (20K requests) or Business: EUR 479/mo (unlimited) |
| **API** | REST API, well-documented, transparent pricing |
| **Why** | Track harvest activity before SSB reports it. Detect treatment vessel mobilization = lice outbreak signal. Currently our AIS data is simulated. |
| **Integration** | Replace `satellite_engine.py` AIS simulation with live Datalastic feed |
| **Revenue impact** | Trader/Investor tier differentiator — worth $100K+ ARR |

### 2. Open-Meteo Marine API — $348/yr ($29/mo)
| | |
|---|---|
| **Provider** | [open-meteo.com](https://open-meteo.com/en/pricing) |
| **Data** | ECMWF IFS 9km resolution: SST, wave height, ocean currents, salinity. 16-day forecast. Historical reanalysis. |
| **Plan** | Commercial: $29/month (1M API calls) |
| **API** | REST, excellent docs, Python client, no auth complexity |
| **Why** | Fills gaps when MET.no NorKyst is down (as observed in QA). Covers ALL 7 countries (not just Norway). Global ocean data at ECMWF quality. |
| **Integration** | Add as fallback/complement to MET.no in `climate_risk_engine.py` |
| **Revenue impact** | Reliability improvement + global coverage |

### 3. Undercurrent News Pricing API — ~$5,000-10,000/yr
| | |
|---|---|
| **Provider** | [undercurrentnews.com](https://www.undercurrentnews.com/api-access/) |
| **Data** | 3,700+ seafood price datasets. Atlantic salmon fresh/frozen/smoked by origin, grade, market. US wholesale. Trade flows. |
| **Plan** | Enterprise API — contact sales. Estimated $5-10K/yr |
| **API** | REST API launched 2023, designed for commodity tracking |
| **Why** | Replaces our single SSB price source with multi-market pricing. US market visibility (currently zero). Frozen salmon prices (currently zero). |
| **Integration** | New `undercurrent_client.py` engine, wire to Market Terminal + Price Outlook |
| **Revenue impact** | Makes our price intelligence globally competitive — $200K+ ARR from trader tier |

### 4. SISALMONI / Sitagri Salmon Index — ~$5,000-15,000/yr
| | |
|---|---|
| **Provider** | [Sitagri Index Services](https://www.sitagri.com/sitagri-salmon-index/) |
| **Data** | THE official weekly spot benchmark (11 sub-indices). Used for Euronext ESF settlement. Replaced NQSALMON. |
| **Plan** | Contact Sitagri. Estimated EUR 5K-15K/yr for data feed |
| **API** | Data distributed through Sitagri platform |
| **Why** | SSB prices are export averages (lagging). SISALMONI is the actual trading benchmark. Without it, our price data is like a stock platform without the actual ticker. |
| **Integration** | New `sisalmoni_client.py`, use as primary price source, SSB as validation |
| **Revenue impact** | Credibility with institutional traders — essential for $24.9K/mo Investor tier |

### 5. Euronext ESF Futures (Delayed) — EUR 500-2,000/yr
| | |
|---|---|
| **Provider** | [Euronext](https://live.euronext.com/en/product/commodities-futures/ESF-DPAR) |
| **Data** | EUR-denominated salmon futures. Forward curve, open interest, volume. Settled against SISALMONI. |
| **Plan** | 15-min delayed data: ~EUR 500/yr. Real-time: EUR 2,000+/yr |
| **API** | WebSocket via Optiq platform, also available through TradingView |
| **Why** | Our forward curve is SYNTHETIC (built from seasonal patterns). Real futures data = real forward curve = real basis analysis. |
| **Integration** | Replace synthetic curve in `euronext_futures.py` with live data |
| **Revenue impact** | Futures/forward curve page becomes actually useful — $150K+ ARR |

---

## TIER 2: BUY WHEN REVENUE JUSTIFIES ($15-50K/year)

### 6. Kontali Edge — NOK 50,000-150,000/yr ($5-15K)
| | |
|---|---|
| **Provider** | [Kontali Analyse](https://www.kontali.com/kontali-edge) (Trondheim) |
| **Data** | THE industry intelligence platform. Global harvest volumes, smolt releases, biomass by country/company, daily analyst commentary, supply/demand forecasts. |
| **Why** | Currently our supply forecasts are modeled from public data. Kontali has the actual numbers from producer reporting. Every serious salmon analyst uses Kontali. |
| **Risk** | They could see us as competitor. Data redistribution restrictions likely. |
| **Integration** | Feed into `global_supply.py`, `smolt_model.py` for calibration |

### 7. LFEX Daily Pricing — ~$10,000-30,000/yr
| | |
|---|---|
| **Provider** | [LFEX](https://lfexchange.com/) (London Fish Exchange) |
| **Data** | First independent DAILY salmon pricing. Live bid/ask from exporters and buyers during harvest week. Norway Exporters Salmon Index. |
| **Why** | Daily price discovery vs SSB weekly average. The difference between Bloomberg and a newspaper stock table. |
| **Integration** | Primary price source for real-time trader dashboard |

### 8. MarineTraffic/Kpler AIS — $10,000-50,000/yr
| | |
|---|---|
| **Provider** | [MarineTraffic/Kpler](https://www.kpler.com/) |
| **Data** | Premium AIS with 13,000+ receivers + satellite. Richer vessel data than Datalastic. Historical vessel tracks. Port call intelligence. |
| **Why** | Upgrade from Datalastic if Tier 1 AIS proves valuable. Deeper analytics. |
| **When** | After Datalastic proves product-market fit |

### 9. Planet Labs Satellite — $10,000-50,000/yr
| | |
|---|---|
| **Provider** | [Planet Labs](https://www.planet.com/) |
| **Data** | Daily global imaging at 3-5m resolution. Detect algal blooms, turbidity, coastal change. |
| **Why** | CMEMS is free but low resolution and delayed. Planet = daily, high-res. Could detect pen damage, oil spills, bloom onset 2-3 days earlier. |
| **When** | When satellite page usage proves demand |

---

## TIER 3: STRATEGIC PARTNERSHIPS (Revenue share, not purchase)

### 10. Fishtalk / AKVA Group — Partnership
| | |
|---|---|
| **Data** | Per-farm operational data: feeding, mortality, treatments, biomass, water quality |
| **Model** | Revenue share or data exchange. Already stubbed in code (`fishtalk_client.py`) |
| **Why** | This is THE missing piece. Per-farm data transforms every feature. Decision engine goes from "generic advice" to "your farm, right now." |
| **Unlock** | $300K+ ARR from farmer tier alone |

### 11. BioMar / Skretting Feed Data — Partnership
| | |
|---|---|
| **Data** | Feed formulation, ingredient prices, delivery schedules, FCR benchmarks per diet |
| **Model** | API partnership — they get farmer engagement, we get feed data |
| **Why** | Feed is 50-60% of production cost. Real feed data = real cost intelligence. Currently using FRED monthly averages with 1.86x multiplier. |

### 12. Insurance/Reinsurance Data — Revenue Product
| | |
|---|---|
| **Data** | Package OUR data (SST, lice, disease, anomaly scores) as insurance APIs |
| **Model** | We SELL to insurers, not buy from them |
| **Revenue** | NOK 50,000-200,000/yr per insurer. 5-10 Norwegian aqua insurers = $50-200K ARR |

---

## CURRENT DATA QUALITY GAPS (What's Degraded)

| Data Source | Status | Confidence | Issue |
|-------------|--------|------------|-------|
| Fish Pool futures | **DEAD** | 0.4 | API offline since 2025. Synthetic curve from SSB seasonal patterns |
| EUMOFA EU prices | **FLAKY** | 0.5 | API frequently down. Falls back to SSB + country premiums |
| Efficacy marketplace | **DEMO** | 0.0 | 80 synthetic treatment outcomes. No real farm data |
| China demand | **PARTIAL** | 0.6 | Only Norway→China is live (SSB). Chile/Scotland/Faroe estimated |
| Global supply 2026 | **ESTIMATED** | 0.5 | Analyst forecasts, not production data |
| AIS vessel data | **SIMULATED** | 0.0 | No real vessel tracking. Entirely synthetic |
| Satellite imagery | **SIMULATED** | 0.0 | No Sentinel-2 CDSE credentials. Simulation mode only |

---

## INVESTMENT PRIORITY MATRIX

```
                        HIGH REVENUE IMPACT
                              |
         Kontali Edge         |    SISALMONI Index
         ($5-15K)             |    ($5-15K)
                              |
         LFEX Daily           |    Undercurrent API
         ($10-30K)            |    ($5-10K)
                              |
   HIGH COST ─────────────────┼──────────────── LOW COST
                              |
         Planet Labs           |    Euronext Delayed
         ($10-50K)            |    ($0.5-2K)
                              |
         Kpler AIS            |    Open-Meteo Marine
         ($25-100K)           |    ($348/yr!)
                              |
                              |    Datalastic AIS
                              |    ($2.4K)
                        LOW REVENUE IMPACT
```

---

## RECOMMENDED PHASE 1 SHOPPING LIST

| # | Data Source | Annual Cost | Action |
|---|------------|-------------|--------|
| 1 | Open-Meteo Marine | $348 | Sign up today |
| 2 | Datalastic AIS | $2,400 | Sign up today |
| 3 | Euronext ESF (delayed) | $500-2,000 | Apply for data license |
| 4 | SISALMONI Index | $5,000-15,000 | Contact Sitagri sales |
| 5 | Undercurrent News API | $5,000-10,000 | Contact sales |
| **Total Phase 1** | | **$13,250-29,750** | |

**Expected ARR unlock from Phase 1 data: $500K-800K**
(Based on: 20 farmer licenses at $5K/yr + 10 trader licenses at $15K/yr + 5 investor licenses at $25K/yr)

---

## WHAT NOT TO BUY

| Source | Cost | Why Skip |
|--------|------|----------|
| Bloomberg Terminal | $32K/seat | FRED covers 90% of our commodity needs for free |
| Refinitiv/LSEG | $24-60K | Same — FRED + Yahoo Finance sufficient |
| Maxar/Airbus imagery | $30K+ | Overkill resolution. CMEMS + Planet sufficient |
| ScaleAQ software | $50-200K | We're a platform, not a farm management tool |

---

## BOTTOM LINE

**Spend $14K → unlock $800K ARR.** The highest-ROI data buys are:
1. **SISALMONI** — you can't be a salmon price platform without the actual benchmark
2. **Datalastic AIS** — harvest intelligence from vessel tracking is unique and defensible
3. **Undercurrent** — multi-market pricing makes us globally relevant
4. **Open-Meteo** — dirt-cheap insurance against MET.no outages + global ocean coverage
5. **Euronext delayed** — real forward curve replaces our synthetic one
