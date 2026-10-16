# AquaIntel Strategic Roadmap — "Bloomberg Terminal for Salmon"

## EXECUTIVE SUMMARY

The single biggest opportunity is building a **Salmon Market Terminal** — the first real-time, algorithmic supply intelligence platform for Norwegian salmon. No competitor does this. Kontali sells static weekly reports for 100,000+ NOK/year. We can deliver real-time, predictive, continuously-updated intelligence.

**Revenue target: 10-40M NOK ARR** from traders alone. Then expand to farmers, transporters, processors.

---

## AVAILABLE DATA SOURCES TO INTEGRATE

### Tier 1 — Free APIs, Integrate Immediately

| Source | Data | Frequency | API |
|--------|------|-----------|-----|
| **BarentsWatch** (already integrated) | Lice counts, treatments, locality data | Weekly | OAuth2 REST |
| **MET.no / Yr.no** | Weather forecasts, sea temperature forecasts, wind, waves | Hourly | `https://api.met.no/weatherapi/` (free, Frost API) |
| **SSB (Statistics Norway)** | Salmon export volumes, prices, trade statistics | Monthly | `https://data.ssb.no/api/v0/` (free JSON-stat) |
| **Fiskeridirektoratet** | Biomass reports, license registry, production stats | Monthly | `https://api.fiskeridir.no/` (Akvakulturregisteret) |
| **Nasdaq Salmon Index** | Spot price reference | Weekly (Friday) | Web scrape from `salmonprice.nasdaqomx.com` |
| **Copernicus Marine (CMEMS)** | Sea surface temp, chlorophyll, ocean currents | Daily | `https://marine.copernicus.eu/` (free registration) |
| **Sentinel Hub** | Satellite imagery, algal bloom detection | Daily | ESA free tier |

### Tier 2 — Paid/Partnership, High Value

| Source | Data | Access | Value |
|--------|------|--------|-------|
| **Fish Pool** | Forward/futures prices, settlement | Member API or partnership | Core for trading terminal |
| **Kontali Analyse** | Weekly market reports, global supply/demand | Subscription ~100K NOK/yr | Benchmark and validation |
| **AIS (MarineTraffic/VesselFinder)** | Wellboat positions, movements | API subscription ~$500/mo | Transport logistics |
| **Eurostat** | EU salmon import volumes by country | Monthly | Export market intelligence |

### Tier 3 — Derived/Computed

| Signal | Derivation | Update |
|--------|-----------|--------|
| **Biomass depletion curve** | Fiskeridirektoratet monthly biomass ÷ harvest rate | Weekly |
| **Lice-to-price correlation** | BarentsWatch lice × historical Nasdaq Salmon Index | Continuous |
| **Treatment event impact** | BarentsWatch treatments → supply delay model | Per event |
| **Feed cost index** | Soy/fishmeal/rapeseed commodity prices | Daily |
| **Chilean supply disruption** | Chile Sernapesca production data + news | Weekly |

---

## WHAT TO BUILD NEXT — PRIORITIZED ROADMAP

### PHASE 1: Salmon Market Terminal (Weeks 1-4) — HIGHEST REVENUE

**Target users:** Fish Pool traders, commodity desks, salmon trading companies
**Pricing:** 8,000-20,000 NOK/month per seat

Build:
1. **Live Price Dashboard** — Nasdaq Salmon Index (weekly spot), Fish Pool forward curve, historical price charts, size-class spreads (2-3, 3-4, 4-5, 5-6, 6-7, 7+ kg)
2. **Supply Model** — Aggregate standing biomass by PA (1-13), harvest pace indicator, estimated days-of-supply-remaining, lice-driven supply disruption alerts
3. **Lice-to-Price Predictor** — Quantitative model: when lice spike → farmers accelerate harvest (short-term supply glut, price dip) → then reduced future supply (forward price rise). 2-6 week price direction forecast
4. **Treatment Impact Model** — Aggregate treatment events from BarentsWatch → model harvest delays → predict supply shortfall windows
5. **Seasonal Anomaly Detector** — Is current price above/below expected seasonal pattern? Calculate reversion probability
6. **Alert System** — "PA-4 lice levels exceeded threshold this week — expect coordinated delousing, harvest delays, spot price upward pressure in 3-4 weeks"

### PHASE 2: Harvest Optimizer for Farmers (Weeks 4-8)

**Target users:** 100+ Norwegian farming companies
**Pricing:** 15,000-40,000 NOK/month

Build:
1. **"When to Harvest" Engine** — Combines: current spot price, forward curve shape, fish size distribution, growth trajectory to next size class, feed cost of holding, cage capacity for next smolt generation, regulatory windows → optimal harvest week recommendation
2. **Feed Cost Optimizer** — Independent of feed supplier. Ingest feeding data + environmental conditions → recommend optimal daily feeding amounts and timing
3. **Lice Cost-Benefit Calculator** — "Treating now costs NOK X (treatment + mortality + growth delay). Waiting 1 week costs NOK Y (increased lice + regulatory risk). Recommendation: treat/wait"
4. **Multi-Generation Cage Planner** — Smolt stocking dates, growth projections, fallow periods, cage rotation schedules

### PHASE 3: Transport & Logistics (Weeks 8-12)

**Target users:** Wellboat operators (Solvtrans, Rostein, etc.), trucking companies
**Pricing:** Transaction fees (per tonne-km) + SaaS

Build:
1. **Wellboat Marketplace** — "Uber for brønnbåt": match farms needing transport with available vessels, optimize routes to minimize empty legs
2. **Route Optimizer** — Algorithm considering: farm locations, tide/weather windows, biosecurity zone constraints, disinfection stops, processing plant berth availability
3. **Cold Chain Monitor** — Real-time temperature tracking from farm → wellboat → plant → truck → airport, with break-in-chain alerts
4. **Airport Cargo Coordinator** — Connect harvest timing with flight availability at Gardermoen, Flesland, Vigra, Evenes. If truck arrives late → cargo misses flight → 12-24h delay → quality impact

### PHASE 4: Export Intelligence (Weeks 12-16)

Build:
1. **Multi-Market Price Dashboard** — Rungis (Paris), Tsukiji/Toyosu (Tokyo), US wholesale prices
2. **Currency-Adjusted Profitability** — NOK/EUR, NOK/USD, NOK/JPY impact on export margins
3. **Air vs Sea Freight Optimizer** — Cost/freshness tradeoff calculator by destination market
4. **Trade Compliance Automation** — Auto-generate EU health certificates, customs declarations

---

## PRICING MODEL INNOVATIONS

### 6 Predictive Models to Build

| Model | Signal → Price Impact | Data Sources | Update |
|-------|----------------------|--------------|--------|
| **Lice-to-Price** | Lice spike → harvest acceleration → glut then shortage | BarentsWatch + Nasdaq Salmon | Weekly |
| **Biomass Depletion** | Standing biomass below norm → price rise | Fiskeridirektoratet + harvest rates | Monthly |
| **Treatment Cascade** | Coordinated treatments in PA → 4-8 week supply gap | BarentsWatch treatments | Per event |
| **Chilean Cross-Market** | Chile disruption → demand shift to Norway → price rise | Sernapesca + news | Weekly |
| **Feed Cost Floor** | Soy/fishmeal prices → production cost floor → price support | Commodity exchanges | Daily |
| **Seasonal Anomaly** | Price deviation from expected seasonal pattern → reversion | Historical Nasdaq Salmon | Continuous |

### The "Holy Grail" Model: Integrated Supply-Demand Balance

```
Supply Side:                     Demand Side:
  Norwegian biomass (PA 1-13)      EU import demand (seasonal)
+ Chilean production               Japan/Asia demand
+ Scottish/Faroese production      US demand
- Lice-driven harvest delays       Retail promotion calendars
- Treatment mortality               Foodservice trends
- Regulatory quota cuts             Substitute protein prices
= Total Available Supply           = Total Demand

→ Price Forecast (2-20 week horizon with uncertainty bands)
```

---

## NETWORK EFFECT STRATEGY

The platform becomes indispensable when:

1. **Farmers** share harvest plans → better supply forecasts → more accurate price predictions
2. **Traders** trust the price models → trade on them → models become self-fulfilling reference
3. **Transporters** book through the platform → logistics data improves supply chain forecasts
4. **Processors** report capacity → harvest scheduling optimizes → less waste

**Each participant's data makes the platform more valuable for everyone else.**

---

## COMPETITIVE POSITIONING

| Competitor | What They Do | What They Don't Do |
|-----------|-------------|-------------------|
| **Kontali Analyse** | Weekly market reports | No real-time data, no algorithms, no predictions |
| **Manolin/Watershed** | Farm-level disease analytics | No market terminal, no pricing, no transport, no value chain |
| **Fish Pool** | Derivatives marketplace | No supply intelligence, no analytics |
| **AquaCloud** | Lice data aggregation | No predictions, no commercial layer |
| **AquaIntel** | **ALL OF THE ABOVE + AI + Digital Twin** | — |

---

## IMMEDIATE NEXT STEPS

1. **Integrate MET.no weather API** — sea temperature forecasts improve lice predictions by ~15%
2. **Integrate SSB export statistics** — monthly volumes and prices by destination market
3. **Integrate Fiskeridirektoratet biomass API** — standing biomass is THE key supply indicator
4. **Build Nasdaq Salmon Index scraper** — weekly spot price is the reference
5. **Build lice-to-price correlation model** — the single most valuable quantitative feature
6. **Add transport tracking page** — wellboat positions from AIS data
