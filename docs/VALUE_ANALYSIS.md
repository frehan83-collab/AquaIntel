# AquaIntel value analysis

*17 October 2026. Read-only review of the product as it runs on the dev box at commit
`61c2318`. No code was changed.*

**Method.** Five research lenses (feature inventory, market and competitors, five
buyer personas, design identity, quality) worked from the repo, the running API and
live web research. 24 of their 27 web-sourced findings were fact-checked by
independent agents, and 8 were refuted or corrected. A first draft of this document
then went through an adversarial critique, and every section was checked twice by
independent verifiers against the code, the API and the cited sources: 391 claims
checked, 88 corrected. What could not be checked is listed in section 10. Every
number carries its source: `file:line`, an API route on this box, or a URL.

**Two kinds of finding.** Some findings describe this box. The lice data is six
months old because no agent runs here (the API was started with `--api-only`); a
production deployment with the agents service would look fresher. Most findings are
defects in the code or the copy, and they appear wherever the product runs: wrong
traffic-light colours, a placeholder company volume, an inverted index component,
"live" labels that ignore data age, an accuracy claim computed partly on demo data,
invented testimonials, SHORT calls on listed salmon shares shown to anonymous
visitors. The verdict rests on the second kind.

---

## 1. The short answers

| Question | Answer |
|---|---|
| Too many features? | **Yes.** 57 sidebar entries in 8 sections for at least six customer types (`frontend/src/components/Sidebar.tsx:25-96`). One question is split across several pages and engines, and the engines contradict each other. The pages that prove honesty (`/indices`, `/accuracy`) are not linked anywhere. The brief plus three small desks (about 8 data pages and the account shell) would serve buyers better today, with three more desks once the lice data is verified (section 4). |
| Valuable for the market today? | **Not yet.** Three of the five buyer personas modelled here would hit a code defect within minutes; the insurer would stop at a self-reported trigger and uncleared licences; the trading desk would find nothing it does not already have (section 5). The market is real but small and well supplied with free public data and quote-only incumbents. The one defensible asset, a published method with provenance and a public out-of-sample record, exists in outline: one baseline in the registry, one index week, and a price model whose edge over carrying last week's price forward is real but small (section 6). |
| What raises quality fastest? | **Cut first, then make what stays visible tell the truth**, in a set order: guard the index history before any agent runs; hide what will not be repaired soon and take down the SHORT calls on listed shares; remove invented and stale claims; take down the contaminated accuracy figure and publish a clean one; make "live" mean the data is current; load regulatory facts as dated data; fix the numbers buyers check (section 6). SSO, SOC 2, Timescale and more models wait for a named deal. |
| The "AI-made" look? | **One template repeated hundreds of times** (translucent gradient cards, KPI tiles, fade-ins, blurred chrome) under two visible product names, with chrome that claims "LIVE" on weekly data. Uniqueness should come first from content conventions only this product can have (week-and-source stamps, a confidence mark on every figure, seasonal fans, 13-area small multiples), applied inside the existing layout; a new visual system, "Sjøkart" (the sea chart), is the optional second step (section 7). |

---

## 2. What the platform delivers today

| Surface | State on this box | Evidence |
|---|---|---|
| SSB weekly salmon export price | **Live and correct**, the strongest market feed | W41 = NOK 72.55/kg (`/api/market/ssb-price-history`); W35 and W36 match the trade press exactly ([SalmonBusiness](https://www.salmonbusiness.com/statistics-norway-prices-fell-3-last-week-as-exports-topped-30000-tonnes/)) |
| Other current feeds | Live | SSB monthly exports to 2026-09 (`/api/market/exports`); MET.no ocean forecast (`/api/ocean/forecast`); Mattilsynet disease cases, fetched on request and cached for one hour (`core/market/mattilsynet_client.py:79-96`) |
| Production costs (`/feed-cost`) | **Partly live** | Five FRED ingredient prices and the SSB spot are live; the "other" ingredient (about 23% of ingredient cost) is a fixed $2/kg default, the cost structure uses fixed ratios (`core/market/feed_cost_engine.py:43-61, 89-100`), and the route carries no provenance. Margin NOK -1.47/kg (`/api/feed-cost/latest`). |
| Competitiveness | Mixed, labelled `data_quality: live` without provenance | Five currencies from Yahoo, but NOK/USD fell back to a hard-coded 0.093 (about 10.75 NOK/USD, against 9.57 in `/api/macro/snapshot`; `core/market/competitiveness_engine.py:89`); Norway's cost live, five other local costs fixed; US tariffs out of date (section 3) |
| Lice and bloom | **Stale, mostly labelled live** | `lice_records`: 186,139 rows, 0 verified, newest fetch 2026-04-07 21:41; bloom last written 2026-04-07 (`/api/data-freshness`) |
| Disease list view | Live feed, misleading view | `/api/disease/norway` shows the first 20 of 48 active outbreaks in upstream order (`mattilsynet_client.py:289`), so its newest visible date is 2026-06-09 while `/api/disease/norway/geo` shows diagnoses up to 2026-09-22 |
| National biomass | Synthetic placeholder, honestly labelled | `/api/farms/biomass/national`: 906,750 t, source `simulated`, confidence 0.0 |
| Canada, Iceland, Faroe, Scotland | Empty or hard-coded, labelled live at 0.8-0.9 | Canada: 0 farms reporting; Iceland: empty arrays (`/api/canada/snapshot`, `/api/iceland/snapshot`). Both took about 55-57 s on a cold cache; warm they answer in about 0.2 s. |
| Indices | AI-STI 100 "severe" and AI-LPI 55 "moderate", both driven by the 238,367% quota defect; AI-LPI's inverted headroom component also caps it at 55 | `/api/indices`; section 3 |
| Accuracy registry | One artifact: the seasonal-naive baseline | MAPE 13.42%, coverage 92.1%, n = 208, `fallback_used: true` (`/api/accuracy`) |
| Commercial | No customer, no pilot | All 260 `design_partners` rows are test fixtures ("X", "Scorecard Co", "Recip Co") in `data/openclaw.db`; 0 of 8 data licences cleared (`/api/legal/data-licenses`) |

**How "live" is overstated.** The liveness report lists 48 of 219 probed routes as
claiming live (`docs/REPORT_LIVENESS.md`). A probe of 39 live-claiming routes during
verification found only a handful serving current data: SSB spot and history, SSB
exports, the MET.no forecast and the Mattilsynet feed. The rest are stale or empty
under a live label, for example heatwave risk with all 13 areas UNKNOWN. On every
probed route the provenance `freshness` field holds the time the response was
computed (the request, or the last cache fill), never the age of the data. The same
dead lice table is "27 weeks stale, confidence 0.4" on `/api/lice/summary` and "live,
confidence 0.85" on `/api/leaders/top30` and `/api/brief`.

**Why the lice picture is wrong even when shown.** The ingest asks for the current
ISO week first and accepts a partial answer (`agents/data_ingest.py`), and
`/api/lice/summary` takes the newest week whatever its size
(`core/routers/lice_routes.py`). The ingest stopped on the Tuesday of 2026-W15, so
that week holds 34 farms against 473 in W14, and the dashboard's national "avg lice
0.092" describes 34 farms. The partial-week logic is a code defect; the stopped
ingest is box state.

---

## 3. Errors a domain buyer would catch in minutes

These are code or copy defects. They appear on any deployment.

| Error | What the platform says | What is true |
|---|---|---|
| Traffic lights | 8 green, 3 yellow, 2 red, wrong for 6 of 13 areas (PO5 shown red; PO6 and PO8-11 shown green), live at 0.85 (`/api/regulatory/traffic-light/current`); colours come from the frozen regime detector (`core/market/traffic_light_simulator.py:108-124, 136-138`), falling back to hard-coded 2020-2024 defaults (`:79-83`); on this box the regime detector supplied them | The 19 June 2026 decision: PO1, PO12, PO13 green; PO3 red; the other nine yellow ([regjeringen.no](https://www.regjeringen.no/no/aktuelt/ny-fargelegging-i-trafikklyssystemet-for-havbruk/id3167021/)) |
| Mowi volume | 113,600 t = 142 localities x 800 t (`core/market/top50_engine.py:249-250`), live at 0.85 | Mowi harvested 332,000 t GWT in Norway in 2025, per its Q4 2025 trading update ([We Are Aquaculture](https://weareaquaculture.com/news/aquaculture/financial-results-did-not-match-mowis-record-volumes-in-q4-2025)) |
| Supply balance | "Undersupply 82.3%": 6-month supply 140,450 t against demand 793,334 t (`/api/supply/demand-balance`) | 793 kt over 26 weeks is about 30.5 kt a week, in line with SSB export volumes; the supply side, the smolt pipeline, is about 5.6x too low. Its `biomass_current_tonnes` of 24,796 t (2.5% of capacity) is implausible, and disagrees with the platform's own placeholder of 906,750 t. |
| Lice quota | 238,367.6% national utilisation, 13 of 13 areas over quota (10,821,890 against 4,540, `/api/analytics/lice-quota/national`) | A lice count is divided by constants labelled in tonnes. The tradable quota system is a proposal in Meld. St. 24 (2024-2025) with no published allocations ([regjeringen.no](https://www.regjeringen.no/no/dokumenter/meld.-st.-24-20242025/id3097131/)). This number alone drives AI-STI to 100 "severe". |
| AI-LPI | 55 "moderate" | `quota_headroom` scores `100 - utilisation`, so more headroom raises the risk score; with the 0.55/0.45 weights the index can only read between about 27 and 55 (`core/market/indices.py:404-421`) |
| Lice limit | Decision cards use 0.5 all year (`core/market/treatment_constants.py:137`); the regulatory reporter applies 0.2 only for PA 2-7 in weeks 16-21 (`core/market/regulatory_reporter.py:189-191`) | Below 0.2 in weeks 16-21 in Nord-Trøndelag and southwards, and in weeks 21-26 in Nordland, Troms and Finnmark; 0.5 otherwise (lice regulation § 8, [Lovdata](https://lovdata.no/dokument/SF/forskrift/2012-12-05-1140)). PA 1 in spring and the northern window are missed. |
| Treatment advice | Locality 24035: "schedule treatment", cost NOK 2.11M, justified by a NOK 4.63M cost of inaction, from lice data that ends in 2026-W5 (26 Jan-1 Feb), labelled live at 0.70 (`/api/decision/24035`) | The engine takes the newest 8 rows whatever their age (`core/market/decision_engine.py:300-313`), decides on them (`:104-107`) and stamps the card live (`:138`) |
| US tariffs | Norway 15%, Chile 0%, Scotland 2.5%, Faroes 15% (`core/market/competitiveness_engine.py`) | Since July 2026: Norway 12.5%, Chile 12.5%, UK 10%; Faroes and Iceland not subject to the new tariff; Canada 10% with USMCA-qualifying goods exempt ([SalmonBusiness, 24 Jul 2026](https://www.salmonbusiness.com/trade-new-us-tariffs-reshapes-competition-between-atlantic-salmon-suppliers/)). Wrong for Norway, Chile and the UK; Faroes probably wrong; Canada and Iceland unverified. |
| **Accuracy claim** | The price outlook prints "Backtested 4-week MAPE: 8.5%" (`/api/market/price-outlook`) | The backtest (`data/models/price_backtest.json`, 2026-10-12) merged the database's SSB rows over the real CSV history, and the database rows win (`scripts/backtest_price_ml.py`, `load_ssb_series`). All 52 database rows are `demo_seed` (2025W01-W52; 2025W01 is NOK 80.26 there against a real 125.36). On real prices the price-only path scores 8.53% at 4 weeks against 8.82% for carrying the last price forward on the same weeks, so the model has a small real edge; but the published figure was computed on partly synthetic data, outside the registry, for a configuration that is not the one served (section 6). It is outside the registry, which the project's own rule says is the only source allowed to back a public accuracy claim (`/api/accuracy`), and it is copied into `price_predictions` on every outlook request and served again by `/api/market/prediction-history` (`core/routers/market_routes.py:293-313, 532-556`). |
| Model availability | `foundation_models_available: true` (`/api/accuracy`) | Set from whether `torch` imports, not from a loaded model (`core/routers/accuracy_routes.py`) |

**SHORT calls on listed shares.** Anonymous `GET /api/signals` returns 50 signals,
all SHORT, on Grieg, Lerøy, Mowi and SalMar, each with a per-share impact such as
"Expected stock impact: -17.2% (NOK -28/share)", without provenance and shown on
`/trader` and `/signals`. The project's own advice boundary says it is "not an
investment adviser and not licensed to give personal recommendations"
(`/api/legal/advice-boundary`). Information that directly proposes an investment
decision in a financial instrument may count as an investment recommendation under
the EU Market Abuse Regulation (Art. 3(1)(34),
[legislation.gov.uk](https://www.legislation.gov.uk/eur/2014/596/article/3)), which
applies in Norway through the EEA. Take these down now and get a short legal opinion.

**Commercial defects, same category:**
- **Invented testimonials** on the public landing page under "Trusted by Industry Leaders", one credited to "Head of Seafood Trading, Nordic Investment Bank", a real institution (`frontend/src/app/landing/page.tsx:47-66, 264`). There is no customer to quote. This is the largest legal and credibility risk found.
- **Stale and unproven claims:** "229 API Endpoints" on the landing page (`:69`) and the API docs page (`frontend/src/app/api-docs/page.tsx:688`) while `/api/health` reports 360; "Real-time" data (`landing/page.tsx:72`); "1,815 farms monitored ... TFT price prediction" (`:99-100`); a causal "12-week lice-to-price lag (z=3.26)" (`:18`). The landing price list matches neither `/pricing` nor `core/entitlements.py`.
- **Inverted plan ladder:** Desk at NOK 2,990 includes "Everything in Operator", the NOK 4,900 plan (`core/entitlements.py:129, 147, 153`).
- **Inverted paywall incentive:** anonymous visitors are deliberately ungated as a funnel (`core/entitlements.py:24-28, 335-337`), so price outlook, supply balance, forward curve and hedge signals answer 200 without a login, while signed-in Insight and Operator users get 402 (`core/tier_quota.py:137-139`). Logging out unlocks more than signing up.
- **ROI calculator defaults** (`/api/gtm/roi`): producer 228x, mostly from a 1.5% harvest-timing gain tied to AI-STI (`core/gtm/roi.py:23`); desk 491x from a 0.35 NOK/kg basis improvement (`:34`); processor 1,693x from a hard-coded 0.5 share of the whole margin (`:138-139`); insurer 9.9x. A finance buyer reads these as red flags.

---

## 4. Are there too many features?

Yes. 68 page files, 57 sidebar entries, at least six customer types, behind 37 router
modules and 77 market modules. Focused competitors sell two or three products
around one job: Manolin sells Watershed and Harpoon
([manolinaqua.com](https://www.manolinaqua.com/)); Kontali sells Edge, reports and
advisory ([kontali.com](https://www.kontali.com/)).

The sprawl does harm beyond clutter:
- Two pages carry the title "Price & Predictions" (`/predictions` and `/price-outlook`, both calling the same outlook).
- "Scenarios" and "Scenario Lab" share no endpoint, so one question gets two engines.
- Different engines contradict each other: 24,796 t of standing biomass in the supply balance against 906,750 t on the biomass route.
- `/predictions` carries a "Train GNN" button (shown only when `torch_geometric` is installed) and the frozen self-improvement module.
- `/indices` and `/accuracy` are linked from nowhere, although the demo script opens with them (`docs/GTM_DEMO_SCRIPT.md`); the licence table sits inside `/privacy`.
- Admin and Design System are shown to every visitor.

There is no page-view analytics, so the cuts below rest on data liveness and
duplication, not on usage. They are recommendations for the owner to decide
(recorded as WS-26 in `docs/HANDOVER.md`). Hiding is hours of work behind a flag;
do it before repairing anything, so repairs target only what stays visible.

| Action | Pages | Reason |
|---|---|---|
| Keep visible (shell) | brief (front page, after its lice, regime, bloom, ESG and early-warning sections are removed or marked unverified; its disease section stays, sorted newest first), notifications, pricing, settings and settings/webhooks, billing, login, landing (after WS-20), privacy, changelog, api-docs (trimmed to the routes that stay) | The weekly entry point and the account shell |
| **Price desk**, visible today | market, price-outlook (after the accuracy claim comes down), trader (after its SHORT signals panel is removed) | The SSB feed is live and correct |
| **Cost desk**, visible today | feed-cost, competitiveness (after the tariff and FX fixes, scheduled in days 1-14) | Partly live today |
| **Method desk**, visible today | indices (after WS-19), accuracy, plus a new view over `/api/data-freshness` and `/api/legal/data-licenses` | The credibility pages, currently orphaned |
| Show once fixed | futures (synthetic curve until a licensed one exists), contracts, global-supply, supply-forecast, china-demand, ras, feed-supply-chain | Synthetic, 5.6x wrong, or curated estimates |
| Show once lice data is verified | **Companies:** leaders, benchmark, compare, esg, investor. **Lice and health:** bio-risk, traffic-light, disease, climate on one map. **Farm:** farmer-daily absorbing farmer, portfolio, treatment, harvest | One company view, one map, one farm adviser |
| Hide behind a flag or role | canada, scotland, faroe, iceland, efficacy, welfare, twin, insurance, traceability, asc-compliance, regulatory-reports, command-centre, causal, chat, scenarios, scenarios-lab; admin for admins; design-system in development only | Empty feeds, seeded data, or no buyer yet |
| Delete or rebuild | satellite, predictions, ml-baselines, exposure, bloom, privacy-benchmark, compliance, welcome, lice-quota (until a quota regime exists), signals (the whole page: its pending and processed sections show the same SHORT equity feed, and its pairs and order sections are frozen or unconfigured); dashboard (`/`, replaced by the brief) | Frozen or unconfigured engines, mislabelled pages, duplicates, invented denominators |

That leaves the brief plus three desks visible today (price, cost, method) and three
more (companies, lice and health, farm) once the lice data is verified.

---

## 5. Is it valuable for the market?

### Market anchors

- **Kontali Analyse**, the best-known specialist: revenue NOK 31.5M in 2025 (down 3.1%), EBIT NOK -5.5M, 26 FTEs, losses in four of the last five years ([iLaks](https://ilaks.no/fjerde-ar-pa-rad-med-underskudd-for-kontali-analyse/)); revenue grew 30.5% in 2024. It is not the only seller of salmon prices: Undercurrent News and Expana/Urner Barry also publish them. Its revenue shows modest spending on specialist analysis; it does not cap the market.
- **Kontali pricing:** Essentials costs EUR 99 a month and covers news, trade statistics and market prices only. Price forecasts, supply forecasts, the Salmon Index and API access are quote-only add-ons that require the quote-only Species Pro tier ([kontali.com/pricing](https://www.kontali.com/pricing)). A forecasting product competes with those add-ons, not with Essentials.
- **Free and cheap substitutes:** SSB prices and BarentsWatch lice data are free (BarentsWatch under the NLOD licence, [developer.barentswatch.no](https://developer.barentswatch.no/docs/fishhealth/)); SalmonBusiness publishes the SSB price and analysts' weekly forecasts free, in English; IntraFish news costs $109 a month ([dngroup](https://info.dngroup.com/ifcom/4-for-4)).
- **AquaCloud**, a shared industry data platform wholly owned by The Seafood Innovation Cluster (whose owners include Lerøy, Grieg Seafood, Cargill, DNB and the University of Bergen, [iLaks](https://ilaks.no/aquacloud-skylder-over-sju-millioner-kroner/)), ran projects funded by FHF, Innovation Norway, aquaculture companies and research groups. It filed for bankruptcy in January 2026; its board said it lacked the necessary support from the industry ([We Are Aquaculture](https://weareaquaculture.com/regions/europe/norwegian-aquaculture-data-specialist-aquacloud-to-file-for-bankruptcy)). DNV agreed to buy its technology and IP to run on Veracity ([SeafoodSource](https://www.seafoodsource.com/news/business-finance/dnv-acquires-aquacloud-to-strengthen-its-shared-data-infrastructure)). It reads as a warning that the industry would not keep funding a shared data platform, not as an opening.
- **Manolin** has raised about USD 1.1M ([Caplight](https://www.caplight.com/company/manolinaqua); CB Insights gives USD 1.06M). Its Norwegian company, Manolin AS, reported operating revenue of NOK 1.81M in 2025 and NOK 0.80M in 2024 ([Brønnøysund](https://data.brreg.no/regnskapsregisteret/regnskap/920632033)). Watershed has a no-cost Researcher tier for farms in its research network and two paid tiers, Explorer and Aquanaut, priced on request ([manolinaqua.com/watershed](https://www.manolinaqua.com/watershed)). It hired its first employee in Chile in August 2026 ([SalmonBusiness](https://www.salmonbusiness.com/manolin-makes-first-chile-hire-as-salmon-data-push-expands/)).

### How many buyers exist

| Segment | Count | Source |
|---|---|---|
| Norwegian grow-out companies | 162 (a sum of county counts that includes trout producers, so the unique number is lower); the 10 largest sold 71.1% of volume in 2025 | Fiskeridirektoratet Key Figures 2025, Tables 11 and 20 ([PDF](https://www.fiskeridir.no/english/aquaculture/statistics-for-aquaculture/booklets/_/attachment/inline/890c957c-fbef-4a3e-8a7e-d4301089d599:ce284c1041b73547e4e7e0bb90e1537b19ccfe91/nokkeltall-havbruk-2025-eng.pdf)) |
| Euronext salmon futures participants | 17, of whom 9 trade frequently; no market makers | ESMA opinion, Feb 2026 ([PDF](https://www.esma.europa.eu/sites/default/files/2026-02/ESMA74-2124877886-17361_Opinion_Euronext_Salmon_contract.pdf)) |
| Sell-side analysts covering Mowi | 22 analysts at 16 houses | [mowi.com](https://mowi.com/investors/share-information/analyst-coverage/) |

**Illustrative arithmetic for the segments counted (assumptions, not a forecast).**
If 10% of the at most 152 grow-out companies outside the 10 largest paid NOK 4,900 a
month, that is about NOK 0.9M a year. If 5 of the 17 futures participants paid NOK
2,990, about NOK 0.2M. If 4 of the 16 broker houses paid NOK 24,900, about NOK 1.2M.
Together, about NOK 2-3M a year. This leaves out the 10 largest producers, insurers
and banks (one Data licence at EUR 25-150k is about NOK 0.3-1.6M at 10.6 NOK/EUR), feed companies,
exporters and foreign importers. It is a floor for the segments counted, not a
ceiling for the business. It does show that a Norway-first product sold to these
buyers is a small business, and that the repo's USD 425-715M figure
(`RESEARCH_REPORT.md:11`) has no bottom-up derivation behind it.

### Per buyer

| Buyer (plan, NOK/month) | Pays today? | The demo-breaking moment | What would change their mind |
|---|---|---|---|
| Production manager, 5-15 sites (Operator 4,900) | No | A NOK 2.1M treatment recommendation on January lice data, labelled live; 0.5 as the limit in spring | Fresh neighbour-farm lice plus their own counts through Fishtalk 5's open API, the spring limits modelled, advice checked against outcomes. Manolin offers a no-cost tier. |
| Trader or exporter desk (Desk 2,990) | No | Nothing it does not already have: desks set and trade prices daily, so the SSB all-sizes average arrives after they know it; the forward curve is honestly labelled synthetic | A size-class price view against SISALMONI, the futures settlement index ([fishpool.eu](https://fishpool.eu/sisalmoni/)), with a record that beats both carry-forward and the futures curve |
| Sell-side analyst (Investor 24,900) | No, and likely to write a critical note | Mowi at 113,600 t; ESG grades from 27-week-old lice data | A quarter-to-date tracker per listed group, backtested against reported quarters |
| Insurer or bank (Data, EUR 25-150k/year) | No | One of five payout triggers (lice) fires on counts the insured farm reports itself; ISA cover overlaps existing indemnity ([If, IPID](https://www.if.no/globalassets/no/bedrift/ipid/kyst-og-fiske/ipid-matfisk.pdf)); 0 of 8 licences cleared | A licence-cleared archive of hazards per site for loss and accumulation models |
| Processor (Enterprise 14,900 is aimed at large processors; the ROI calculator prices them at Desk 2,990) or retail buyer (no plan aimed at retail) | No | Supply off by about 5x; a processor ROI of 1,693x | A "lock the contract or wait?" view on the real futures curve with a calibrated 4-12-week supply outlook |

### What the moat is, and is not

- **Not breadth.** 360 routes are a maintenance cost, not an advantage.
- **Not models alone.** On real prices the served model beats carrying last week's price forward by 0.1-0.5 points of error at 2-8 weeks: statistically significant, economically small (section 6). Free analyst forecasts and, for desks, the futures curve are the bars buyers will judge it by.
- **Not aggregating public data.** SSB and BarentsWatch are free, and Aquafacts already maps sites, biomass, lice and company accounts ([SalmonBusiness](https://www.salmonbusiness.com/new-tool-maps-sites-biomass-lice-numbers-aquaculture-boats-and-accounts/)).
- **Not farm data.** Farms keep it in Fishtalk or Mercatus and control it. With consent and an integration the gap can close; it protects nobody.
- **The defensible asset in outline:** a published method, provenance on every figure, and a public out-of-sample record. Free weekly analyst forecasts already form a public, scoreable record, and for buyers who see a futures price the relevant bar is the futures curve. The record only becomes an asset if it beats those.
- **A timely opening:** landed-cost and trade-flow intelligence after the July 2026 US tariff change. The platform cannot use it yet: its tariff table is wrong, and its "total" puts the duty on the producer's production cost with fixed freight (`core/market/competitiveness_engine.py:233-240`), whereas an importer's landed cost is purchase price plus freight plus duty on the customs value.

### Four candidate wedges

The first draft proposed a weekly SSB-based price-and-supply brief for Norwegian
desks. That fails: desks know the price before SSB publishes it. The same objection
reaches importers on the other side of those trades, and generalist investors can
read the SSB price free in English. No candidate is ready today.

| Wedge | Buyers | Needs that do not exist yet | Main risk |
|---|---|---|---|
| **A. Origin-comparable landed cost and supply outlook** | US and EU importers, retail buyers | A landed-cost model on customs value; export volumes by destination (the export-volume source has 0 rows in `/api/data-freshness`); a real biomass feed (the current one is a placeholder); legal sign-off of the SSB licence entry (pending) | Importers may already get this from their suppliers |
| **B. Size-class price desk on SISALMONI** | Exporters, desks, processors | A redistribution licence for Fish Pool/Euronext data (`resale_allowed: false` in `core/legal/data_licenses.py`); licence cost unknown | Licence cost may exceed what 17 participants will pay |
| **C. Lice and traffic-light readiness for mid-size producers** | At most 152 companies outside the top 10 (fewer once duplicates are removed) | A working, verified lice ingest; the dated regulatory facts; a Fishtalk 5 integration | Competes with free BarentsWatch data, and with Manolin's free Researcher tier (benchmarks in exchange for contributed data) as an entry to its paid tiers |
| **D. License the method, index or brief to a distributor** | Expana/Urner Barry, DNV Veracity, trade press, the Fishtalk ecosystem; feed companies as direct buyers | A method that survives an expert's review, and a track record | Distributors buy proven series, not prototypes |

**Recommendation.** Do not build any wedge yet. Run ten paid-intent discovery calls
first, showing a hand-made sample for A and the method page for D, because those
need the least new data. Choose at day 45 on evidence. Pursue C only if producers
say they would pay and the ingest is verified; pursue B only once the licence price
is known.

**Regulatory check.** The SHORT equity signals (section 3) come down now. Price
forecasts sold to futures participants or investors may also fall under the
investment-recommendation rules of the EU Market Abuse Regulation; get a short legal
opinion before selling forecasts to those buyers.

### Pricing

Seven plans is too many for buyer pools of roughly 9 to 160 organisations
(`core/entitlements.py:107-235`). Cut to three: free, one paid plan, and custom.
Hide Investor and Intelligence until there is a published out-of-sample record, and
take the Data plan's "licensed trigger feeds with SLA" off until a licence is
cleared. Close the paywall inversion as a pricing decision, not an honesty fix:
either treat anonymous visitors as the free plan and give prospects a demo login, or
open the same routes to signed-in free users until there is a paid plan to protect.
Do not set the paid price from Kontali's EUR 99 Essentials, which contains no
forecasts; ask in the discovery calls what Kontali's forecast add-ons cost.

---

## 6. What raises quality, in order

The order matters. The store already holds a test-written AI-STI of 100 and an
AI-LPI of 55 for 2026-W42. Running the agents before step 0 would add a degraded
AI-STI of 100 every week from 2026-W43, once the 72-hour grace has passed (about 22
October; `agents/index_publisher_agent.py`, `core/market/index_publication.py`).
Running them before step 7's completeness rule would also label partial lice weeks
live, and `--agents-only` starts all 13 agents, including the frozen self-evolving
agent and the execution and hedger agents (`main.py`). Until both steps land, keep
`--api-only`. Hiding comes before repair, so effort goes only to what stays visible.

| Step | What | Size | Backlog |
|---|---|---|---|
| **0** | Withdraw AI-STI's quota component and AI-LPI v1.0, or disable the publisher, before any agent runs. Mark the two test-written 2026-W42 rows superseded under the method-version bump; do not delete them. | S | WS-19 |
| **1** | Hide the pages the owner decides to cut, behind a flag. In the same change, take down the SHORT equity signals (`/api/signals`, `/trader`, `/signals`), strip the brief's unverified sections, and sort the disease list newest first. | S | WS-26, WS-20, WS-22 |
| **2** | Public honesty: delete the testimonials and "Trusted by Industry Leaders"; remove the endpoint and engine counts (landing and API docs) and the "real-time", "1,815 farms", "TFT" and causal-lag claims; render prices from `/api/billing/catalog`; fix the Desk/Operator inversion; choose one product name. | S | WS-20 (closes WS-11) |
| **3** | Take down the 8.5% claim wherever it is served (the outlook text, the copy written to `price_predictions` on every request, `/api/market/prediction-history`), and stop writing a prediction per request. Re-run the backtest on real SSB rows only, publish it in the registry next to carry-forward with the Diebold-Mariano result, and start a weekly forecast log scored against carry-forward. | S-M | WS-23 |
| **4** | Make "live" mean live on the routes that stay visible: `is_live` from the age of the newest observation, `freshness` set to that observation's time, an empty payload never live. A lice week below the completeness threshold is never live. Remove the unconditional LIVE pulse (`frontend/src/components/TopBar.tsx:162`) and replace the price-outlook "REAL DATA" badge with a week-and-source stamp (`frontend/src/app/price-outlook/page.tsx:373`); the "All Clear" hero and the other two badges go with the dashboard and exposure pages (section 4). Decision cards refuse to recommend treatment on lice data older than two weeks. | S-M | WS-14, WS-22 |
| **5** | Regulatory facts as dated, sourced data: the 2026 traffic-light decision, the spring lice limits by region, the July 2026 US tariffs (the tariffs in days 1-14, since competitiveness stays visible). | S | WS-21 |
| **6** | Fix the numbers buyers check: the competitiveness NOK fallback (days 1-14); company volumes from reported figures (or drop the column); the smolt pipeline; the biomass placeholder; `foundation_models_available` from a loaded model; ROI assumptions defaulting to zero, with break-even shown. | S-M | WS-22 |
| **7** | Lice ingest correctness: request the last completed week, retry on zero reported farms, use a week only above a completeness threshold, flag only rises in the anomaly engine. Run the agents service and backfill only after steps 0 and 7, and only where the lice desks or wedge C need it. | M | WS-16 (with WS-9's zero-row alert) |
| **8** | Test isolation: tests that write partners, audit rows and predictions use a throwaway database, as the WS-2 publish tests now do. Land it before real design partners are recorded. | S | WS-24 |
| **9** | Cold starts: move upstream fetches off the request path and persist last-good values. Measure first under the production server configuration: the liveness probe's 60 of 219 routes over 12 s ran in-process with 8 requests in flight (`docs/REPORT_LIVENESS.md`). | M | WS-25 |

**The right accuracy bar.** The registry's baseline forecasts each week from the
same week a year earlier (13.42%). At 1-4 weeks, carrying the last observed price
forward is a much stronger bar. The table compares the served model with
carry-forward on the same target weeks, the registry's 207 scorable weeks
(2022W42-2026W41). It was computed during this review with a read-only
re-implementation of the backtest's price-only path (lice inputs at their neutral
defaults, seasonal climatology from years before 2020) on the real SSB history in
`data/historical/ssb_prices_2000_2026.csv`, without the demo rows. It is not stored
in the repo.

| Horizon | Served model (price-only path) | Carry-forward | Diebold-Mariano | p |
|---|---|---|---|---|
| 1 week | 4.17% | 4.23% | -1.45 | 0.15 |
| 2 weeks | 6.47% | 6.60% | -2.01 | 0.04 |
| 4 weeks | 8.53% | 8.82% | -2.48 | 0.01 |
| 8 weeks | 13.18% | 13.69% | -2.28 | 0.02 |

Over all 259 scorable weeks from 2021W42 the pattern is the same (8.83% against
9.14% at 4 weeks, p = 0.004). The model's edge is statistically real at 2-8 weeks and
small: 0.1-0.5 points. Whether buyers pay for that edge is a question for the
discovery calls, not for more modelling. The live outlook adds lice and other inputs
that this path holds neutral, so publish and serve the configuration that was
tested.

**Defer until a named deal waits on it:** WS-4 Timescale (186k lice rows do not need
it), WS-5 metered billing (one test subscription exists), WS-6 SSO and WS-13's SOC 2
and pen test (answer security questionnaires instead), WS-7, WS-10, WS-18, and
anything built for the NOK 39,900 tier. **Drop:** WS-15's quota calibration
(superseded by WS-19) until a quota regime publishes allocations. **Sequence:** WS-3
(shipping model artifacts) only after WS-23 has regenerated the backtest and the
conformal residuals on real rows; WS-17 and WS-8 are part of WS-23; WS-9's zero-row
alert goes with WS-16. **Keep:** the cheap part of WS-12 (never show Fish Pool or
Euronext prices publicly, never redistribute raw Copernicus data as a product), and a
local Python 3.12 install so the dev box matches CI.

---

## 7. Design identity

### Why it reads as AI-made

No single colour or font causes it. The cause is one template applied everywhere,
plus chrome that contradicts the data:

- **One template.** About 355 `GlassCard` and 260 `KPICard` tags; framer-motion in 66 page files; 63 route loading files (40 skeletons, 23 spinners). Translucent gradient cards, gradient accent bars, hover glow, count-up numbers and blurred chrome: the recognisable default of generated dark dashboards.
- **Template typography.** DM Sans, DM Serif Display and JetBrains Mono (`frontend/src/app/layout.tsx:2`), with text set at 7-10 px over 900 times. A coding font carries every KPI.
- **Colour without meaning.** About 13 Tailwind hue families plus an 8-hue chart palette; the primary accent is SaaS cyan; salmon, the brand colour, also means "bad" (`frontend/src/components/KPICard.tsx`).
- **Icons without meaning.** Globe2 five times, Shield four times, TrendingUp three times in the sidebar.
- **Two visible names.** "FishIntel" in the page title and sidebar (`layout.tsx:34`, `Sidebar.tsx:328`), "AquaIntel" in the manifest and billing (`frontend/public/manifest.json:2-3`, `frontend/src/app/billing/page.tsx:113`), and "openclaw" in the database and the `oc_live_` key prefix (`core/auth.py`).
- **Chrome that claims too much.** A pulsing LIVE pill on a weekly statistic; "All Clear" beside "Risk 50/100"; the same price shown as 72.5 and 72.6 on one screen.
- **The first impression is waiting**: skeletons, spinners and fade-ins dominated three of seven screenshots taken during this review (not stored in the repo).

The right idea is already in the repo, unseen: `docs/DESIGN_SYSTEM.md` describes
"Bloomberg Terminal meets Norwegian fjord", and sea-chart contour rings are drawn at
1.5% alpha and shown at opacity 0.4, about 0.6% effective
(`frontend/src/app/globals.css:182-189`, `frontend/src/components/GlassCard.tsx:81`).

### Layer 1: content conventions that only this product can have

These carry most of the uniqueness, cost little, and work inside the existing
layout. Apply them to the pages that stay visible, before any restyle.

1. **Time in weeks, never "LIVE".** The market runs weekly: SSB publishes weekly, and SISALMONI is calculated on Tuesdays ([fishpool.eu](https://fishpool.eu/sisalmoni/)). Every panel carries its week and source: "uke 41 · SSB" (or "week 41 · SSB" if English wins).
2. **A confidence mark on every figure**, borrowed from nautical charts' zones of confidence (CATZOC) as an analogy, not a mapping: filled for verified and current, half for degraded, hollow with "est." for estimated or synthetic, "U" for no provenance. Pressing "." opens the provenance. If a page would show mostly hollow marks, cut the page rather than mark it.
3. **Signature views:** a seasonal fan (this year over a five-year band); the 13 production areas as small multiples on aligned scales with their official traffic-light colour; a weight-class price ladder if SISALMONI is licensed.
4. **Charts like an editorial desk:** straight lines, no area fills, no animation, direct labels instead of legends, the source under every chart (as Our World in Data does, [OWID](https://ourworldindata.org/redesigning-our-interactive-data-visualizations)) plus an as-of date, lice limits and traffic-light decisions annotated, forecast bands in grey with the model named.
5. **One number formatter**, so a value renders once; no count-ups; no LIVE pulse.

### Layer 2: the "Sjøkart" visual system (optional, test first)

Read the salmon market the way a navigator reads a chart: paper, ink, hairline-ruled
tables instead of cards, depth tints for intensity, magenta reserved for caution,
salmon as the single accent for the series a page is about, and traffic-light colours
only for official status. Candidate colour values come from the IHO S-52 tables as
published in OpenCPN's `chartsymbols.xml`
([GitHub](https://raw.githubusercontent.com/OpenCPN/OpenCPN/master/data/s57data/chartsymbols.xml));
check them against the IHO standard before adopting them. A dark "dusk" mode follows
S-52's dusk table. Type: Monokrom's Telefon, drawn from the lettering of Georg Fredrik
Fasting's 1932 Norwegian telephone kiosk ([monokrom.no](https://monokrom.no/fonts/telefon)),
for the wordmark and section labels; IBM Plex Sans and Plex Mono for interface and
figures; an 11 px floor. Keyboard first: Cmd+K, "g" plus a letter for desks, a bottom
status bar of source freshness from `/api/data-freshness`.

Honest limits: hairline tables, sparklines, Cmd+K and IBM Plex are the standard
editorial and terminal idiom, so they are good practice rather than unique. The
distinctive parts of layer 2 are the chart palette and the licensed display face.
Decide the label language before choosing a Norwegian-voiced face, since wedge A
would argue for English.

**Scope and cost (owner decisions):**
- Either a scoped stylesheet and new components used only on the visible pages, with the old tokens untouched, or a full migration across 68 client pages (about 355 `GlassCard` and 260 `KPICard` uses). The second is several weeks of work.
- Costs not yet known: the Telefon web licence, moving charts to one library (ECharts; recharts is also installed), and the cached snapshot layer needed before skeletons can be removed (all pages are client-rendered today).
- Regression guard: the existing visual baseline covers only home, market, satellite and traffic-light (`frontend/e2e/visual.spec.ts`), and a redesign fails it by intent. Take new baselines of the redesigned pages once approved.
- Test layer 2 by showing two mock-ups in the discovery calls before building it.

**Files, in order:** `docs/DESIGN_SYSTEM.md` and `docs/figma-tokens.json` (which
generates `frontend/src/lib/design-tokens.ts`); `frontend/tailwind.config.ts`,
`frontend/src/app/globals.css`, `frontend/src/app/layout.tsx`; `Sidebar.tsx`,
`TopBar.tsx`; new `Panel` and `Figure` components in place
of `GlassCard` and `KPICard` on the pages in scope; the chart components.

---

## 8. What happens to the existing code

Hiding pages leaves their API routes reachable (anonymously, given the open
funnel), their live labels in place, their entries in the API docs, and their tests
in CI. If the owner chooses a wedge:
- tag the current commit so nothing is lost;
- unregister the routers behind hidden desks, not only their sidebar links;
- move frozen and unbuilt engines to an archive branch;
- trim tests, CI and the API docs to what remains.

This is an owner decision, and reversible through the tag.

---

## 9. A 90-day focus plan

Sized for a solo founder: anything not listed here waits.

**Week 1.** Step 0 (index guard). Step 1 (hide behind a flag, take the SHORT equity
signals down). Step 2, testimonials first. The takedown half of step 3: remove the
8.5% claim everywhere it is served.

**Days 1-14.** The rest of step 3 (publish the clean same-window result, start the
weekly forecast log); step 4 on the pages that stay visible; the tariff and
NOK-fallback fixes for competitiveness (steps 5 and 6); step 8, before any real
partner is recorded. Layer 1 conventions on the visible pages.

**Days 1-45.** Ten paid-intent discovery calls: three US or EU importers or retail
buyers (wedge A), two distributors or feed companies (wedge D), three independent
producers (wedge C), two exporters or desks (wedge B). Show a hand-made sample brief,
the method page and two layer-2 mock-ups. Ask what they pay today, including for
Kontali's forecast add-ons, and whether a forecast that beats carry-forward by a few
tenths of a point is worth paying for. Get the legal opinion. Record real rows in
`design_partners` once step 8 has landed and the test fixtures are removed.

**Day 45.** Choose the wedge and name its deliverable (for A: one weekly page plus an
email).

**Days 45-90.** Build only what the chosen wedge needs, plus the rest of steps 5 and
6 where it touches them. Apply layer 2 only if the calls favour it. Step 7 in full
only if wedge C wins; step 9 before any public demo. Then the first paid pilot.

**Three things to stop now:**
1. Adding pages, engines and models outside the wedge, including the Foundation Model Arena and pages on frozen engines.
2. Showing anything untrue or unlicensed: the SHORT equity signals, AI-STI and AI-LPI as they stand, the 8.5% accuracy figure, the lice-quota page, the ROI defaults, the testimonials, the Data plan's "licensed feeds", the parametric insurance products.
3. Enterprise-readiness work (SSO, SOC 2, Timescale, metered billing) until a named deal needs it.

**Metrics that measure the code, not this box:**

| Metric | Today | Day 90 |
|---|---|---|
| Visible routes whose `is_live` is computed from the newest observation's age, enforced by a test | 1 (`/api/indices`, through the WS-1 lineage rule) | All visible routes |
| Same-window backtest of the served model against carry-forward | Run during this review, not stored | Published in the registry, with the weekly log running |
| Routes over 12 s, measured under the production server configuration | Not measured that way | 0 |
| Real design partners | 0 (260 test rows) | 3 named, with written pilot terms |
| Paid pilots | 0 | 1 |

**Stop rule.** If by day 90 no buyer has accepted a paid pilot, stop and rethink the
business rather than add features. The weekly forecast log started in the first two
weeks (about 11-12 weeks by then) shows that the method is followed; on its own it cannot prove
skill.

---

## 10. What this analysis could not establish

- Whether any production deployment serves real users, and how fresh its data is.
- Kontali's forecast add-on prices; the licence cost for SISALMONI and Euronext data; the price of a Telefon web licence.
- Whether the tradable lice-emission quota system will be adopted, and when.
- The US tariff base rate for Faroese and Icelandic salmon, and whether Canadian salmon qualifies for the USMCA exemption.
- Whether selling price forecasts triggers investment-recommendation obligations (needs a legal opinion).
- Real page usage: there is no analytics, so the feature cuts rest on liveness and duplication.
- Cold-start timings (about 30 s for the dashboard, 55-57 s for two country snapshots) were observed once on the dev server and not reproduced during verification, where warm caches answered in about 0.2 s.
- The research lenses' web tally (24 of 27 fact-checked, 8 refuted) comes from the review's own run logs, which are not in the repo.
- The design screenshots were viewed during the review and not stored in the repo.

---

## Appendix: corrections to earlier research

Rows 1-6 correct the repo's earlier research documents; rows 7-9 correct claims from
this analysis's own research phase that fact-checking did not support.

| # | Earlier claim | Status | Correction |
|---|---|---|---|
| 1 | TAM USD 425-715M a year (`RESEARCH_REPORT.md:11`) | Unsupported | It has no bottom-up derivation. The segments counted in section 5 come to a low single-digit NOK million a year; the repo's own conservative case was USD 50-100M (`docs/COMPETITIVE_ANALYSIS.md`). |
| 2 | "No competitor occupies our position" (`RESEARCH_REPORT.md:11, 56`) | Overstated | Kontali, Aquafacts, Manolin, DNV (with AquaCloud's assets) and AKVA Fishtalk 5 each cover part of the ground. Only the combination is uncovered, and no buyer has yet been shown to pay for it. |
| 3 | "1/10th of Kontali's cost" (`docs/RESEARCH_SYNTHESIS.md:18`) | Unsupported | Kontali's forecast products are quote-only, so there is no public price to be a tenth of. Against the only public tier (EUR 99/month, about NOK 13k a year at 2026 rates, no forecasts), Desk at NOK 35,880 a year costs about 2.8 times as much (`core/entitlements.py:147`). |
| 4 | AquaCloud's bankruptcy as an opening (`docs/RESEARCH_SYNTHESIS.md:15`) | Reversed | The industry would not keep funding its own shared platform; DNV agreed to buy its technology and IP. "32 members" could not be verified. (`RESEARCH_REPORT.md:70` read it as a warning against raw open data, but still as support for an intelligence product.) |
| 5 | Manolin raised $897K with $48K revenue (`RESEARCH_REPORT.md:61`) | Not found in any source | About USD 1.1M raised; Manolin AS revenue NOK 1.81M in 2025 (Brønnøysund). |
| 6 | Kontali costs $10-50K a year (`RESEARCH_REPORT.md:59`) | Unverified | Only the EUR 99 tier is public; forecasts are quote-only. |
| 7 | Kontali sets a hard ceiling on market spend | Refuted | Other sellers exist (Undercurrent, Expana/Urner Barry); Kontali's revenue grew 30.5% in 2024. |
| 8 | "Many" sell-side analysts already use Kontali | Unsupported | Kontali's site shows testimonials from two sell-side houses (Handelsbanken, Pareto); no source shows how many analysts subscribe. |
| 9 | CATZOC maps directly onto the provenance states | Refuted | A useful analogy, not a mapping. |
