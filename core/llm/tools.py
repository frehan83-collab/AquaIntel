"""
LLM Tool Definitions for Agentic RAG
======================================
Defines tools the LLM can call during multi-turn conversations
to fetch live data from OpenClaw's market engines.

Each tool has:
  - name: identifier for the tool
  - description: what the tool does (shown to LLM)
  - parameters: JSON schema for inputs
  - handler: async function that returns data
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


async def get_lice_data(pa: int | None = None, company: str | None = None) -> dict:
    """Fetch current lice levels, trends, threshold status."""
    try:
        from core.market.farm_graph import farm_graph
        summary = await farm_graph.get_summary()
        result = {
            "avg_lice": summary.get("avg_lice", 0),
            "n_farms": summary.get("n_farms", 0),
            "n_above_threshold": summary.get("n_above_threshold", 0),
            "clusters": summary.get("n_clusters", 0),
        }
        if company:
            exposure = farm_graph.get_company_exposure()
            for co in (exposure if isinstance(exposure, list) else []):
                if company.lower() in (co.get("company", "") or "").lower():
                    result["company_exposure"] = co
                    break
        return result
    except Exception as e:
        return {"error": str(e)[:100]}


async def get_price_outlook(horizon: int = 4) -> dict:
    """Fetch price forecast from ML ensemble."""
    try:
        from core.market.price_ml import price_predictor
        outlook = price_predictor.predict(horizon_weeks=horizon)
        return {
            "current_spot_nok": outlook.get("current_spot_nok", 0),
            "predicted_nok": outlook.get("predicted_nok", 0),
            "direction": outlook.get("direction", "neutral"),
            "confidence": outlook.get("confidence", 0),
            "signals": outlook.get("signals", {}),
            "bands": outlook.get("bands", {}),
        }
    except Exception as e:
        return {"error": str(e)[:100]}


async def get_disease_status() -> dict:
    """Fetch active disease outbreaks from Mattilsynet."""
    try:
        from core.market.mattilsynet_client import mattilsynet_client
        cases = await mattilsynet_client.fetch_disease_cases()
        isa_count = sum(1 for c in cases if "ISA" in (c.get("disease", "") or "").upper())
        pd_count = sum(1 for c in cases if "PD" in (c.get("disease", "") or "").upper())
        return {
            "total_outbreaks": len(cases),
            "isa_cases": isa_count,
            "pd_cases": pd_count,
            "recent": [{"disease": c.get("disease"), "location": c.get("location"), "date": c.get("date")} for c in cases[:5]],
        }
    except Exception as e:
        return {"error": str(e)[:100]}


async def get_farm_network_risk(locality_no: int | None = None) -> dict:
    """Fetch farm network cluster risk assessment."""
    try:
        from core.market.farm_graph import farm_graph
        if locality_no:
            detail = farm_graph.get_farm_detail(locality_no)
            return detail if isinstance(detail, dict) else {"farm": locality_no, "data": str(detail)[:200]}
        clusters = farm_graph.get_clusters(risk_level="high")
        return {
            "high_risk_clusters": len(clusters) if isinstance(clusters, list) else 0,
            "clusters": (clusters if isinstance(clusters, list) else [])[:5],
        }
    except Exception as e:
        return {"error": str(e)[:100]}


async def get_supply_forecast(months: int = 6) -> dict:
    """Fetch supply pipeline forecast from smolt model."""
    try:
        from core.valuechain.smolt_model import smolt_model
        balance = smolt_model.get_demand_balance()
        pipeline = smolt_model.get_supply_pipeline(months)
        return {
            "price_pressure": balance.get("price_pressure", "neutral"),
            "balance_tonnes": balance.get("balance_tonnes", 0),
            "signal": balance.get("signal", "balanced"),
            "next_months": pipeline[:3] if pipeline else [],
        }
    except Exception as e:
        return {"error": str(e)[:100]}


async def search_knowledge_base(query: str) -> dict:
    """Search the internal knowledge base using RAG retrieval."""
    try:
        from core.llm.rag import rag_retriever
        results = rag_retriever.search(query, top_k=3)
        return {
            "results": [{"title": r.get("title", ""), "content": r.get("content", "")[:300]} for r in results] if isinstance(results, list) else [{"content": str(results)[:500]}],
        }
    except Exception as e:
        return {"error": str(e)[:100]}


# ── Tool Registry ───────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_lice_data",
        "description": "Fetch current sea lice levels, farm network status, and threshold exceedance data. Can filter by production area or company.",
        "parameters": {
            "type": "object",
            "properties": {
                "pa": {"type": "integer", "description": "Production area number (1-13)"},
                "company": {"type": "string", "description": "Company name to filter by"},
            },
        },
        "handler": get_lice_data,
    },
    {
        "name": "get_price_outlook",
        "description": "Fetch salmon price forecast from the ML ensemble model, including direction, confidence, and signal breakdown.",
        "parameters": {
            "type": "object",
            "properties": {
                "horizon": {"type": "integer", "description": "Forecast horizon in weeks (default 4)"},
            },
        },
        "handler": get_price_outlook,
    },
    {
        "name": "get_disease_status",
        "description": "Fetch active disease outbreaks (ISA, PD) from Norwegian Food Safety Authority (Mattilsynet).",
        "parameters": {"type": "object", "properties": {}},
        "handler": get_disease_status,
    },
    {
        "name": "get_farm_network_risk",
        "description": "Fetch farm network cluster risk from the hydrodynamic lice spread model. Can look up specific farms.",
        "parameters": {
            "type": "object",
            "properties": {
                "locality_no": {"type": "integer", "description": "Specific farm locality number"},
            },
        },
        "handler": get_farm_network_risk,
    },
    {
        "name": "get_supply_forecast",
        "description": "Fetch supply-demand balance and price pressure signal from the smolt-to-harvest model.",
        "parameters": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "Forecast horizon in months (default 6)"},
            },
        },
        "handler": get_supply_forecast,
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the aquaculture knowledge base for regulatory frameworks, scientific literature, and domain knowledge.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        "handler": search_knowledge_base,
    },
]

# Quick lookup
TOOL_MAP = {t["name"]: t for t in TOOLS}
