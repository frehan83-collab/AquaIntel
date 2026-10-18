# Data sources: what they cost, what their licences allow

*Compiled 2026-10-18 from vendor and official pages (prices as published that day; no
figure below is estimated). Confidence: **H** read on the page today, **M** official
URL exists but the detail was not read end-to-end, **L** inferred.*

This file exists because the platform now sells access, and a paid product may only
display data whose licence permits it. It answers two questions: **what would more
satellite/algal-bloom data cost**, and **what may we legally show today**.

---

## 1. Satellite and ocean-colour data for algal-bloom risk

| Product | What it measures | Resolution / revisit | Licence | Price (2026-10-18) |
|---|---|---|---|---|
| **Copernicus Data Space Ecosystem** — Sentinel-2 L1C/L2A, Sentinel-3 OLCI L1B/L2, SLSTR | chl-a, Kd490, TSM/turbidity (OLCI L2); surface scum/turbidity (S2 red/NIR); SST (SLSTR) | 10–20 m (S2); 300 m (OLCI); 1 km (SLSTR) · S2 ~2–5 d at Norwegian latitudes, OLCI ~daily | Copernicus open, free re-use | **€0** — General Users quota: 10 000 Sentinel Hub requests **and** 10 000 processing units/month, 300 req/min, 50 000 COG requests/month, 25 data-workspace products/month, 12 TB/month ([quotas](https://documentation.dataspace.copernicus.eu/Quotas.html)) — H |
| **Copernicus Marine (CMEMS)** — `OCEANCOLOUR_ATL_BGC_L4_NRT_009_116`, `OCEANCOLOUR_ARC_BGC_L4_NRT_009_122` | gap-free chl-a, phytoplankton functional types, Kd/transparency | ~1 km (ATL L4), daily (ATL) / monthly (ARC) | Copernicus Marine licence: free, attribution, **redistribution and derivative works expressly permitted** (free until 30 Jun 2028) | **€0** ([product](https://data.marine.copernicus.eu/product/OCEANCOLOUR_ATL_BGC_L4_NRT_009_116/services), [licence](https://marine.copernicus.eu/user-corner/service-commitments-and-licence)) — H (IDs) / M (grid, lag) |
| **NASA OB.DAAC** — PACE OCI, MODIS-Aqua, VIIRS | chl-a, Kd490, PFT | ~1 km L3, daily | NASA open | **€0** ([OB.DAAC](https://oceandata.sci.gsfc.nasa.gov/)) — H access / M specs |
| **NASA MUR SST v4.1** | foundation SST | 1 km, daily | NASA open | **€0** ([PO.DAAC](https://podaac.jpl.nasa.gov/dataset/MUR-JPL-L4-GLOB-v4.1)) |
| **Satellittdata.no** (MET Norway + Norwegian Space Agency) | Sentinel-1/2/3/5P mirror over Norway | mission-native | free for users | **€0** ([romsenter](https://www.romsenter.no/tilgang-til-satellittdata-2/satellittdata-no)) — H |
| **MET Norway APIs** (Norkyst-800, waves, ocean forecast) | currents, SST, waves | 800 m–2.5 km, hourly–3-hourly | **CC BY 4.0**, User-Agent required | **€0** ([terms](https://api.met.no/doc/TermsOfService)) — H |
| **IMR Algestatus** | weekly HAB distribution map (qualitative) | station/area, weekly | public | **€0** — **no API** ([map](https://algestatus.hi.no/), verified 2026-10-18) — H |
| **Google Earth Engine** | L2→L3 compositing of any of the above | n/a | commercial terms | Limited (usage only); **Basic $500/month**; Enterprise Professional $2 000/month; compute $0.40/EECU-hour ([pricing](https://cloud.google.com/earth-engine/pricing)) — H |

**Quote-only (no public price found):** Sentinel Hub (its pricing page now redirects to
Planet), Planet, Descartes Labs, EOX/Sinergise, Aquabyte, Manolin, DNV Veracity, Sinay,
Xylem/YoSI, Aanderaa, SAIV.

**Our position.** The satellite stack this platform uses is **already free** (CMEMS +
CDSE + MET). The expensive part is not access; it is a validated, decision-grade signal.
That is why the platform does not buy imagery: the blockers are science (no published
operational species-level HAB forecast for the fish-killing taxa) and validation labels
(~10 lethal events over 35 years), not budget.

## 2. Data the platform displays, and what its licence allows

### Safe to display commercially with credit — **H**

| Source | What | Licence obligation |
|---|---|---|
| SSB (Statbank, incl. table 03024) | salmon export prices | CC BY 4.0 — credit |
| Fiskeridirektoratet | biomass, licences, cost survey | NLOD — credit "Kilde: Fiskeridirektoratet" |
| BarentsWatch Fishhealth | lice and treatment reports | NLOD — must show "Data delivered by BarentsWatch" + data owner (Mattilsynet), and **may not alter the data** |
| MET Norway | forecasts, ocean model | NLOD + CC BY 4.0 — credit "Data from MET Norway" |
| Copernicus Marine | chlorophyll, ocean colour | attribution, DOIs |
| FRED | commodity prices, FX history | free, but the notice **"This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis"** is required |
| Norges Bank EXR | official NOK rates | open data — credit |
| World Bank, EUMOFA | commodity and trade data | CC BY 4.0 |

### Needs a licence before charging — **H**

| Source | Position |
|---|---|
| Euronext salmon futures | commodity-derivative display **€18.80/user/month** (Level 2), €8.75 last price, redistributor non-display **€562/month**; the fee schedule says redistribution in Open Access is not permitted where no Open Access display fee applies ([schedule](https://www.euronext.com/sites/default/files/2026-06/Information%20Product%20Fee%20Schedule%20%28effective%201%20October%202026%29%20V21.1.pdf)) |
| Nasdaq Salmon Index (NQSALMON) | no public price and no public redistribution right found — direct negotiation |
| Fish Pool / SISALMONI | no public price or terms found — direct negotiation |
| Kontali | Essentials €99/month published; Species Pro / Premium (API access) quote-only ([pricing](https://www.kontali.com/pricing)) |
| Undercurrent News | **$375/month** billed annually; reproduction and distribution prohibited ([register](https://www.undercurrentnews.com/register/)) |
| IntraFish | $114/month, subscriber reading only |
| FMP, EODHD, Massive, Alpha Vantage | each requires a display/licensing agreement for redistribution |

### Unusable for resale — **H**

* **Yahoo Finance** — terms forbid selling, sharing or **deriving income from** the APIs
  without written permission ([terms](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html)).
  **Removed from the platform entirely (WS-31/WS-31b):** currency conversion now comes
  from Norges Bank, commodity prices from FRED and the World Bank, and the Oslo equity
  quotes — including the fallback that *derived* share prices from the salmon spot — are
  deleted. `/api/market/equity-prices` reports `equity_quotes: "unavailable"` until a
  licensed display feed exists.
* **FAO FishStat** — CC BY 4.0 **plus** a prohibition on use in connection with the
  promotion of a commercial product or service.
* Undercurrent/IntraFish content beyond subscriber reading.

## 3. What this means for pricing a data product

* The **free** Norwegian public APIs (SSB, Fiskeridirektoratet, BarentsWatch, MET) make a
  Norway-first intelligence product legally straightforward — the moat is productisation,
  not access.
* The two industry **benchmark indices** (NQSALMON, SISALMONI) have no published price or
  redistribution terms: they need a negotiated commercial agreement before they can
  appear in a paid product. Do not build a paid surface on them until that exists.
* A **futures display** (Euronext) is priced per user per month and is not permitted
  without a display agreement; the current synthetic forward curve must never be
  labelled real.
* Every displayed source must carry its attribution. `frontend/src/components/DataAttribution.tsx`
  is the single place that renders it, and the FRED notice is now part of that footer.
