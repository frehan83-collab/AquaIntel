# AquaIntel — Market-Leading Advancement Roadmap

## Competitive Landscape Summary

### Current Competitors

| Platform | Focus | Strengths | Weaknesses (vs AquaIntel) |
|----------|-------|-----------|--------------------------|
| **Manolin/Watershed** | Disease prediction, farm operations | Strong biological models, farmer UX, real-time alerts | No trading signals, no market intelligence, no cross-market arbitrage |
| **Kontali** | Market analytics, production data | Industry-standard production forecasts, buyer/seller intelligence | Static reports, no real-time, no predictive ML, no farmer tools |
| **ScaleAQ** | Hardware + software integration | Physical sensor integration (oxygen, temp, feed) | Hardware-locked, no market intelligence, no trading |
| **Aquabyte** | Computer vision (lice counting) | Automated in-pen lice counting cameras | Single-purpose, no market/price analytics, expensive per-site |
| **CageEye** | Biomass estimation (sonar) | Accurate real-time biomass measurement | Single-purpose, no lice/disease prediction |
| **Optimeering** | Feed optimization | AI-driven feed strategy, FCR improvement | Feed-only, no lice/market intelligence |

### AquaIntel Unique Position

**No competitor combines all of:** lice prediction + price forecasting + trading signals + farm advisory + regulatory compliance + AIS vessel intelligence + bloom monitoring + causal inference + GNN network spread + digital twin simulation.

---

## Feature Roadmap (Prioritized by Impact)

### TIER 1: Ship Immediately (Highest Impact, Fastest Value)

#### 1.1 Feed Cost Index Integration
**Value:** Feed is 50-60% of salmon production cost. No competitor tracks feed-to-price-to-margin in real-time.
- Connect to global feed ingredient APIs (fishmeal, soy, rapeseed oil indices)
- Model feed cost per kg salmon produced
- Alert when margin squeeze detected (feed up + salmon price down)
- **Impact:** Every farmer, buyer, and investor needs this

#### 1.2 Weather & Ocean Forecast Overlay
**Value:** Sea temperature drives lice reproduction rate. 7-day forecast = 7-day lice prediction improvement.
- MET.no OceanForecast integration (already partially built)
- 7-day sea temp forecast per farm location
- Correlate forecast temp with lice growth model (Stige inputs)
- **Impact:** Upgrades lice prediction accuracy by 15-25%

#### 1.3 ESG / Sustainability Score per Company
**Value:** ESG is now mandatory for institutional investors. No salmon platform provides this.
- Compute per-company ESG score from: lice performance, treatment frequency, chemical use, mortality rate, cleaner fish adoption
- Benchmark vs industry average and peers
- Historical trend tracking
- **Impact:** Institutional investors, banks, rating agencies will pay premium

#### 1.4 Harvest Intelligence Dashboard (AIS + Supply)
**Value:** AIS vessel data is already flowing (418 positions). Turn raw positions into actionable harvest intelligence.
- Identify wellboats approaching farms → infer treatment
- Identify harvest vessels loading → infer supply coming to market
- 48-72h advance warning of supply changes
- **Impact:** Traders get edge, buyers get planning intelligence

### TIER 2: High Impact (Next Sprint)

#### 2.1 Multi-Country Supply Model (Norway + Chile + Scotland + Canada)
**Value:** Global salmon supply drives price. Chile disruptions cause Norway price spikes.
- Extend Chile monitor to Scotland (SEPA data), Canada (DFO), Faroe Islands
- Global supply balance model with disruption alerts
- Cross-country price arbitrage signals

#### 2.2 Contract Risk Analyzer for Buyers
**Value:** Salmon buyers sign fixed-price contracts. If price spikes, they're exposed.
- Model buyer contract risk vs forward curve
- Alert when contract terms become unfavorable
- Suggest hedging strategies
- **Impact:** Salmon processors/exporters will pay premium

#### 2.3 Treatment Cost Optimizer
**Value:** Treatments cost NOK 5-15M per event. Wrong timing = wasted money.
- Model optimal treatment timing based on lice trajectory + temperature + cost
- Compare mechanical vs thermal vs medicinal vs cleaner fish ROI
- Network-aware: consider neighbor farm treatment schedule

#### 2.4 Investor Portfolio Exposure Dashboard
**Value:** Institutional investors hold salmon equity (MOWI, SalMar, Lerøy, Grieg). They need lice-risk exposure analytics.
- Portfolio-weighted lice risk score
- Regulatory exposure (PA traffic light impact on production capacity)
- Peer comparison (which company outperforms on biology?)

### TIER 3: Moonshot (Competitive Moat)

#### 3.1 Reinforcement Learning Harvest Optimizer
- RL agent learns optimal harvest timing across entire farm portfolio
- Balances: fish growth rate, lice risk, market price, cage capacity, processing plant availability
- Multi-objective optimization (maximize value, minimize treatment cost, comply with regulations)

#### 3.2 Satellite Imagery Analysis (Beyond Chlorophyll)
- Integrate Sentinel-2 RGB/NIR for: cage detection, surface disturbance patterns, mortality events visible from space
- Combine with existing Copernicus chlorophyll data

#### 3.3 Real-Time Streaming Architecture
- Migrate from 15-min polling to event-driven streaming (Kafka/Redis Streams)
- Sub-second signal generation when new data arrives
- WebSocket push to all connected dashboards

#### 3.4 Federated Learning Across Farm Groups
- Allow multiple farm companies to improve shared models without sharing raw data
- Each company's local data stays private; model improvements flow to all
- Creates massive network effect and data moat

---

## Implementation Priority Matrix

| Feature | Impact | Effort | Data Available | Priority |
|---------|--------|--------|----------------|----------|
| Feed Cost Index | 🔴 Critical | 🟢 Low | Yes (public indices) | **#1** |
| Weather/Ocean Forecast | 🔴 Critical | 🟢 Low | Yes (MET.no) | **#2** |
| ESG Score | 🔴 Critical | 🟡 Medium | Yes (from existing data) | **#3** |
| Harvest Intelligence | 🔴 Critical | 🟡 Medium | Yes (AIS flowing) | **#4** |
| Multi-Country Supply | 🟡 High | 🟡 Medium | Partial | #5 |
| Contract Risk | 🟡 High | 🟡 Medium | Yes | #6 |
| Treatment Optimizer | 🟡 High | 🔴 High | Yes | #7 |
| Investor Dashboard | 🟡 High | 🟢 Low | Yes | #8 |
| RL Harvest | 🟢 Moon | 🔴 High | Yes | #9 |
| Satellite RGB | 🟢 Moon | 🔴 High | Yes (Sentinel-2) | #10 |

---

*Generated: 2026-03-29 | Next review: Weekly autonomous advancement cycle*
