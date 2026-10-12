---
name: satellite-research
description: Refresh and extend the FishIntel satellite/remote-sensing source report (docs/summit/REPORT_SATELLITE.md). Use when researching satellite data access, costs, quotas, vendors, or integrating new EO sources (Sentinel, MET.no, CMEMS, NASA, Planet, ICEYE).
---

# Satellite Research (FishIntel)

## Workflow

1. **Research via the repo helper** (reads `FIRECRAWL_API_KEY` from `.env`):
   ```bash
   python scripts/firecrawl_research.py search "<query>" --limit 6
   python scripts/firecrawl_research.py scrape "<url>" --out docs/raw/<name>.md
   ```
   Prefer official agency/vendor docs over blogs. Save every capture you cite.
2. **Update** `docs/summit/REPORT_SATELLITE.md`:
   - every number keeps an inline source URL; if a vendor does not publish
     pricing, write **contact sales** — never invent a price;
   - new sources go into the correct table (§1 free / §2 commercial) and get a
     row in the use-case matrix (§3) with effort estimate and licence note.
3. **Data honesty** (see the `data-honesty` skill): satellite outputs are
   risk PROXIES (SST, chlorophyll, currents, waves) — never claim direct
   sea-lice detection. Always carry scene date + cloud cover in provenance.

## Canonical sources (verified Session 40)

| Source | What | Access |
|---|---|---|
| CDSE Sentinel Hub | Sentinel-1/2/3/5P | OAuth client-credentials; 10k req + 10k PU/mo free ([Quotas](https://documentation.dataspace.copernicus.eu/Quotas.html)) |
| MET.no NorKyst v3 | Coast currents + SST, 800 m, hindcast 2012→ | `thredds.met.no/thredds/catalog/fou-hi/norkystv3.html` (free) |
| CMEMS | Arctic physics/tide, global WAM waves | `data.marine.copernicus.eu` (free w/ registration) |
| NASA PACE | Hyperspectral ocean colour | `earthaccess` + Earthdata Login (free) |
| Sentinel Hub paid | 999 EUR/yr Basic commercial | creodias.eu/pricing/sh-pricing |
| SkyFi | SAR from $450/scene, optical from $15 | skyfi.com/en/pricing |
| Planet MCPs | Docs MCP `https://planet.mcp.kapa.ai`; `pip install planet-mcp` | planet.com/pulse |

## Rules

- Free-first: any paid recommendation must state the trigger condition (e.g.
  exceeding CDSE's 10k requests/month) and include the annualised cost.
- Never re-request CDSE tokens per call — cache (10-min TTL) and refresh.
- New integrations ship with a `DataProvenance` source string including the
  sensor and processing level (e.g. "Sentinel-2 L2A, scene 2026-10-01, 4% cloud").
