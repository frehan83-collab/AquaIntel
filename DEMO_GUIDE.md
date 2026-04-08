# OpenClaw Demo Guide — 3-Minute Golden Path

> **Target:** Seafood Expo Global Barcelona, April 21-23, 2026
> **Audience:** Farm operators, traders, investors, regulators
> **Setup:** `FISHINTEL_DEMO_MODE=true python main.py` + `npm run dev`

---

## Pre-Demo Checklist

- [ ] Backend running on port 8000 (`python main.py`)
- [ ] Frontend running on port 3000/3001 (`npm run dev`)
- [ ] Demo mode enabled (`FISHINTEL_DEMO_MODE=true`)
- [ ] Browser in dark mode (our default — looks best on booth screens)
- [ ] Open dashboard at full screen (F11)
- [ ] Verify data loads (KPI cards show numbers, not spinners)

---

## The 3-Minute Story

### Act 1: The Problem (30 seconds)
**Page: Dashboard** (`/`)

> "Norwegian salmon farming generates $15B/year, but operators make critical decisions — when to treat for lice, when to harvest, where prices are going — using spreadsheets and phone calls. OpenClaw changes that."

**Point to:**
- KPI cards: spot price, feed cost, anomaly score, lice average
- Live data indicator (auto-refreshes every 60 seconds)
- Hero alert zone (if active — shows most urgent threshold breach)

### Act 2: The Intelligence (60 seconds)
**Navigate: Dashboard → Morning Brief** (`/brief`)

> "Every morning, our AI synthesizes data from BarentsWatch, SSB, Mattilsynet, MET.no, and 10+ sources into one actionable briefing."

**Point to:**
- Section count (12 sections of synthesized intelligence)
- Data provenance badges (green = live, amber = recent)
- PDF export button

**Navigate: Brief → Farmer Daily Check** (`/farmer-daily`)

> "For the farm manager on the boat: one screen, one decision. Our AI says TREAT NOW or MONITOR — with the ROI calculation backing it up."

**Point to:**
- Decision card color (rose = TREAT NOW, ocean = MONITOR)
- SHAP explainability bars (why the AI recommends this)
- Lice sparkline trend (escalating at Hitra Sor — the demo farm)
- Treatment efficacy chart (mechanical best, medicinal showing resistance)

### Act 3: The Market Edge (60 seconds)
**Navigate: Farmer Daily → Market Terminal** (`/market`)

> "For traders and investors: real-time price intelligence, forward curves, and signals."

**Point to:**
- SSB price chart (52-week history)
- NOK/USD rate (live from FRED)
- Equity prices (5 Oslo-listed salmon companies)

**Navigate: Market → Leaders & ESG** (`/leaders`)

> "We rank all 123 companies by biological performance. Investors use this to find the best operators before the market does."

**Point to:**
- Top 30 leaderboard table (sort by lice, ESG grade)
- SalMar at top (best lice performance in demo data)
- Grieg at bottom (highest lice — creates clear differentiation)

### Act 4: The Differentiator (30 seconds)
**Navigate: Leaders → Global Supply** (`/global-supply`)

> "We cover 7 countries. No one else combines biological risk, market intelligence, and regulatory compliance in one platform."

**Point to:**
- Country cards (Norway, Chile, Scotland, Faroe, Iceland, Canada)
- Supply chain Sankey diagram
- Production trends

**Close with:**

> "This is live data. Right now. Not a report from last week. OpenClaw is the Bloomberg Terminal of aquaculture."

---

## Backup Demo Paths (if questions lead elsewhere)

### "How does this help with regulations?"
→ Traffic Light (`/traffic-light`) → ASC Compliance (`/asc-compliance`)

### "What about disease outbreaks?"
→ Disease Intel (`/disease`) → Bio Risk Map (`/bio-risk`)

### "Can you predict prices?"
→ Salmon Futures (`/futures`) → ML Baselines (`/ml-baselines`)

### "How does the AI work?"
→ Causal Engine (`/causal`) → AI Chat (`/chat`)

### "Do you cover our country?"
→ Canada (`/canada`) | Scotland (`/scotland`) | Iceland (`/iceland`) | Faroe (`/faroe`)

### "What about feed costs?"
→ Feed Cost (`/feed-cost`) — composite index + Peru anchovy watch

---

## Key Numbers to Know

| Metric | Value | Source |
|--------|-------|--------|
| Norwegian salmon production | 1.7M tonnes/year | Fiskeridirektoratet |
| National MTB | 947,943 tonnes | Fiskeridirektoratet Table 8 |
| Active farms tracked | 1,815 | BarentsWatch |
| Companies benchmarked | 123 | BarentsWatch + Mattilsynet |
| Data sources integrated | 13+ | Live APIs |
| ML models deployed | 3 | TimesFM 2.5, Chronos-2, MOIRAI-2 |
| API endpoints | 300+ | FastAPI |
| Countries covered | 7 | Norway + 6 |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Pages show spinners | Backend not running. Check `python main.py` |
| No lice data | BarentsWatch credentials not set. Demo mode uses cached data |
| Charts blank | Refresh browser (Ctrl+R). Check console for errors |
| Slow load | First load warms caches. Second load is fast |
| Mobile layout issues | Platform optimized for desktop/tablet. Use landscape on tablets |
