# Deep Research: Market Opportunities We're Missing

## BIGGEST GAPS NO ONE IS FILLING

### 1. ALGAL BLOOM EARLY WARNING (Critical — lives and millions at stake)
- **What happened**: Northern Norway lost millions of fish in 2019 and 2024 from algal blooms. March 2026 Skagerrak coast also hit.
- **Gap**: No real-time predictive platform exists. OTAQ has hardware cameras but no predictive model.
- **Our play**: Integrate Copernicus satellite chlorophyll data (daily, free) + MET.no sea temp + NorKyst800 currents → build an **algae bloom risk predictor** per locality. Alert farmers 3-7 days before bloom reaches their site.
- **Who pays**: Every farmer. This is life-or-death for their stock. 10,000+ NOK/month easy.
- **Build effort**: Medium — data sources exist, need the prediction model.

### 2. PARAMETRIC INSURANCE DATA LAYER (New revenue stream)
- **Research finding**: Academic paper (2025) confirms parametric insurance for aquaculture using sea surface temperature triggers is viable. Insurers need to frequently revise triggers based on latest oceanographic data.
- **Our play**: Become the **data provider to insurance companies**. Sell our sea temperature monitoring, lice predictions, and algae risk scores as parametric trigger data to underwriters.
- **Who pays**: Insurance companies (Gjensidige, IF Skadeforsikring, specialist marine insurers). License fees 50,000-200,000 NOK/year per insurer.
- **Build effort**: Low — we already have the data. Need packaging and API.

### 3. FISH WELFARE SCORING (ASC Compliance Automation)
- **Research finding**: New ASC Farm Standard (May 2025) requires 9-category welfare scoring. Currently done manually. SWIM (Salmon Welfare Index Model) scores on 0-3 scales.
- **Our play**: Build an **automated welfare compliance dashboard** that tracks the 9 ASC categories using data we already collect (lice, treatments, mortality, temperature, handling events). Auto-generate ASC audit reports.
- **Who pays**: Every ASC-certified farm (which is most large producers). Saves weeks of manual compliance work per audit cycle. 5,000-15,000 NOK/month.
- **Build effort**: Medium — need to map our data to ASC scoring criteria.

### 4. FEED COST OPTIMIZER (50-60% of production cost)
- **Research finding**: Feed is 50-60% of salmon production cost. AI can reduce FCR by 5-15%. The global feed optimization market is USD 1.35B growing 14.4% CAGR.
- **Gap**: Feed suppliers (Skretting, Cargill, BioMar) offer their own models but they're biased — they want to sell MORE feed. Farmers need independent optimization.
- **Our play**: Build a **feed cost tracker** that correlates feed commodity prices (soy, fishmeal, rapeseed) with optimal feeding rates based on sea temperature and growth stage. Show farmers where they're overspending.
- **Who pays**: Farmers. A 5% FCR improvement on a 10,000-tonne farm saves ~NOK 20M/year.
- **Build effort**: Medium-high. Need feed commodity price feeds + growth model integration.

### 5. WELLBOAT MARKETPLACE ("Uber for Brønnbåt")
- **Research finding**: ~80-90 active wellboats in Norway (Sølvtrans, Rostein, etc.). Scheduling is done by phone/email. No digital marketplace exists. Wellboats cost 200M+ NOK each — utilization is critical.
- **Our play**: Build a **wellboat booking and route optimization platform**. Show available vessels, optimize routes to minimize empty legs, enforce biosecurity zone constraints.
- **Who pays**: Wellboat operators (utilization optimization) + farmers (transparent pricing, guaranteed capacity). Transaction fees per booking.
- **Build effort**: High — need AIS tracking + booking system + routing algorithm.

### 6. SALMON PRICE PREDICTION (Proven ML approaches)
- **Research finding**: Published papers show LSTM models effectively forecast salmon price volatility. Best models: k-nearest neighbors for 1-week, elastic net for 2-3 weeks, futures prices for 4-5 weeks.
- **Critical insight**: A 2025 paper combines conformal prediction with dynamic portfolio insurance — uncertainty-aware price hedging. No commercial product does this.
- **Our play**: We already built the lice-to-price model. Now add: (1) conformal prediction intervals, (2) hedging strategy recommendations, (3) multi-factor model (lice + biomass + feed costs + Chilean supply + EUR/NOK).
- **Who pays**: Traders (8,000-20,000 NOK/month), farmers for harvest timing.

### 7. ESG/SUSTAINABILITY REPORTING AUTOMATION
- **Research finding**: GSI & WWF launched an ESG Feed Risk Assessment Tool (2024). Sustell by DSM-Firmenich calculates carbon footprint per farm. But no platform integrates ESG across the full value chain.
- **Our play**: Build an **automated ESG dashboard** that calculates carbon footprint per kg of salmon produced, using our data on treatments (chemical vs mechanical), feed usage, transport mode, and energy consumption.
- **Who pays**: All listed companies (MOWI, SALM, LSG, GSF) need this for mandatory EU CSRD reporting. Processors and exporters need it for retail buyer requirements.
- **Build effort**: Medium. We have most input data. Need LCA methodology integration.

### 8. MORTALITY PREDICTION & ROOT-CAUSE ANALYSIS
- **Research finding**: AI mortality prediction is an active research area. Companies want: "Your mortality in cage 3 is trending high — most likely causes are: (1) gill disease from algal event, (2) handling stress from delousing."
- **Our play**: Build a **mortality anomaly detector** that flags unusual mortality patterns and correlates with known causes (recent treatments, temperature events, lice levels, disease reports).
- **Who pays**: Farmers — mortality directly = lost revenue. Insurance companies.
- **Build effort**: Medium. Need mortality data from Fiskeridirektoratet.

## PRIORITY MATRIX

| Opportunity | Revenue Potential | Build Effort | Time to Revenue | Competitive Moat |
|-------------|-------------------|--------------|-----------------|-------------------|
| **Algal Bloom Warning** | Very High | Medium | 2-3 months | HIGH (satellite + prediction) |
| **Insurance Data Layer** | High | Low | 1-2 months | HIGH (unique data position) |
| **Price Prediction v2** | Very High | Medium | 1-2 months | MEDIUM (research public) |
| **ASC Welfare Compliance** | High | Medium | 2-3 months | MEDIUM |
| **Feed Cost Optimizer** | Very High | High | 3-4 months | HIGH (independent of suppliers) |
| **ESG Reporting** | High | Medium | 2-3 months | MEDIUM |
| **Wellboat Marketplace** | High | High | 4-6 months | VERY HIGH (network effect) |
| **Mortality Prediction** | Medium | Medium | 2-3 months | MEDIUM |

## RECOMMENDED BUILD ORDER

1. **Now**: Algal Bloom Warning (Copernicus + satellite data) — saves lives, makes headlines
2. **Next**: Insurance Data API — low effort, high-margin revenue
3. **Then**: Price Prediction v2 with conformal intervals — traders pay immediately
4. **After**: ASC Welfare Dashboard — compliance automation, sticky product
5. **Future**: Feed Optimizer + Wellboat Marketplace — bigger builds, bigger moats

Sources:
- [Salmon Price Forecasting (LSTM)](https://www.tandfonline.com/doi/full/10.1080/13657305.2023.2255346)
- [Parametric Insurance for Aquaculture](https://link.springer.com/article/10.1007/s11160-025-09920-3)
- [ASC Farm Standard V1.5 (Oct 2025)](https://asc-aqua.org/wp-content/uploads/2025/10/ASC-STD-010-ASC-Salmon-and-Cod-Standard-V1.5-Oct-2025-1.pdf)
- [Feed Optimization Market ($1.35B)](https://www.futuredatastats.com/data-driven-aquaculture-feed-optimization-market)
- [Climate Risks in Norwegian Aquaculture (EY)](https://www.ey.com/en_no/insights/climate-change-sustainability-services/why-aquaculture-must-adapt-to-risks-posed-by-climate-change)
- [Algae Bloom Norway 2024](https://www.seafoodsource.com/news/aquaculture/algae-bloom-in-northern-norway-resulting-in-salmon-mortalities)
- [Digital Welfare Scoring](https://www.frontiersin.org/journals/animal-science/articles/10.3389/fanim.2023.1162384/full)
- [FCR Prediction ML](https://www.mdpi.com/2076-2615/15/12/1773)
