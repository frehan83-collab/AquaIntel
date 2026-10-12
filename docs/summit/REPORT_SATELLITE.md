# FishIntel Satellite & Remote-Sensing Source Report

> Session 40 research. Every number below is cited inline; vendor prices that are
> not published are marked **contact sales** rather than guessed. Raw captures in
> `docs/raw/`.

## Executive Summary — Top 5 Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **Optical backbone = Sentinel-2 L2A via CDSE Sentinel Hub (free tier)** | Official quota: **10,000 requests + 10,000 PU per month** on Sentinel Hub APIs for Copernicus General Users ([CDSE Quotas](https://documentation.dataspace.copernicus.eu/Quotas.html)). S3/STAC access for bulk: 2,000 req/min, 12 TB/month. Revisit ~5 days at 10 m. `SENTINEL_HUB_CLIENT_ID/SECRET` already in `.env.example`. |
| D2 | **Ocean physics/currents/SST = MET.no NorKyst800 v3 THREDDS (free)** | "Norkyst is the primary tool for ocean forecasting along the Norwegian coast" — analysis runs + 5-day forecasts on [thredds.met.no/fou-hi/norkystv3](https://thredds.met.no/thredds/catalog/fou-hi/norkystv3.html), hindcast **2012→present**, plus 160 m nests for Oslofjorden/Sulafjorden ([ocean.met.no/models](https://ocean.met.no/models)). The repo already has a `norkyst_client`; the separate CMEMS fetch in `ocean_currents.py` is failing on a stale dataset ID (see §5 Fix List). |

## 1. Free / Open Sources (verified quotas)

### 1.1 Copernicus Data Space Ecosystem (CDSE) — official free-tier quotas
Source: [documentation.dataspace.copernicus.eu/Quotas.html](https://documentation.dataspace.copernicus.eu/Quotas.html) (monthly, reset 1st of month)

| API surface | Requests/month | Req/min | PU/month | PU/min | Notes |
|---|---|---|---|---|---|
| Sentinel Hub APIs | 10,000 | 300 | 10,000 | 300 | Digital, Statistical, Process, WMS/WMTS |
| Direct HTTP to COGs | 50,000 | — | — | — | Direct Cloud-Optimized GeoTIFF access |
| S3/OData/STAC | unlimited* | 2,000 | — | — | 12 TB/30-day transfer, 20 MB/s per conn, 4 concurrent |
| openEO | — | 12 | — | — | 10,000 credits/mo (temporary boost), 2 concurrent |
| Data Workspace | — | — | 25 processed products/mo | — | 0.1 TB |

*Token rules: access token lives 10 min, refreshable up to 60 min; **do not fetch a token per request** — the token endpoint is rate-limited ([CDSE auth docs](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html)).

**Auth (already wired in repo env):**
```
POST https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token
grant_type=client_credentials&client_id=..&client_secret=..   # OAuth client from shapps.dataspace.copernicus.eu dashboard
API base: https://sh.dataspace.copernicus.eu
```

**Sensors:** Sentinel-2 MSI (10 m optical, L2A BOA), Sentinel-1 C-SAR (all-weather, GRD/SLC), Sentinel-3 OLCI/SLSTR (ocean colour, SST), Sentinel-5P (NO₂/CH₄, coarse). License: free and open, including commercial use, with attribution (Copernicus regulation) — verify attribution text per product family before shipping derived analytics.

### 1.2 MET Norway ocean models (free, operational archive on THREDDS)
Source: [ocean.met.no/models](https://ocean.met.no/models)

| Model | Domain | Resolution | Access | Use for FishIntel |
|---|---|---|---|---|
| **Norkyst v3** | Norwegian coast + fjords | 800 m | [THREDDS operational](https://thredds.met.no/thredds/catalog/fou-hi/norkystv3.html) | Currents, SST per site/PA |
| Norkyst-DA | Data assimilated analysis | 2.4 km, 42 layers | same THREDDS | Best-available analysis fields |
| Norkyst hindcast 2012→ | Historical free run | 800 m | [THREDDS hindcast](https://thredds.met.no/thredds/catalog/romshindcast/norkyst_v3/catalog.html) | Backtesting, climatology |
| Oslofjorden/Sulafjorden nests | Fjord detail | **160 m** | same THREDDS | Farm-level current detail |
| Barents-2.5 | Barents/Svalbard | 2.5 km, 24-member ensemble | [THREDDS](https://thredds.met.no/thredds/catalog/fou-hi/barents_eps.html) | Northern sites, sea ice |
| Nordic4 stormsurage | Nordic seas | 4 km, 120 h | [api.met.no tidalwater/1.1](https://api.met.no/weatherapi/tidalwater/1.1/documentation) | Storm-surge risk |
| TOPAZ (via CMEMS) | Pan-Arctic | ~6 km / 3 km tide | CMEMS product IDs below | Arctic currents/tides |

### 1.3 Copernicus Marine (CMEMS) — free with registration

## 2. Commercial Sources (published prices only)

| Vendor | Product | Published price | Source | Fit for FishIntel |
|---|---|---|---|---|
| Sentinel Hub (via CREODIAS) | Exploration (non-commercial!) | **300 EUR/yr** — 30k PU, 100k requests/mo | [creodias.eu/pricing/sh-pricing](https://creodias.eu/pricing/sh-pricing/) | ⚠️ non-commercial licence — NOT usable for our commercial product |
| Sentinel Hub (via CREODIAS) | **Basic (commercial)** | **999 EUR/yr** — 70k PU, 700k requests/mo, 500 req/min | same | Entry paid tier when free 10k req/mo is exceeded |
| Sentinel Hub (via CREODIAS) | Enterprise-S | **5,000 EUR/yr** — 400k PU, 800k requests/mo | same | Scale tier (multiple high-cadence sites) |
| Sentinel Hub (via CREODIAS) | Enterprise-L | **10,000 EUR/yr** — 1M PU, 10M requests/mo | same | Full Norway + neighbour markets |
| SkyFi (reseller) | Optical archive/tasking | **from $15** per scene | [skyfi.com/en/pricing](https://skyfi.com/en/pricing) | Ad-hoc high-res optical; pay-as-you-go |
| SkyFi (reseller) | **SAR imagery** (ICEYE US Direct, Capella) | **from $450** per scene | same | Storm/wave events, all-weather verification |
| SkyFi | Analytics add-ons | from $5 | same | Change detection (competitor cages, infra) |
| SkyFi | Aerial | from $35 | same | Ultra-high-res site imagery |
| ICEYE (direct) | SAR tasking via ICAS API | region-based pricing model, integrated tasking prices via API; **contact sales** for rate card | [docs.iceye.com pricing-model](https://docs.iceye.com/constellation/api/1.0/tasking/pricing-model/) | Enterprise SAR program |
| ICEYE | SAR archive (CC-BY subset) | **free (18,000 images, CC licence)** | [ICEYE press release](https://www.iceye.com/newsroom/press-releases/iceye-shares-nearly-18000-satellite-image-archive-under-creative-commons-license) | Free SAR sample library for algorithm dev |
| Planet | PlanetScope monitoring / SkySat tasking / Pelican | **contact sales** (self-service purchasing exists for small customers — see [self-service announcement](https://www.planet.com/pulse/planet-enables-self-service-purchasing-for-small-customers-on-planet-insights-platform/)) | [planet.com/pricing](https://www.planet.com/pricing/) | Daily 3 m monitoring (cage/boat activity, infrastructure) |
| GHGSat | Site-level methane/CO₂ monitoring | **subscription per monitored site — contact sales** | [ghgsat.com](https://www.ghgsat.com/); model confirmed by [independent AGU evaluation](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023JD039906) | CSRD/ESG scope-1 story for enterprise tier |
| KSAT | Acquisition-as-a-service (Ground segment) | contact sales | — | Ground-tracking partnerships (not data itself) |

**Honest cost path for a commercial product:**

## 3. Use-Case Matrix (source → product → effort → licence)

| FishIntel use case | Primary source | Product | Integration effort | Licence note |
|---|---|---|---|---|
| Sea temperature per site/PA (lice generation-time proxy) | MET.no NorKyst800 v3 (+ PACE/S3 SST validation) | SST time series, anomaly vs 30-yr baseline | **Already implemented** (`norkyst_client`) | Free, attribution |
| Currents for de-licing/medication timing | Norkyst v3 (800 m), Sulafjorden/Oslofjord nests (160 m) | u/v current vectors, 5-day forecast | ~4 h (extend existing client) | Free, attribution |
| Marine heatwave detection | PACE/S3 SST + repo `marine_heatwave` engine | Hobday-category events | **Implemented** | Free |
| HAB / algal bloom risk | NASA PACE OCI chlorophyll + S-3 OLCI | Chl-a concentration, bloom index | **Implemented** (`nasa_pace_client`); add S3 OLCI fallback ~3 h | Free |
| Storm/wave damage risk | CMEMS WAM wave fields + MET.no stormsurge | Hs, Tp, direction, surge height | ~6 h new client (CMEMS client exists to copy) | Free |
| Cage/biofouling/boat activity visible evidence | Sentinel-2 L2A (10 m, 5-day) + SkyFi tasking on demand | True-colour + NIR crops of sites | ~8 h (new `cdse_client` using existing OAuth keys) | Free (S2); paid (tasking) |
| Infrastructure change detection (competitor capacity) | SkyFi optical archive / S2 time series | Before/after composites | ~6 h | Mixed |
| Methane/ESG (CSRD) | GHGSat (paid) / Sentinel-5P (coarse, free) | Site-level CH₄ | ~4 h (5P is coarse: PA-level only) | Free (5P) / subscription (GHGSat) |
| **Direct sea-lice detection** | ❌ not physically possible (lice are mm-scale) | — | — | Feeds through proxies above (SST, currents, salinity). **Be explicit in marketing.** |

## 4. Data Honesty Notes (platform brand promise)
1. Satellite metrics are **proxies** for risk, not direct measurements of lice/infection.
2. Every satellite-derived number must carry `DataProvenance` with source, sensor, scene date, cloud-cover %, and the processing level (L1/L2A).
3. Attribution requirements: Copernicus ("Contains modified Copernicus Sentinel data 2026"), NASA, MET.no (NLOD licence) — surface in API `source` fields and UI footers.
4. Cloud cover in Norway: optical gaps Oct–Mar are the norm — the product must state "last clear scene: <date>" rather than imply daily coverage (SAR covers this gap).

## 5. Fix List (from this research)

| # | Repo issue found | Fix |
|---|---|---|
| F1 | `core/market/ocean_currents.py` fetches CMEMS dataset `cmems_mod_nok_phy_anfc_nordic_P1D-m` → live-fails "Please check that the dataset exists" | Replace with either (a) Norkyst v3 THREDDS (preferred — same source as `norkyst_client`, 800 m), or (b) CMEMS `GLOBAL_ANALYSISFORECAST_PHY_001_024` subset. Verify the ID in the CMEMS catalogue UI before coding. |
| F2 | No wave/storm data anywhere in platform | Add `cmems_wave_client` (WAM Hs/Tp) ~6 h using the same auth pattern as `met_ocean.py`. |
| F3 | CDSE keys in `.env.example` may be unused | Audit `sentinel_client` vs `.env.example`; wire the CDSE OAuth flow with a **cached token** (10-min TTL, refresh ≤60 min; never re-auth per request — token endpoint is rate-limited). |
| F4 | PACE client exists but no fallback for cloudy days | Add S-3 OLCI daily composite fallback (free, 300 m) — ~3 h. |

## 6. Open Questions (with verification URL)
1. Exact current CMEMS dataset ID for Norwegian coastal physics — check in the [CMEMS catalogue](https://data.marine.copernicus.eu/products) with the account; confirm before F1 implementation.
2. Sentinel-2 revisit for a specific farm AOI (cloud-adjusted) — quantify with the CDSE Statistical API during Phase 3 (consumes from the 10k free requests).
3. Planet/ICEYE price cards remain **contact sales**; pursue only if enterprise clients request daily sub-3 m monitoring.
4. KSAT/ground-station angle — relevant only if we later fly our own sensors; park.

## Sources Index (raw captures)
- `docs/raw/cdse_quotas.md` — official free-tier quotas
- `docs/raw/cdse_auth.md` — OAuth client-credentials flow + endpoints
- `docs/raw/ocean_metno_models.md` — Norkyst v3 / Barents / TOPAZ / stormsurge details
- `docs/raw/sentinel_hub_pricing.md` — CREODIAS Sentinel Hub price table (EUR)
- `docs/raw/skyfi_pricing.md` — SkyFi starting prices ($15/$450/$35/$5)
- `docs/raw/planet_pricing.md` — Planet pricing page capture (contact-sales model)
- `docs/raw/iceye_skyfi.md` — ICEYE US Direct pay-as-you-go ordering flow

- **Now (free)**: CDSE free tier (10k req/mo) + MET.no THREDDS + CMEMS + NASA. Sufficient for ~30-60 PA-scale queries/day with tile caching.
- **First revenue (>€50/user/mo)**: Sentinel Hub Basic **999 EUR/yr** covers 700k requests ≈ 19k/day — headroom for full Norway coverage at 5-day cadence.
- **Enterprise add-ons**: SkyFi SAR per-incident ($450/scene — charge per storm report), Planet contact-sales for premium monitoring, GHGSat for ESG.

- `ARCTIC_ANALYSISFORECAST_PHY_002_001` — 10-day Arctic physics forecast (surface + 3D), [product page](https://data.marine.copernicus.eu/product/ARCTIC_ANALYSISFORECAST_PHY_002_001/description)
- `ARCTIC_ANALYSISFORECAST_PHY_TIDE_002_015` — 3 km tides + surface currents, 15-min output ([resources.marine.copernicus.eu](https://resources.marine.copernicus.eu/?option=com_csw&view=details&product_id=ARCTIC_ANALYSISFORECAST_PHY_TIDE_002_015))
- `GLOBAL_ANALYSISFORECAST_PHY_001_024` — 1/12° global physics incl. Norwegian coast ([product page](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description))
- Waves: WAM-based `GLOBAL_ANALYSISFORECAST_WAV_001_027` (significant wave height, period, direction)
- Reanalysis: WAVERYS (global waves 1993→), GLORYS12V1 (physics)

### 1.4 NASA Earthdata — PACE & ocean colour (free)
- PACE OCI: hyperspectral ocean colour → chlorophyll-a, Rrs, HAB-relevant bands. Access: Earthdata Login + [`earthaccess`](https://www.earthdata.nasa.gov/learn/data-recipes/access-data-from-ocean-color-instrument-oci) (Python). Also [Worldview](https://pace.oceansciences.org/access_pace_data.htm) for visual QA.
- VIIRS/MODIS: coarser but long-history ocean colour + SST.
- License: NASA open data (free, commercial use OK with attribution).

| D3 | **Waves/storm = CMEMS WAM (free) + MET.no stormsurge** | CMEMS free with registration; Arctic physics via `ARCTIC_ANALYSISFORECAST_PHY_002_001`, 3 km tides+currents via `ARCTIC_ANALYSISFORECAST_PHY_TIDE_002_015` (both linked from ocean.met.no). Storm surge forecast via `api.met.no/weatherapi/tidalwater/1.1` (free). |
| D4 | **Ocean colour / HAB = NASA PACE OCI via `earthaccess` (free)** | Earthdata Login required; `earthaccess` handles auth. Repo already integrates PACE (`nasa_pace_client`). Sources: [PACE data access](https://pace.oceansciences.org/access_pace_data.htm), [OCI Earthdata recipe](https://www.earthdata.nasa.gov/learn/data-recipes/access-data-from-ocean-color-instrument-oci). |
| D5 | **Commercial escalation path only on revenue justification** | Sentinel Hub paid entry **999 EUR/yr (Basic: 70k PU + 700k requests/mo)** via CREODIAS; SAR pay-as-you-go **from $450/scene** via SkyFi; Planet/ICEYE/GHGSat = contact-sales subscriptions. Nothing purchased in this session. |
