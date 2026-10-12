"""
FishIntel MCP Server
====================
Exposes the core aquaculture intelligence capabilities to external AI agents
(Claude, GitHub Copilot, etc.) via the Model Context Protocol (MCP).

Usage:
    mcp dev core/mcp_server.py
"""
import asyncio
from mcp.server.mcpserver import MCPServer

# Create the MCP server
mcp = MCPServer("FishIntel")

@mcp.tool()
async def get_morning_brief() -> dict:
    """Get the daily salmon market intelligence brief, including prices, lice risk, and bloom alerts."""
    from core.routers.analytics_routes import morning_brief
    return await morning_brief()

@mcp.tool()
async def get_salmon_price_outlook(horizon_weeks: int = 4) -> dict:
    """
    Get ML ensemble price prediction for Norwegian salmon with conformal uncertainty bands.
    Args:
        horizon_weeks: Number of weeks to forecast into the future (2 to 20).
    """
    from core.routers.market_routes import price_outlook
    return await price_outlook(horizon=horizon_weeks, scenarios=100)

@mcp.tool()
async def get_national_lice_summary() -> dict:
    """Get the latest national salmon lice aggregate statistics for Norway."""
    from core.routers.lice_routes import lice_summary
    return await lice_summary()

@mcp.tool()
async def get_causal_insights(max_lag: int = 8) -> dict:
    """
    Get causal inference insights (Granger causality & Transfer Entropy) 
    explaining the lag between sea lice outbreaks and spot price impact.
    """
    from core.routers.causal_routes import causal_summary
    return await causal_summary(max_lag=max_lag)

@mcp.tool()
async def get_feed_cost_index() -> dict:
    """Get the FishIntel composite feed cost index and Peru anchovy quota status."""
    from core.routers.feed_cost_routes import feed_cost_composite_index
    return await feed_cost_composite_index(years=1)

@mcp.tool()
async def get_regulatory_traffic_light() -> dict:
    """Get the current Norwegian traffic light system status (green/yellow/red) per Production Area."""
    from core.routers.misc_routes import traffic_light_current
    return await traffic_light_current()
