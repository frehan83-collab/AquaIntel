# MCP Setup — FishIntel

> Session 40 research (inline; agents backend was unavailable). All install
> commands and packages below verified against vendor docs July–Oct 2026.

## Current state on this machine

| Location | Contents today |
|---|---|
| `~/.mcp.json` (Claude Code, user scope) | 1 server: `hexstrike-ai` (pentest — unrelated project) |
| Cline MCP config | **not created yet** — open Cline → MCP Servers → Configure to create it (file: `cline_mcp_settings.json`) |
| Repo `.mcp.json` | created in this session (commit) — Claude Code project scope + reference for any MCP client |

## Recommended set (top 5)

| # | Server | Why FishIntel needs it | Install |
|---|---|---|---|
| 1 | **firecrawl-mcp** (official) | Research/scrape for satellite-source updates, competitor intel, price pages. Our key already works via `scripts/firecrawl_research.py`. | `npx -y firecrawl-mcp` (v3.23.7+), env `FIRECRAWL_API_KEY` |
| 2 | **Playwright MCP** (Microsoft) | Drive the Next.js app for e2e + visual-regression + screenshot workflows across 63 routes. | `npx @playwright/mcp@latest` |
| 3 | **Context7** (Upstash) | Version-correct docs for Next 15/React 19/FastAPI libs while coding. | `npx -y @upstash/context7-mcp` |
| 4 | **Planet Documentation MCP** | Grounded answers about Sentinel Hub/Planet imagery APIs during satellite integration — hosted, no install. | URL server: `https://planet.mcp.kapa.ai` |
| 5 | **Planet Platform MCP** (when we get a Planet account) | Catalog search, image preview, ordering from the agent (requires Planet account). | `pip install planet-mcp` (Python 3.11+) then `planet auth login` |

## Verified install commands & notes

- **firecrawl-mcp** — official repo [github.com/firecrawl/firecrawl-mcp-server](https://github.com/firecrawl/firecrawl-mcp-server); local docs [docs.firecrawl.dev/mcp-server/local](https://docs.firecrawl.dev/mcp-server/local). `env FIRECRAWL_API_KEY=fc-... npx -y firecrawl-mcp@3.23.7`.
- **Playwright MCP** — [playwright.dev/docs/getting-started-mcp](https://playwright.dev/docs/getting-started-mcp): `command: npx, args: ["@playwright/mcp@latest"]`.
- **Context7** — [github.com/upstash/context7](https://github.com/upstash/context7) / [@upstash/context7-mcp](https://www.npmjs.com/package/@upstash/context7-mcp).
- **Planet MCPs** — [planet.com/pulse/what-is-the-planet-mcp](https://www.planet.com/pulse/what-is-the-planet-mcp-and-how-do-i-install-and-use-it/): docs MCP URL `https://planet.mcp.kapa.ai`; platform MCP `pip install planet-mcp` + `planet auth login`.

## Geospatial MCP landscape (for satellite work)

- **Registry**: [sparkgeo/geo-mcp-servers](https://github.com/sparkgeo/geo-mcp-servers) — 77+ curated geospatial/GIS/STAC MCP servers ([blog](https://sparkgeo.com/blog/geospatial-mcp-servers-mapped-and-categorized/)).
- **STAC MCP** ([mcpmarket.com/server/stac](https://mcpmarket.com/server/stac)) — geospatial data discovery/access via STAC catalogs (CDSE exposes STAC → usable for Sentinel discovery queries).
- **Esri Geoportal Server 3.1+** ships an MCP API for STAC ([Esri community](https://community.esri.com/en/discussion/1703939/announcing-esri-geoportal-server-catalog-3-1-0)) — enterprise GIS angle.
- No dedicated "Sentinel Hub MCP" found; the practical path for CDSE is our Python client + firecrawl for docs.

## Honorable mentions (not in top 5, evaluated)

| Server | Verdict |
|---|---|
| GitHub MCP | Useful for PR/CI ops on `frehan83-collab/AquaIntel` (master branch). Add when the CI badge workflow matures. Needs PAT. |
| postgres MCP | Only once we run PG/Timescale in dev; community successors vary — re-evaluate at adoption time. No maintained sqlite MCP found; SQLite-first today. |
| Stripe MCP | Test-mode keys only; valuable when billing E2E work starts. |
| Sentry MCP | Only if Sentry is adopted (Phase 4 observability decision). |
| memory / knowledge-graph MCP | Skip — repo has `memory/` + `docs/` conventions; duplicating them invites drift. |

## The differentiator: ship our own `fishintel-mcp`

No competitor exposes their aquaculture intelligence as MCP. A thin server wrapping our public API (`/api/lice/summary`, `/api/market/*`, `/api/causal/*`, `/api/brief`, provenance envelopes) lets any LLM client (Claude, Copilot, ChatGPT) query live salmon intelligence — a distribution channel as much as a feature.

**Implemented (Session 40)**: `core/mcp_server.py` using the official `mcp`
package (`mcp.server.mcpserver.MCPServer` — FastMCP is renamed to MCPServer in
mcp 2.x). Six tools: morning brief, price outlook, national lice summary,
causal insights, feed cost index, regulatory traffic light.

```bash
# Smoke (import + tool registration, exits)
python -c "from core.mcp_server import mcp; print('MCP server ready')"

# Client config entry for this repo (stdio transport):
#   "fishintel": { "command": "python", "args": ["-m", "core.mcp_server"] }
```

## Config snippets

### Cline (`cline_mcp_settings.json` — open via Cline → MCP Servers → Configure)
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "fc-..." },
      "disabled": false
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "disabled": false
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "disabled": false
    },
    "planet-docs": { "url": "https://planet.mcp.kapa.ai", "disabled": false }
  }
}
```
Windows note: if Cline reports spawn errors with `npx`, use
`"command": "cmd", "args": ["/c", "npx", "-y", "firecrawl-mcp"]`
(classic Cline-on-Windows workaround).

### Claude Code (repo `.mcp.json` — committed; supports `${VAR}` expansion)
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" }
    },
    "playwright": { "command": "npx", "args": ["@playwright/mcp@latest"] },
    "context7": { "command": "npx", "args": ["-y", "@upstash/context7-mcp"] },
    "planet-docs": { "type": "http", "url": "https://planet.mcp.kapa.ai" }
  }
}
```

## Not enabled in this session (reasons)
1. Restart of the IDE is required to pick up MCP servers — deferred to the user.
2. The Cline MCP settings file does not exist yet on this box; the first save happens through the Cline UI.
3. `planet-mcp` requires a Planet account (currently contact-sales) — revisit with the satellite roadmap.


Skeleton (~150 lines, `mcp` Python SDK):
```python
from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("fishintel")
BASE = "https://api.fishintel.no"  # or localhost:8000

@mcp.tool()
async def salmon_spot_price() -> dict:
    """Live salmon spot price (NOK/kg) with provenance."""
    async with httpx.AsyncClient() as c:
        return (await c.get(f"{BASE}/api/market/spot-price")).json()

# ... one tool per high-value endpoint; keep <12 tools
```
