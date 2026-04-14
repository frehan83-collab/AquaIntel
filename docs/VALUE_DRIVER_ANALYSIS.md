# FishIntel — What Actually Drives Value
**Date:** 2026-04-14 | **Method:** Deep market research + codebase audit + competitive analysis

---

## The Brutal Truth

Of 66 engines and 63 pages, **6 features have real commercial buyers**. The rest are technical showcases. AquaCloud (a shared aquaculture data platform) went bankrupt in January 2026 because the industry wouldn't pay enough. DNV bought the corpse. This market punishes unfocused products.

---

## The 6 Features That Make Money

### 1. Farmer Decision Engine — "Treat or Wait?"
**Value per farm: NOK 200K-2.5M/year**

| | |
|---|---|
| **Buyer** | Site managers at 50-80 Norwegian salmon companies |
| **Decision** | Treat today? Which method? What's my ROI? |
| **Data** | LIVE — BarentsWatch lice (15-min), MET.no ocean forecasts, treatment history |
| **Economics** | Wrong treatment = NOK 500K wasted. Missing regulatory threshold = 6% MAB cut. Industry spends NOK 5-18B/year on lice control |
| **Evidence** | "Each farm's ~200,000 fish; treatment cost NOK 150K-500K per event, 2-4x per year" |

### 2. Price Forecasting Ensemble — "Contract Now or Wait?"
**Value per trader: NOK 2-50M/year**

| | |
|---|---|
| **Buyer** | Salmon traders, processors, feed companies |
| **Decision** | Forward-contract now or wait 4 weeks? |
| **Data** | LIVE — SSB 6-hourly, 3 ML models (TimesFM, Chronos-2, MOIRAI-2), conformal bands |
| **Economics** | Salmon spot ranged NOK 57-125/kg in 2022. A processor buying 1000 tonnes at wrong time loses NOK 50-100M. Academic research: 7% net profit uplift from better harvest timing |
| **Evidence** | Bloznelis (2018): price-forecast-based harvest scheduling increases net profit ~7% |

### 3. Treatment Efficacy Marketplace — "What Actually Works?"
**Value: NOK 15M+ industry-wide if network reaches critical mass**

| | |
|---|---|
| **Buyer** | Veterinarians, regulators (Mattilsynet), multi-farm companies |
| **Decision** | Which treatment method works best in my region, at this temperature, this season? |
| **Data** | LIVE (farmer-logged outcomes) — but only 80 seed records today. Needs 100+ active farms |
| **Economics** | Treatment failure costs NOK 300M+/year industry-wide. 5% efficacy improvement = NOK 15M value |
| **Warning** | This is the biggest moat IF network effect kicks in. Without 100+ contributing farms, it's Tier C |

### 4. Multi-Farm Portfolio Risk — "Where Do I Focus Today?"
**Value per company: NOK 10-50M/year**

| | |
|---|---|
| **Buyer** | COOs/CFOs at Mowi, SalMar, Lerøy, Cermaq, Grieg (20-100 farms each) |
| **Decision** | Cross-farm resource allocation, synchronized treatment avoidance |
| **Data** | LIVE — all 1,815 BarentsWatch farms, mortality, disease |
| **Economics** | One prevented synchronized treatment cascade = NOK 20-50M savings |

### 5. Lice GNN Network Prediction — "Who Gets Hit Next?"
**Value: NOK 5-10M per prevented cascade**

| | |
|---|---|
| **Buyer** | Regulators (Fiskeridir), cluster management groups, multi-farm operators |
| **Decision** | Which farms will exceed threshold in 1-2 weeks due to dispersal? |
| **Data** | LIVE — graph topology from BarentsWatch, sea currents, temporal lice trends |
| **Economics** | Early warning prevents treatment cascades across clusters |
| **Moat** | Only product that predicts farm-to-farm lice contagion. Could become regulatory mandate |

### 6. Feed Cost Analytics — "What Are My Real Costs?"
**Value: NOK 350-400M/year if 1% feed cost reduction achieved industry-wide**

| | |
|---|---|
| **Buyer** | Feed companies (BioMar, Skretting), farmers, investment analysts |
| **Decision** | Real-time cost structure monitoring, ingredient price sensitivity |
| **Data** | LIVE — FRED 12 series (2-hourly), SSB prices, 17 years official cost history |
| **Economics** | Feed = 43% of NOK 64/kg production cost. 0.1 FCR improvement saves 5-9% of annual feed |
| **Evidence** | Our computed cost: NOK 64.70 vs NOK 64.64 official = 0.1% error |

---

## The 17+ Features Nobody Will Pay For

These dilute the narrative and confuse buyers:

| Feature | Why It's Tier C |
|---------|----------------|
| **Satellite imagery** | SIMULATED (no CDSE credentials). Frozen Session 9. Cloud-blocked 70% of time in fjords |
| **Pairs trading** | FROZEN. Fish Pool dead since 2025. No salmon trader uses statistical pairs |
| **Regime detector** | FROZEN. Superseded by traffic light simulator |
| **Self-evolving agent** | FROZEN. "Speculative auto-tuning, no proven value" |
| **Causal engine** | Needs 20+ weeks data. Academic output, not operational |
| **Sentiment analysis** | Hours behind real price moves. Fish prices driven by lice/feed, not headlines |
| **AIS vessel tracking** | Novelty visualization. Farmers already know which boats are harvesting |
| **RAS monitoring** | <5% of Norwegian production. No customer base |
| **Scenarios sandbox** | "Real traders use spreadsheets" — saved scenarios rarely used |
| **Chat agent** | LLM novelty. Users can just look at dashboards |
| **Command centre** | Cool infra, no use case. Who is "commanding"? |
| **Competitiveness ranking** | Tariffs change slowly. Strategic, not operational |
| **China demand** | Unpredictable market. Traders hedge via futures, not demand forecasts |
| **ASC compliance** | Binary pass/fail used once/year at audit time |
| **Welfare scorer** | Correlated with profitability but farms optimize profit directly |
| **Lice quota tracker** | Post-hoc compliance reporting, not daily decision |
| **Smolt forecasting** | Emotional market, few sellers, locked 18+ months ahead |

---

## Industry Economics (Hard Numbers)

| Metric | Value | Source |
|--------|-------|--------|
| Norway salmon exports 2024 | NOK 122.9B ($10.8B) | SSB |
| Industry pre-tax profit 2024 | NOK 14.3B (down 32% from 2023) | Fiskeridir |
| Total production cost/kg | NOK 63-64.60 (2024) | EY Aquaculture Analysis |
| Lice control costs/year | NOK 5-18B | Fish Site / Nofima |
| Mortality cost/year | ~USD 2B (57.8M fish died, 15.4% rate) | Fish Farming Expert |
| Feed share of cost | 43% | Mowi Handbook |
| ISA outbreak cost (single site) | NOK 50-500M+ | Multiple sources |
| Traffic light red zone impact | NOK 3.6B total | Fish Farming Expert |
| License auction value 2024 | NOK 5.29B for 17,330 tonnes MAB | IntraFish |
| Active farming licenses | ~1,100 in Norway | Fiskeridir |
| Meaningful farming companies | 50-80 | Industry estimates |

---

## Competitive Landscape

| Competitor | Revenue/Funding | What They Do | Our Advantage |
|------------|----------------|-------------|---------------|
| **Kontali Edge** | NOK 24M/yr, 27 staff | Market intelligence, analyst reports, SISALMONI index | We have real-time ML forecasts + operational data. They have analyst opinion |
| **Manolin** | $8M Series A | Fish health analytics (Watershed/Harpoon) | We cover market + operations + trading. They do health only |
| **AquaByte** | $41.7M raised (SoftBank) | Camera-based lice counting per pen | Hardware play. We're data platform. Complementary |
| **ScaleAQ Mercatus** | Mowi partnership | Farm management (feeding, planning) | They manage farms. We provide intelligence across farms |
| **Vesper** | EUR 5M raised | Commodity intelligence (16 categories) | We're salmon-specific with biological data. They're generic commodity |
| **AquaCloud** | **Bankrupt Jan 2026** (DNV acquired) | Shared data platform | Warning: industry won't pay for "data sharing" alone. Must deliver decisions |

**Key lesson from AquaCloud's death:** The industry will NOT pay for data platforms. They pay for **decisions**. Data is a means, not an end.

---

## What Actually Drives Willingness-to-Pay

Based on the hard numbers:

### The $500K Decision (Farmer)
> "Should I treat Farm 10735 with mechanical delousing today, or wait until next week when the water temperature drops?"

Wrong answer costs NOK 500K (wasted treatment) to NOK 2.5M (regulatory overshoot + production cut). Our Decision Engine answers this with live data + ML + economics. **This is the #1 value driver.**

### The $50M Decision (Trader)
> "Should I forward-contract 500 tonnes at NOK 89/kg for Q3 delivery, or wait for price correction?"

Wrong answer costs NOK 25-50M. Our Price Ensemble + forward curve answers this. **This is the #2 value driver.**

### The $20M Decision (Multi-Farm COO)
> "Where should I allocate treatment vessels this week across my 40 farms?"

Wrong prioritization causes cascade treatments across clusters = NOK 20M+ wasted. Our Portfolio + GNN prediction answers this. **This is the #3 value driver.**

---

## Recommended Go-to-Market

### Step 1: Kill the Noise
Remove or hide Tier C features from the main navigation. They make the platform look like a tech demo instead of a business tool.

### Step 2: Three Products, Three Buyers

| Product | Buyer | Price | Core Features |
|---------|-------|-------|---------------|
| **FishIntel Farmer** | Site managers (50-80 companies) | NOK 2,990/mo per site | Decision Engine + Treatment Efficacy + Feed Cost |
| **FishIntel Trader** | Salmon traders/processors | NOK 14,900/mo | Price Ensemble + Forward Curve + Supply Intelligence |
| **FishIntel Enterprise** | Multi-farm COOs + regulators | NOK 24,900/mo | Portfolio Risk + GNN Prediction + All Farmer features |

### Step 3: Build the Flywheel
The Efficacy Marketplace is the moat. Every farmer who logs treatment outcomes makes the platform more valuable for every other farmer. First to 100 contributing farms wins the market.

---

## TAM Calculation

| Segment | # Buyers | ACV | Revenue |
|---------|----------|-----|---------|
| Norwegian farmers (per-site) | 200 sites | NOK 36K/yr | NOK 7.2M |
| Norwegian multi-farm companies | 15 | NOK 300K/yr | NOK 4.5M |
| Salmon traders/processors | 30 | NOK 180K/yr | NOK 5.4M |
| Regulators + insurers | 10 | NOK 200K/yr | NOK 2.0M |
| International (3-5x Norway) | — | — | NOK 57M |
| **Total addressable** | | | **NOK 76M/yr** |

Kontali captures NOK 24M of this with 27 people. The market supports 2-3 players.

---

## Bottom Line

**The platform's value comes from 6 features that help people make NOK 500K-50M decisions better.** Everything else is noise. Focus the product, the pitch, and the engineering effort on these 6 features. Kill or hide the other 17+. The industry killed AquaCloud for being unfocused. Don't be AquaCloud.
