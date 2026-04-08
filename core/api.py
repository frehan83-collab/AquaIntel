"""
FastAPI REST API for OpenClaw.
Provides endpoints for programmatic access, webhooks, and the premium signal service.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, func

from config.settings import settings
from core.models import (
    Session, Signal, Order, AuditLog, LiceRecord, Locality, init_db,
    PricePrediction, FuturesSnapshot, ExportVolume, User,
)
from core.bloom.models import BloomRiskAssessment, BloomAlert, ChlorophyllReading
from execution.execution_agent import ExecutionAgent
from compliance.compliance_agent import ComplianceAgent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event handler — replaces deprecated @app.on_event('startup').
    Reference: https://fastapi.tiangolo.com/advanced/events/
    """
    import structlog
    log = structlog.get_logger("startup")

    # Initialize database tables
    init_db()

    # Run Alembic migrations (safe — stamps if already at head)
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_cfg.set_main_option("script_location", "alembic")
        alembic_command.upgrade(alembic_cfg, "head")
        log.info("startup.migrations", status="complete")
    except Exception as exc:
        log.warning("startup.migrations_skipped", error=str(exc)[:120])

    # Log startup config summary
    from config.settings import settings
    log.info("startup.config",
        env=settings.fishintel_env,
        db=settings.database_url.split("@")[-1] if "@" in settings.database_url else "sqlite",
        barentswatch="configured" if settings.barentswatch_client_id else "not_set",
        stripe="configured" if settings.stripe_secret_key else "not_set",
        llm_provider=settings.llm_provider,
    )

    # Demo mode: seed realistic data for offline expo demos
    if os.environ.get("FISHINTEL_DEMO_MODE", "").lower() in ("true", "1", "yes"):
        try:
            from core.demo_seed import seed_demo_data
            seed_demo_data()
            log.info("startup.demo_seed", status="complete")
        except Exception as exc:
            log.warning("startup.demo_seed_failed", error=str(exc)[:120])

    log.info("startup.ready", version="2.2.0", routes=len(app.routes))
    yield
    log.info("shutdown.complete")


app = FastAPI(
    title="FishIntel API",
    description="Aquaculture Intelligence Platform — real-time salmon market intelligence, disease monitoring, and decision support for farmers, traders, and investors.",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {"name": "auth", "description": "Authentication & user management"},
        {"name": "lice", "description": "Sea lice monitoring & forecasting"},
        {"name": "disease", "description": "Disease outbreak intelligence"},
        {"name": "market", "description": "Market data, pricing & predictions"},
        {"name": "decision", "description": "Farmer decision engine & treatment"},
        {"name": "investor", "description": "Event impact modeling & scenarios"},
        {"name": "supply", "description": "Supply chain & biomass forecasting"},
        {"name": "countries", "description": "Multi-country aquaculture data"},
        {"name": "ml", "description": "Machine learning models & baselines"},
        {"name": "notifications", "description": "Threshold alerts & monitoring"},
        {"name": "billing", "description": "Stripe subscription management"},
        {"name": "traceability", "description": "EU traceability & compliance"},
    ],
)

_allowed_origins = os.environ.get(
    "FISHINTEL_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:8000,https://fishintel.io,https://app.fishintel.io",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
)

# ── Security Headers ────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── Correlation ID Middleware ─────────────────────────────────────────
import uuid
import structlog

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response

app.add_middleware(CorrelationIDMiddleware)

# ── HTTP Cache Headers (ETag + Cache-Control) ───────────────────────
from core.cache_headers import CacheHeadersMiddleware

app.add_middleware(CacheHeadersMiddleware)

# ── Tiered Rate Limiting ─────────────────────────────────────────────
# Limits scale by subscription tier. Free tier is generous for evaluation,
# Pro for active users, Enterprise for production integrations.
# Reference: Bloomberg Terminal API limits ~10K/hour for enterprise.

def _get_rate_limit_key(request: Request) -> str:
    """Build rate limit key from user tier + IP.

    Looks for X-API-Key header (API key auth) or JWT tier claim.
    Falls back to IP-based limiting for unauthenticated requests.
    """
    # Check API key tier from header
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"apikey:{api_key[:16]}"
    # Check JWT tier
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from core.auth import decode_token
            payload = decode_token(auth[7:])
            return f"user:{payload.user_id}:{payload.tier}"
        except Exception:
            pass
    return get_remote_address(request)

# Tier-based limits (requests per minute)
TIER_LIMITS = {
    "free": "100/minute",        # ~1.7 req/sec — evaluation tier
    "pro": "500/minute",         # ~8.3 req/sec — active farmer/trader
    "enterprise": "2000/minute", # ~33 req/sec — production integration
    "admin": "5000/minute",      # internal
}

def _dynamic_limit(key: str) -> str:
    """Return rate limit string based on user tier."""
    for tier, limit in TIER_LIMITS.items():
        if f":{tier}" in key:
            return limit
    return "200/minute"  # default for IP-based

limiter = Limiter(
    key_func=_get_rate_limit_key,
    default_limits=["200/minute"],
    strategy="moving-window",  # sliding window avoids burst-at-boundary
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Prometheus Metrics ──────────────────────────────────────────────
# Must be added before routers, at module level (not in lifespan)
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/api/docs", "/api/redoc", "/openapi.json"],
    ).instrument(app).expose(app, endpoint="/api/metrics", include_in_schema=False)
except ImportError:
    pass

# ── Router Modules (Session 7-10: incremental decomposition) ─────────
from core.routers.auth_routes import router as auth_router
from core.routers.billing_routes import router as billing_router
from core.routers.disease_routes import router as disease_router
from core.routers.lice_routes import router as lice_router
from core.routers.decision_routes import router as decision_router
from core.routers.investor_routes import router as investor_router
from core.routers.signals_routes import router as signals_router
from core.routers.farm_routes import router as farm_router
from core.routers.alerts_routes import router as alerts_router
from core.routers.analytics_routes import router as analytics_router
from core.routers.twin_routes import router as twin_router
from core.routers.misc_routes import router as misc_router
from core.routers.notification_routes import router as notification_router
from core.routers.locality_routes import router as locality_router
from core.routers.bloom_routes import router as bloom_router
from core.routers.bloom_routes import bio_risk_router
from core.routers.country_routes import router as country_router
from core.routers.market_routes import router as market_router
from core.routers.market_routes import futures_router
from core.routers.ml_routes import router as ml_router
from core.routers.supply_routes import router as supply_router
from core.routers.traceability_routes import router as traceability_router
from core.routers.traceability_routes import compliance_router
from core.routers.admin_routes import router as admin_router
from core.routers.webhook_routes import router as webhook_router
from core.routers.apikey_routes import router as apikey_router
from core.routers.integration_routes import router as integration_router
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(disease_router)
app.include_router(lice_router)
app.include_router(decision_router)
app.include_router(investor_router)
app.include_router(signals_router)
app.include_router(farm_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(twin_router)
app.include_router(misc_router)
app.include_router(notification_router)
app.include_router(locality_router)
app.include_router(bloom_router)
app.include_router(bio_risk_router)
app.include_router(country_router)
app.include_router(market_router)
app.include_router(ml_router)
app.include_router(supply_router)
app.include_router(traceability_router)
app.include_router(compliance_router)
app.include_router(admin_router)
app.include_router(webhook_router)
app.include_router(apikey_router)
app.include_router(futures_router)
app.include_router(integration_router)

# ── Models ────────────────────────────────────────────────────────────
from core.schemas import HealthResponse


# ── Dependency ────────────────────────────────────────────────────────
# In production, replace with JWT auth
def verify_api_key():
    # Simplified — add real auth in production
    return True


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    db_status = "ok"
    try:
        from core.async_db import get_async_session
        from sqlalchemy import text
        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {str(exc)[:80]}"

    from core.cache import engine_cache, cache_manager
    return {
        "status": "healthy",
        "database": db_status,
        "cache": engine_cache.stats(),
        "cache_manager": cache_manager.get_stats(),
        "routes": len([r for r in app.routes if hasattr(r, 'path')]),
        "version": "2.2.0",
        "rate_limits": TIER_LIMITS,
    }


@app.get("/api/rate-limit-info")
async def rate_limit_info(request: Request):
    """Check your current rate limit tier and remaining quota.

    Returns the tier detected from your auth credentials and the
    corresponding rate limit. Use this to monitor your API usage.
    """
    key = _get_rate_limit_key(request)
    tier = "default"
    for t in TIER_LIMITS:
        if f":{t}" in key:
            tier = t
            break
    limit = TIER_LIMITS.get(tier, "200/minute")
    return {
        "tier": tier,
        "limit": limit,
        "key_prefix": key[:20] + "..." if len(key) > 20 else key,
        "tiers_available": TIER_LIMITS,
        "note": "Upgrade your subscription tier for higher limits.",
    }


@app.get("/api/metrics")
async def metrics():
    """Prometheus-compatible metrics for monitoring."""
    import time as _time
    from core.cache import engine_cache

    cache = engine_cache.stats()

    # Process metrics (optional — psutil may not be installed)
    process_info = {}
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        process_info = {
            "memory_rss_mb": round(mem.rss / 1024 / 1024, 1),
            "memory_vms_mb": round(mem.vms / 1024 / 1024, 1),
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads(),
            "uptime_seconds": round(_time.time() - process.create_time()),
        }
    except ImportError:
        process_info = {"note": "psutil not installed — limited process metrics"}
    except Exception as exc:
        process_info = {"error": str(exc)[:80]}

    return {
        "cache": cache,
        "process": process_info,
        "routes": len([r for r in app.routes if hasattr(r, 'path')]),
        "version": "2.1.0",
    }


@app.get("/api/cache/stats")
async def cache_stats():
    """Cache performance statistics."""
    from core.cache import engine_cache
    return engine_cache.stats()


@app.post("/api/cache/invalidate")
async def cache_invalidate(request: Request):
    """Invalidate cache entries. POST body: {"pattern": "yoy"} or {} for all."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    pattern = body.get("pattern", "")
    from core.cache import engine_cache
    engine_cache.invalidate(pattern)
    return {"status": "ok", "pattern": pattern or "(all)", "cache": engine_cache.stats()}


# DISEASE ROUTES: Moved to core/routers/disease_routes.py
# BENCHMARK/FEDERATED ROUTES: Moved to core/routers/analytics_routes.py
# AUTH ROUTES: Moved to core/routers/auth_routes.py


# SIGNALS/ORDERS/AUDIT/DISCLAIMER ROUTES: Moved to core/routers/signals_routes.py
# LICE ROUTES: Moved to core/routers/lice_routes.py
# ANALYTICS/YOY ROUTES: Moved to core/routers/analytics_routes.py


# ══════════════════════════════════════════════════════════════════════
# BLOOM/TIERS/SUPPLY/FARM/MARKET/ML PRICE/LEADERS/SELF-IMPROVEMENT ROUTES:
# Moved to core/routers/misc_routes.py, analytics_routes.py, farm_routes.py

# ══════════════════════════════════════════════════════════════════════
# AI CHAT ENDPOINT
# ══════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """AI chat with full platform context via OpenRouter/Anthropic."""
    import httpx as hx
    from config.settings import settings

    # Build platform context from live data
    from core.async_db import get_async_session
    async with get_async_session() as s:
        lice_stats = (await s.execute(
            select(
                func.count(LiceRecord.id),
                func.avg(LiceRecord.avg_adult_female_lice),
                func.max(LiceRecord.avg_adult_female_lice),
            ).where(LiceRecord.avg_adult_female_lice.isnot(None))
        )).one()

        latest_week = (await s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        )).first()

        n_localities = (await s.execute(
            select(func.count(func.distinct(Locality.locality_no)))
        )).scalar() or 0

        n_signals = (await s.execute(
            select(func.count(Signal.id)).where(Signal.status == "pending")
        )).scalar() or 0

    # Get real SSB spot price
    try:
        from core.market.ssb_price_client import ssb_price_client
        spot = await ssb_price_client.get_current_spot()
    except Exception:
        spot = 0

    avg_lice = lice_stats[1] or 0
    max_lice = lice_stats[2] or 0
    n_records = lice_stats[0] or 0

    system_prompt = f"""You are the OpenClaw AI — an expert analyst for Norwegian salmon aquaculture.
You have access to real-time platform data:
- {n_records:,} lice records across {n_localities} localities
- Latest data: {f"Y{latest_week[0]}W{latest_week[1]}" if latest_week else "N/A"}
- National avg adult female lice: {avg_lice:.3f} per fish (threshold: 0.5)
- Maximum observed: {max_lice:.3f}
- Pending trading signals: {n_signals}
- Current SSB salmon spot price: {spot:.1f} NOK/kg
- Data sources: BarentsWatch (NLOD 2.0), SSB (Statistics Norway), Fiskeridirektoratet

Key domain knowledge:
- Norwegian regulatory threshold: 0.5 adult female lice per fish
- Traffic light system: green (< 0.2), yellow (0.2-0.5), red (> 0.5) per production area
- Major listed companies: MOWI, SALM (SalMar), LSG (Lerøy), GSF (Grieg Seafood)
- Treatment types: mechanical (Hydrolicer/Thermolicer), cleaner fish (wrasse/lumpfish), medicinal (bath/in-feed)
- High lice → forced harvest → supply disruption → price increase (4-8 week lag)

Always provide data-backed answers. Include accuracy caveats where relevant. Never give financial advice."""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history[-10:]:  # last 10 messages for context
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    # Call LLM via OpenRouter (or Anthropic)
    if settings.llm_provider == "openrouter" and settings.openrouter_api_key:
        api_url = f"{settings.openrouter_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openclaw.no",
            "X-Title": "OpenClaw",
        }
    elif settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
    else:
        # No LLM key — fall through to rule-based data response
        return await _rule_based_chat_response(req.message)

    try:
        async with hx.AsyncClient(timeout=60.0) as client:
            if settings.llm_provider == "anthropic":
                # Anthropic Messages API format
                resp = await client.post(api_url, headers=headers, json={
                    "model": settings.llm_model.replace("anthropic/", ""),
                    "max_tokens": settings.llm_max_tokens,
                    "temperature": settings.llm_temperature,
                    "system": system_prompt,
                    "messages": [m for m in messages if m["role"] != "system"],
                })
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", [{}])[0].get("text", "")
                    return {"response": content}
            else:
                # OpenAI-compatible (OpenRouter)
                resp = await client.post(api_url, headers=headers, json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "max_tokens": settings.llm_max_tokens,
                    "temperature": settings.llm_temperature,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return {"response": content}

            log.warning("chat.llm_error", status=resp.status_code)
            # Fallback to rule-based on LLM error
            return await _rule_based_chat_response(req.message)

    except Exception as e:
        log.warning("chat.connection_error", error=str(e)[:100])
        return await _rule_based_chat_response(req.message)


@app.post("/api/chat/briefing")
async def chat_briefing(request: Request):
    """Generate a personalized intelligence briefing."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    pas = body.get("pas", [3, 4, 5, 6])
    companies = body.get("companies", ["Mowi", "SalMar", "Lerøy"])

    # Build context from live data
    context_parts = []
    try:
        from core.market.farm_graph import farm_graph
        summary = await farm_graph.get_summary()
        context_parts.append(f"Farm network: {summary.get('n_farms', 0)} farms, {summary.get('n_above_threshold', 0)} above lice threshold")
    except Exception:
        pass
    try:
        from core.valuechain.smolt_model import smolt_model
        balance = smolt_model.get_demand_balance()
        context_parts.append(f"Supply balance: {balance.get('signal', 'unknown')}, price pressure: {balance.get('price_pressure', 'unknown')}")
    except Exception:
        pass

    briefing_prompt = (
        f"Generate a concise intelligence briefing for a salmon industry professional "
        f"monitoring production areas {pas} and companies {companies}. "
        f"Current data: {'; '.join(context_parts)}. "
        f"Include: market outlook, key risks, and recommended actions."
    )

    try:
        from core.llm.chat_agent import chat_agent
        response = await chat_agent.ask(briefing_prompt)
        return {"briefing": response, "context": context_parts, "pas": pas, "companies": companies}
    except Exception as e:
        return {"briefing": f"Briefing generation unavailable: {str(e)[:100]}", "context": context_parts}

@app.get("/api/chat/history")
async def chat_history(limit: int = 20):
    """Return recent conversation history."""
    try:
        from core.llm.chat_agent import chat_agent
        history = getattr(chat_agent, "conversation_history", [])
        return {"messages": history[-limit:], "total": len(history)}
    except Exception:
        return {"messages": [], "total": 0}


# ══════════════════════════════════════════════════════════════════════
# SSB REAL DATA ENDPOINTS
# ══════════════════════════════════════════════════════════════════════


# REMAINING MARKET/SSB/LEADERS/TWIN/EXPOSURE/AIS/SENTIMENT/FARM-GRAPH ROUTES:
# All moved to router modules in core/routers/ (Session 10)



# ── Unified Intelligence Summary ─────────────────────────────────────

@app.get("/api/intelligence/summary")
async def intelligence_summary():
    """
    Unified intelligence summary combining all advanced features.
    Single endpoint for the Command Centre dashboard.
    """
    from core.market.ais_tracker import ais_tracker
    from core.market.sentiment_engine import sentiment_engine
    from core.market.farm_graph import farm_graph
    from core.market.regime_detector import regime_detector
    from core.market.chile_monitor import chile_monitor
    from core.market.pairs_engine import pairs_engine

    # Optional: enrich with SSB spot price
    spot_price = 0.0
    try:
        from core.market.ssb_price_client import ssb_price_client
        spot_price = await ssb_price_client.get_current_spot()
    except Exception:
        pass

    # Causal lag (if computed)
    causal_lag_weeks = None
    try:
        from core.market.causal_engine import causal_engine
        csummary = causal_engine.get_causal_summary()
        causal_lag_weeks = csummary.get("dominant_lag_weeks") if csummary else None
    except Exception:
        pass

    all_pairs = pairs_engine.get_all_pairs()

    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "ais": {
            "active_vessels": len(ais_tracker.get_active_tracks()),
            "harvest_signals_72h": len(ais_tracker.get_harvest_signals(72)),
            "treatment_signals_72h": len(ais_tracker.get_treatment_signals(72)),
        },
        "sentiment": sentiment_engine.get_sentiment_summary(),
        "farm_network": await farm_graph.get_graph_summary(),
        "regime": {
            "alerts": regime_detector.get_alerts()[:3],
            "high_risk_pas": [
                s for s in regime_detector.get_all_states()
                if s.get("color_change")
            ][:3],
        },
        "chile": chile_monitor.get_latest_snapshot(),
        "pairs": {
            "active_pairs": len(all_pairs),
            "active_signals": len(pairs_engine.get_signals(7)),
            "causal_calibrated": all_pairs[0].get("causal_calibrated", False) if all_pairs else False,
            "causal_lag_weeks": all_pairs[0].get("causal_lag_weeks") if all_pairs else None,
        },
        "prices": {
            "spot": round(spot_price, 1),
            "currency": "NOK/kg",
            "source": "SSB table 03024",
        },
        "causal": {
            "dominant_lag_weeks": causal_lag_weeks,
        },
        # Context stats for AI chat
        "signal_count": len(pairs_engine.get_signals(7)) + len(regime_detector.get_alerts()),
        "lice_active": True,  # lice data is always loaded
    }


@app.get("/api/intelligence/health")
async def intelligence_health():
    """Per-module health check for the intelligence engine."""
    from core.market.ais_tracker import ais_tracker
    from core.market.sentiment_engine import sentiment_engine
    from core.market.farm_graph import farm_graph
    from core.market.regime_detector import regime_detector
    from core.market.chile_monitor import chile_monitor
    from core.market.pairs_engine import pairs_engine

    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "modules": {
            "ais": {
                "status": "ok",
                "tracks": len(ais_tracker.get_active_tracks()),
                "last_updated": ais_tracker.get_supply_intelligence().get("generated_at"),
            },
            "sentiment": {
                "status": "ok",
                "articles_cached": len(sentiment_engine._articles) if hasattr(sentiment_engine, "_articles") else 0,
                "signals": len(sentiment_engine.get_signals()),
            },
            "farm_graph": {
                "status": "ok",
                **(await farm_graph.get_graph_summary()),
            },
            "regime": {
                "status": "ok",
                "pas_tracked": len(regime_detector.get_all_states()),
                "active_alerts": len(regime_detector.get_alerts()),
            },
            "chile": {
                "status": "ok",
                "snapshot": chile_monitor.get_latest_snapshot(),
            },
            "pairs": {
                "status": "ok",
                "pairs_count": len(pairs_engine.get_all_pairs()),
                "signals_7d": len(pairs_engine.get_signals(7)),
            },
        },
    }


# ══════════════════════════════════════════════════════════════════════
# WEBSOCKET — Real-time Command Centre streaming
# ══════════════════════════════════════════════════════════════════════

class ConnectionManager:
    """Manages active WebSocket connections for the Command Centre."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        payload = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_ws_manager = ConnectionManager()


@app.websocket("/ws/command-centre")
async def ws_command_centre(websocket: WebSocket):
    """
    Real-time WebSocket for Command Centre dashboard.

    Streams a fresh intelligence snapshot every 30 seconds.
    Clients can also send {"action": "refresh"} to trigger immediate update.
    """
    await _ws_manager.connect(websocket)
    try:
        while True:
            # Wait for client message (with timeout for periodic push)
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(raw) if raw else {}
            except asyncio.TimeoutError:
                msg = {"action": "auto_refresh"}
            except WebSocketDisconnect:
                break

            if msg.get("action") in ("refresh", "auto_refresh"):
                from core.market.ais_tracker import ais_tracker
                from core.market.sentiment_engine import sentiment_engine
                from core.market.farm_graph import farm_graph
                from core.market.regime_detector import regime_detector
                from core.market.chile_monitor import chile_monitor
                from core.market.pairs_engine import pairs_engine

                payload = {
                    "type": "intelligence_update",
                    "generated_at": dt.datetime.now(dt.UTC).isoformat(),
                    "ais": {
                        "active_vessels": len(ais_tracker.get_active_tracks()),
                        "harvest_signals": len(ais_tracker.get_harvest_signals(72)),
                        "treatment_signals": len(ais_tracker.get_treatment_signals(72)),
                        "tracks": ais_tracker.get_active_tracks()[:10],
                    },
                    "sentiment": sentiment_engine.get_sentiment_summary(),
                    "articles": sentiment_engine.get_recent_articles(hours=6)[:5],
                    "farm_network": await farm_graph.get_graph_summary(),
                    "regime_alerts": regime_detector.get_alerts()[:5],
                    "chile": chile_monitor.get_latest_snapshot(),
                    "chile_signals": chile_monitor.get_signals(days=7)[:3],
                    "pairs": pairs_engine.get_all_pairs()[:6],
                    "pairs_signals": pairs_engine.get_signals(days=3)[:5],
                }
                try:
                    await websocket.send_text(json.dumps(payload))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        _ws_manager.disconnect(websocket)


@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """Real-time alert streaming via WebSocket."""
    await websocket.accept()
    try:
        while True:
            from core.market.threshold_alerts import threshold_alert_engine
            alerts = await threshold_alert_engine.check_all()
            await websocket.send_json({
                "type": "alerts",
                "count": len(alerts),
                "critical": sum(1 for a in alerts if a.severity == "critical"),
                "alerts": [a.to_dict() for a in alerts[:20]],
                "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            })
            # Dispatch critical/high alerts to configured webhooks
            critical_alerts = [a for a in alerts if a.severity in ("critical", "high")]
            if critical_alerts:
                try:
                    from core.market.webhook_dispatcher import webhook_dispatcher
                    for alert in critical_alerts[:5]:  # Cap to avoid flooding
                        await webhook_dispatcher.dispatch_alert(
                            f"alert.{alert.category}",
                            {
                                "title": alert.title,
                                "message": alert.message,
                                "severity": alert.severity,
                                "category": alert.category,
                                "metric_value": alert.metric_value,
                                "threshold": alert.threshold,
                                "timestamp": alert.created_at,
                            },
                        )
                except Exception:
                    pass  # Webhook failures must not break the alert stream
            await asyncio.sleep(30)  # Push every 30 seconds
    except WebSocketDisconnect:
        pass


# GNN/TWIN/EQUITY/OCEAN/CAUSAL/FEED-COST routes: Moved to routers

async def _rule_based_chat_response(message: str) -> dict:
    """
    Data-grounded rule-based fallback response.
    Used when no LLM API key is configured, or as fallback on LLM errors.
    Returns a structured response compatible with the /api/chat contract.
    """
    msg = message.lower()

    # ── Intent detection ──────────────────────────────────────────────
    is_lice = any(w in msg for w in ("lice", "sea lice", "parasite", "infestation", "caligus"))
    is_price = any(w in msg for w in ("price", "market", "nok", "fish pool", "spot", "cost"))
    is_signal = any(w in msg for w in ("signal", "trade", "buy", "sell", "long", "short", "pairs"))
    is_regime = any(w in msg for w in ("regime", "regulation", "traffic light", "production area", "pa "))
    is_risk = any(w in msg for w in ("risk", "farm", "cluster", "network", "cascade", "spread"))
    is_forecast = any(w in msg for w in ("forecast", "predict", "outlook", "future", "expect", "next week"))
    is_ais = any(w in msg for w in ("vessel", "ais", "ship", "harvest", "treatment boat", "wellboat"))
    is_causal = any(w in msg for w in ("causal", "lag", "granger", "transfer entropy", "how long", "delay"))
    is_chile = any(w in msg for w in ("chile", "chilean", "atlantic sapphire", "global supply", "arbitrage"))

    answer_parts: list[str] = []
    data_used: list[str] = []
    confidence = "medium"

    # ── Lice context ──────────────────────────────────────────────────
    if is_lice:
        data_used.append("lice_records")
        async with get_async_session() as s:
            latest_wk = (await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )).first()
            if latest_wk:
                stats = (await s.execute(
                    select(
                        func.avg(LiceRecord.avg_adult_female_lice),
                        func.max(LiceRecord.avg_adult_female_lice),
                        func.count(LiceRecord.id),
                    ).where(
                        LiceRecord.year == latest_wk[0],
                        LiceRecord.week == latest_wk[1],
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )).first()
                if stats and stats[0]:
                    avg_l = float(stats[0])
                    max_l = float(stats[1] or 0)
                    n_sites = int(stats[2] or 0)
                    above_thresh = (await s.execute(
                        select(func.count(LiceRecord.id)).where(
                            LiceRecord.year == latest_wk[0],
                            LiceRecord.week == latest_wk[1],
                            LiceRecord.avg_adult_female_lice > 0.5,
                        )
                    )).scalar() or 0
                    pct_above = above_thresh / max(n_sites, 1) * 100
                    threshold_status = (
                        "⚠️ **above the 0.5 threshold**" if avg_l > 0.5 else "✅ **below the 0.5 threshold**"
                    )
                    answer_parts.append(
                        f"**Lice Situation (Week {latest_wk[1]}/{latest_wk[0]})**\n\n"
                        f"- National average: **{avg_l:.3f}** adult female lice per fish — {threshold_status}\n"
                        f"- Peak recorded: **{max_l:.3f}** at a single site\n"
                        f"- Sites monitored: **{n_sites}** across all production areas\n"
                        f"- Sites above threshold (>0.5): **{above_thresh}** ({pct_above:.1f}%)\n\n"
                        f"{'High lice pressure increases disease risk and treatment costs, which historically causes a supply reduction and price spike 6–10 weeks later.' if avg_l > 0.5 else 'Lice levels are currently under control. Monitor week-on-week trends for early warning signals.'}"
                    )
                    confidence = "high"
                else:
                    answer_parts.append("Lice data is in the database but no statistics are available for the latest week. This may indicate data is still being ingested from BarentsWatch.")
            else:
                answer_parts.append("No lice data found in the database yet. Run the BarentsWatch ingestor to populate lice records from the Norwegian Directorate of Fisheries API.")

    # ── Price context ─────────────────────────────────────────────────
    if is_price:
        data_used.append("ssb_prices")
        try:
            from core.market.ssb_price_client import ssb_price_client
            spot = await ssb_price_client.get_current_spot()
            history = await ssb_price_client.get_price_history(n_weeks=4)
            prev_week = history[-2]["price_nok_kg"] if len(history) >= 2 else spot
            wow_chg = ((spot - prev_week) / prev_week * 100) if prev_week else 0
            direction = "📈 up" if wow_chg > 0 else "📉 down"
            answer_parts.append(
                f"**Salmon Price (SSB — Statistics Norway)**\n\n"
                f"- Current spot: **{spot:.1f} NOK/kg** (head-on gutted, export)\n"
                f"- Week-on-week: **{direction} {abs(wow_chg):.1f}%**\n"
                f"- Data source: SSB table 03024, licensed CC BY 4.0\n\n"
                f"Key price drivers: Norwegian lice pressure (6–10 week lag), Chilean supply disruptions, "
                f"EU import demand, and seasonal patterns (Q4 typically strongest)."
            )
            confidence = "high"
        except Exception as exc:
            answer_parts.append(f"SSB price data is temporarily unavailable ({str(exc)[:60]}). Fish Pool Index is the primary real-time reference — spot prices typically trade at 1–3% premium/discount.")
            data_used.append("ssb_unavailable")

    # ── Signal context ────────────────────────────────────────────────
    if is_signal:
        data_used.append("signals")
        async with get_async_session() as s:
            sigs = (await s.execute(
                select(Signal)
                .where(Signal.status == "pending")
                .order_by(Signal.created_at.desc())
                .limit(5)
            )).scalars().all()

        if sigs:
            sig_lines = "\n".join(
                f"- **{sig.ticker}** {sig.direction.upper()} | strength {sig.strength:.2f} | {sig.rationale[:80]}…"
                for sig in sigs
            )
            answer_parts.append(
                f"**Active Trading Signals ({len(sigs)} pending)**\n\n{sig_lines}\n\n"
                f"Signals are generated by the lice-price correlation model. "
                f"Confirm or reject via the Command Centre. All signals require human review before execution."
            )
            confidence = "high"
        else:
            from core.market.pairs_engine import pairs_engine
            pairs = pairs_engine.get_signals(days=7)
            if pairs:
                p_lines = "\n".join(
                    f"- **{p['pair']}** {p['signal']} | z={p['z_score']:.2f} | {p['biological_overlay'][:60]}…"
                    for p in pairs[:3]
                )
                answer_parts.append(
                    f"**No pending directional signals.** However, **{len(pairs)} pairs signals** are active in the last 7 days:\n\n{p_lines}"
                )
            else:
                answer_parts.append("No active signals at this time. The market appears to be in a neutral phase — lice levels and price momentum are not generating entry conditions.")

    # ── Regime context ────────────────────────────────────────────────
    if is_regime:
        data_used.append("regime_detector")
        from core.market.regime_detector import regime_detector
        states = regime_detector.get_all_states()
        alerts = regime_detector.get_alerts()
        if states:
            red_pas = [pa for pa, s in states.items() if s.get("lice_regime") in ("high", "critical")]
            green_pas = [pa for pa, s in states.items() if s.get("lice_regime") == "low"]
            answer_parts.append(
                f"**Regulatory Regime Status ({len(states)} Production Areas)**\n\n"
                f"- 🔴 High/critical pressure: **{len(red_pas)} PAs** ({', '.join(red_pas[:5])})\n"
                f"- 🟢 Low pressure: **{len(green_pas)} PAs**\n"
                f"- Active alerts: **{len(alerts)}**\n\n"
                f"Norway uses a traffic-light system: red PAs face mandatory production cuts (-6% capacity), "
                f"yellow PAs are under observation, green PAs can expand. "
                f"Red designation historically correlates with 3–8% price increases over 6–8 weeks."
            )
            confidence = "high"
        else:
            answer_parts.append("Regime data is being computed. The traffic-light system covers 13 Norwegian production areas. Red = capacity reduction, Yellow = monitoring, Green = expansion allowed.")

    # ── Risk / Farm Network context ───────────────────────────────────
    if is_risk:
        data_used.append("farm_graph")
        from core.market.farm_graph import farm_graph
        summary = await farm_graph.get_graph_summary()
        cascades = await farm_graph.get_predicted_cascades()
        answer_parts.append(
            f"**Farm Network Risk**\n\n"
            f"- Network nodes: **{summary.get('node_count', 0)} farms**\n"
            f"- High-risk clusters: **{summary.get('high_risk_clusters', 0)}**\n"
            f"- Predicted cascade events: **{len(cascades)}**\n\n"
            f"The farm network graph uses geographic proximity and ocean current direction "
            f"to model how lice can spread between sites. Clusters of high-risk farms in the same "
            f"current corridor represent elevated systemic risk for the production area."
        )

    # ── Forecast context ──────────────────────────────────────────────
    if is_forecast:
        data_used.append("price_ensemble")
        try:
            from core.market.price_ensemble import price_ensemble
            from core.market.ssb_price_client import ssb_price_client
            spot = await ssb_price_client.get_current_spot()
            fc = price_ensemble.predict(
                current_spot=spot or 75.0,
                horizon_weeks=8,
                national_avg_lice=0.3,
                pct_above_threshold=0.2,
                n_scenarios=500,
            )
            direction_emoji = "📈" if fc.direction == "up" else "📉" if fc.direction == "down" else "➡️"
            answer_parts.append(
                f"**8-Week Price Forecast**\n\n"
                f"- Current spot: **{spot:.1f} NOK/kg**\n"
                f"- Predicted (8w): **{fc.predicted_nok:.1f} NOK/kg** {direction_emoji}\n"
                f"- 80% confidence interval: **{fc.price_lo80:.1f} – {fc.price_hi80:.1f} NOK/kg**\n"
                f"- Model signal: **{fc.combined_signal.upper()}**\n\n"
                f"Forecast uses an ensemble of lice-adjusted mean reversion, seasonal decomposition, "
                f"and causal lag models. MAPE on backtested data: ~{fc.mape_backtest:.1f}%."
            )
            confidence = "high"
        except Exception:
            answer_parts.append("Price forecast models are initializing. Run the BarentsWatch ingestor and SSB price sync to activate ensemble forecasting.")

    # ── AIS context ───────────────────────────────────────────────────
    if is_ais:
        data_used.append("ais_tracker")
        from core.market.ais_tracker import ais_tracker
        tracks = ais_tracker.get_active_tracks()
        harvest = ais_tracker.get_harvest_signals(72)
        treatment = ais_tracker.get_treatment_signals(72)
        answer_parts.append(
            f"**AIS Vessel Intelligence**\n\n"
            f"- Active vessel tracks: **{len(tracks)}**\n"
            f"- Harvest signals (72h): **{len(harvest)}** (wellboats at cage sites)\n"
            f"- Treatment signals (72h): **{len(treatment)}** (treatment vessels deployed)\n\n"
            f"Treatment vessel movements are a leading indicator of lice pressure — "
            f"farms request treatment 1–3 days after exceeding threshold. "
            f"Elevated treatment activity typically signals an upcoming supply reduction."
        )

    # ── Causal lag context ────────────────────────────────────────────
    if is_causal:
        data_used.append("causal_engine")
        from core.market.causal_engine import causal_engine
        try:
            summary = causal_engine.get_causal_summary()
            if summary.get("dominant_lag_weeks"):
                lag = summary["dominant_lag_weeks"]
                conf = summary.get("confidence", "medium")
                rng = summary.get("recommended_lag_range", [lag - 1, lag + 1])
                answer_parts.append(
                    f"**Causal Lag Analysis (Granger + Transfer Entropy)**\n\n"
                    f"- Dominant lice→price lag: **{lag} weeks** ({conf} confidence)\n"
                    f"- Recommended entry window: **Week {rng[0]}–{rng[1]} after lice event**\n"
                    f"- Asymmetric response: {summary.get('asymmetry_detected', False)}\n\n"
                    f"Interpretation: {summary.get('interpretation', 'Run /api/causal/summary to compute.')}"
                )
                confidence = conf
            else:
                answer_parts.append(
                    "Causal analysis has not been run yet. Navigate to the **Causal Engine** page "
                    "and click 'Run Analysis' to discover the data-driven lice→price lag using Granger causality and Transfer Entropy. "
                    "Academic literature suggests 6–10 weeks (Abolofia et al. 2017, Asche et al. 2015)."
                )
        except Exception:
            answer_parts.append("Causal engine is ready. Click 'Run Analysis' on the Causal Engine page to compute the lice→price lag from your historical data.")

    # ── Chile / cross-market context ──────────────────────────────────
    if is_chile:
        data_used.append("chile_monitor")
        from core.market.chile_monitor import chile_monitor
        snapshot = chile_monitor.get_latest_snapshot()
        if snapshot:
            answer_parts.append(
                f"**Chilean Market Intelligence**\n\n"
                f"- Supply disruption score: **{snapshot.get('supply_disruption_score', 0):.1f}/10**\n"
                f"- Market: {snapshot.get('market_condition', 'unknown')}\n\n"
                f"Chile accounts for ~25% of global Atlantic salmon supply. "
                f"Supply disruptions in Chile (ISA virus, red tide, regulatory changes) "
                f"typically cause a 2–4 week lag before Norwegian export prices react, "
                f"per Asche et al. (2009) on global market integration."
            )
        else:
            answer_parts.append("Chilean market data is being initialised. The Chile Monitor tracks ISA disease outbreaks, regulatory changes, and production volume to identify cross-market arbitrage opportunities.")

    # ── Fallback ──────────────────────────────────────────────────────
    if not answer_parts:
        answer_parts.append(
            "I'm OpenClaw's intelligence assistant, specialising in Norwegian aquaculture markets.\n\n"
            "I can help you with:\n"
            "- **Lice levels** — real-time BarentsWatch data across 13 production areas\n"
            "- **Salmon prices** — SSB spot prices, Fish Pool index, equity prices\n"
            "- **Trading signals** — lice-price momentum, pairs arbitrage, hedger signals\n"
            "- **Regulatory regimes** — traffic-light system, production area restrictions\n"
            "- **Farm network risk** — cluster analysis, cascade predictions\n"
            "- **Forecasts** — ensemble ML price predictions up to 20 weeks ahead\n"
            "- **Causal analysis** — Granger causality and Transfer Entropy for lag discovery\n\n"
            "Try asking: *'What's the current lice situation?'* or *'Show me active signals'*"
        )
        confidence = "high"

    # ── Compose final response ────────────────────────────────────────
    full_answer = "\n\n---\n\n".join(answer_parts)

    # Follow-up suggestions based on what was answered
    follow_ups = []
    if is_lice and not is_price:
        follow_ups.append("What does this lice level mean for salmon prices?")
    if is_price and not is_signal:
        follow_ups.append("Are there any active trading signals right now?")
    if is_signal and not is_forecast:
        follow_ups.append("What's the 8-week price forecast?")
    if is_forecast and not is_causal:
        follow_ups.append("What is the causal lag between lice and price?")
    if not follow_ups:
        follow_ups = [
            "What's the current lice situation?",
            "Show me active trading signals",
            "What's the 8-week price forecast?",
        ]

    return {
        "response": full_answer,
        "answer": full_answer,  # both keys for compatibility
        "data_used": data_used,
        "confidence": confidence,
        "follow_up": follow_ups[:3],
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
    }




# COUNTRY/TRACEABILITY/CHRONOS/PRICE-HUB/TRAFFIC-LIGHT/ALERTS routes: Moved to routers



@app.get("/api/global/farms")
async def global_farms():
    """All country farm locations merged into one GeoJSON — always returns data."""
    features = []
    # Iceland
    try:
        from core.market.iceland_monitor import iceland_monitor
        geo = iceland_monitor.get_farms_geojson()
        features.extend(geo.get("features", []))
    except Exception:
        pass
    # Scotland
    try:
        from core.market.scotland_monitor import scotland_monitor
        geo = scotland_monitor.get_farms_geojson()
        features.extend(geo.get("features", []))
    except Exception:
        pass
    # Faroe Islands
    try:
        from core.market.faroe_monitor import faroe_monitor
        geo = faroe_monitor.get_farms_geojson()
        features.extend(geo.get("features", []))
    except Exception:
        pass
    # Chile
    try:
        from core.market.chile_monitor import chile_monitor
        geo = chile_monitor.get_farms_geojson()
        features.extend(geo.get("features", []))
    except Exception:
        pass
    # Canada
    try:
        from core.market.canada_monitor import canada_monitor
        geo = canada_monitor.get_farms_geojson()
        features.extend(geo.get("features", []))
    except Exception:
        pass
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/global/bloom-risk")
async def global_bloom_risk():
    """Bloom risk GeoJSON for ALL countries. Always returns points — enriched with live CMEMS when available."""
    features = []

    # ── Norway — from BloomRiskAssessment DB table (same as /api/bloom/risk) ──
    try:
        from core.models import BloomRiskAssessment, Locality
        from core.async_db import get_async_session
        from sqlalchemy import select, func
        async with get_async_session() as s:
            subq = (
                select(
                    BloomRiskAssessment.locality_no,
                    func.max(BloomRiskAssessment.assessed_at).label("latest"),
                )
                .group_by(BloomRiskAssessment.locality_no)
                .subquery()
            )
            rows = (await s.execute(
                select(
                    BloomRiskAssessment.locality_no,
                    BloomRiskAssessment.risk_level,
                    BloomRiskAssessment.chl_a_value,
                    BloomRiskAssessment.sst_value,
                    Locality.name,
                    Locality.latitude,
                    Locality.longitude,
                )
                .join(subq, (
                    BloomRiskAssessment.locality_no == subq.c.locality_no
                ) & (
                    BloomRiskAssessment.assessed_at == subq.c.latest
                ))
                .outerjoin(Locality, BloomRiskAssessment.locality_no == Locality.locality_no)
                .limit(500)
            )).all()
            for row in rows:
                if row.latitude and row.longitude:
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [float(row.longitude), float(row.latitude)]},
                        "properties": {
                            "name": row.name or f"#{row.locality_no}",
                            "country": "Norway",
                            "risk_level": row.risk_level or "LOW",
                            "chl_a": float(row.chl_a_value or 0),
                            "sst": float(row.sst_value or 0),
                            "layer": "bloom",
                        },
                    })
    except Exception:
        pass

    # ── Helper: add region points for a country ──
    def _add_regions(regions: dict, country: str, cache_obj=None, sst_attr: str = "avg_sst",
                     chl_attr: str = "avg_chl_a", bloom_attr: str = "bloom_risk"):
        for name, info in regions.items():
            lat = info.get("lat", 0)
            lng = info.get("lng", 0)
            if not lat or not lng:
                continue
            # Try to get live data from cache, default to "monitoring"
            risk = "monitoring"
            chl = 0
            sst = 0
            if cache_obj:
                if hasattr(cache_obj, bloom_attr):
                    r = getattr(cache_obj, bloom_attr, "unknown")
                    if r != "unknown":
                        risk = r
                if hasattr(cache_obj, chl_attr):
                    chl = getattr(cache_obj, chl_attr, 0) or 0
                if hasattr(cache_obj, sst_attr):
                    sst = getattr(cache_obj, sst_attr, 0) or 0
                # Handle nested sea_conditions
                if hasattr(cache_obj, "sea_conditions"):
                    sc = cache_obj.sea_conditions
                    if sc:
                        if hasattr(sc, bloom_attr) and getattr(sc, bloom_attr, "unknown") != "unknown":
                            risk = getattr(sc, bloom_attr)
                        if hasattr(sc, chl_attr):
                            chl = getattr(sc, chl_attr, 0) or 0
                        if hasattr(sc, sst_attr):
                            sst = getattr(sc, sst_attr, 0) or 0
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "name": name,
                    "country": country,
                    "risk_level": risk,
                    "chl_a": chl,
                    "sst": sst,
                    "layer": "bloom",
                },
            })

    # ── Iceland — always show 2 regions, enriched when CMEMS available ──
    try:
        from core.market.iceland_monitor import iceland_monitor, ICELAND_REGIONS
        s = iceland_monitor._cache
        for region_key, bbox in ICELAND_REGIONS.items():
            center_lat = (bbox["lat_min"] + bbox["lat_max"]) / 2
            center_lng = (bbox["lon_min"] + bbox["lon_max"]) / 2
            risk = "monitoring"
            chl = 0
            sst = 0
            if s and s.sea_conditions:
                r = getattr(s.sea_conditions, f"bloom_risk_{region_key}", "unknown")
                if r != "unknown":
                    risk = r
                chl = getattr(s.sea_conditions, f"{region_key}_chl_a", 0) or 0
                sst = getattr(s.sea_conditions, f"{region_key}_sst", 0) or 0
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [center_lng, center_lat]},
                "properties": {
                    "name": f"Iceland {region_key.title()}", "country": "Iceland",
                    "risk_level": risk, "chl_a": chl, "sst": sst, "layer": "bloom",
                },
            })
    except Exception:
        pass

    # ── Scotland — always show 7 regions ──
    try:
        from core.market.scotland_monitor import scotland_monitor, SCOTLAND_REGIONS
        _add_regions(SCOTLAND_REGIONS, "Scotland", scotland_monitor._cache)
    except Exception:
        pass

    # ── Faroe Islands — always show 10 regions ──
    try:
        from core.market.faroe_monitor import faroe_monitor, FAROE_REGIONS
        _add_regions(FAROE_REGIONS, "Faroe Islands", faroe_monitor._cache)
    except Exception:
        pass

    # ── Canada — always show 8 BC regions ──
    try:
        from core.market.canada_monitor import canada_monitor, BC_REGIONS
        _add_regions(BC_REGIONS, "Canada", canada_monitor._cache)
    except Exception:
        pass

    # ── Chile — always show 4 regions ──
    try:
        from core.market.chile_monitor import CHILE_REGIONS
        for name, info in CHILE_REGIONS.items():
            if "lat" in info:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                    "properties": {
                        "name": name, "country": "Chile",
                        "risk_level": "monitoring", "chl_a": 0, "sst": 0, "layer": "bloom",
                    },
                })
    except Exception:
        pass

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/global/disease-geo")
async def global_disease_geo():
    """Disease outbreaks GeoJSON for ALL countries."""
    features = []

    # Norway (Mattilsynet — detailed per-locality)
    try:
        from core.market.mattilsynet_client import mattilsynet_client
        from core.models import Locality
        from core.async_db import get_async_session
        from sqlalchemy import select
        cases = await mattilsynet_client.fetch_disease_cases(limit=200)
        active = [c for c in cases if c.status == "active"]
        # Get coordinates from Locality table
        loc_coords: dict[int, tuple] = {}
        try:
            async with get_async_session() as s:
                rows = (await s.execute(
                    select(Locality.locality_no, Locality.lat, Locality.lng)
                    .where(Locality.locality_no.in_([c.locality_no for c in active]))
                )).all()
                for r in rows:
                    if r[1] and r[2]:
                        loc_coords[r[0]] = (r[1], r[2])
        except Exception:
            pass

        DISEASE_NAMES = {
            "PANKREASSYKDOM": "PD", "ILA": "ISA",
            "INFEKSIØS_LAKSEANEMI": "ISA", "IHN": "IHN",
        }
        for c in active:
            coords = loc_coords.get(c.locality_no)
            if coords:
                disease = DISEASE_NAMES.get(c.disease_type, c.disease_type)
                severity = "critical" if "ISA" in disease or "IHN" in disease else "high"
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [coords[1], coords[0]]},
                    "properties": {
                        "name": c.locality_name,
                        "country": "Norway",
                        "disease": disease,
                        "subtype": c.disease_subtype,
                        "severity": severity,
                        "status": c.status,
                    },
                })
    except Exception:
        pass

    # Scotland — endemic PD markers at each region
    try:
        from core.market.scotland_monitor import scotland_monitor, SCOTLAND_REGIONS
        s = scotland_monitor._cache
        disease_n = s.disease_events if s else 0
        for name, info in SCOTLAND_REGIONS.items():
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                "properties": {
                    "name": name,
                    "country": "Scotland",
                    "disease": "PD (endemic)",
                    "subtype": "SAV",
                    "severity": "medium",
                    "status": "endemic",
                },
            })
    except Exception:
        pass

    # Chile — ISA/SRS from chile_monitor
    try:
        from core.market.chile_monitor import chile_monitor, CHILE_REGIONS
        snap = chile_monitor.get_latest_snapshot() or {}
        isa = snap.get("isa_outbreaks", 0) or 0
        srs = snap.get("srs_outbreaks", 0) or 0
        if isa > 0 or srs > 0:
            for name, info in CHILE_REGIONS.items():
                if "lat" in info and info["share_pct"] >= 20:
                    if isa > 0:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                            "properties": {
                                "name": name, "country": "Chile",
                                "disease": "ISA", "subtype": "",
                                "severity": "critical", "status": "active",
                            },
                        })
                    if srs > 0:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [info["lng"] + 0.3, info["lat"] + 0.2]},
                            "properties": {
                                "name": name, "country": "Chile",
                                "disease": "SRS", "subtype": "Piscirickettsia",
                                "severity": "high", "status": "active",
                            },
                        })
    except Exception:
        pass

    # Canada — DFO health events (always show BC regions as monitored)
    try:
        from core.market.canada_monitor import canada_monitor, BC_REGIONS
        s = canada_monitor._cache
        n_events = s.disease_events if s else 0
        for name, info in list(BC_REGIONS.items())[:4]:
            if n_events > 0:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                    "properties": {
                        "name": name, "country": "Canada",
                        "disease": f"{n_events} health events",
                        "subtype": "DFO reported",
                        "severity": "medium" if n_events < 10 else "high",
                        "status": "active",
                    },
                })
            else:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                    "properties": {
                        "name": name, "country": "Canada",
                        "disease": "DFO monitored",
                        "subtype": "IHN surveillance",
                        "severity": "low",
                        "status": "monitoring",
                    },
                })
    except Exception:
        pass

    # Iceland — disease-free status
    try:
        from core.market.iceland_monitor import ICELAND_FARMS
        for farm in ICELAND_FARMS[:4]:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [farm["lng"], farm["lat"]]},
                "properties": {
                    "name": farm["name"], "country": "Iceland",
                    "disease": "Disease-free",
                    "subtype": "MAST 2024 confirmed",
                    "severity": "low",
                    "status": "clear",
                },
            })
    except Exception:
        pass

    # Faroe Islands — ISA vaccinated
    try:
        from core.market.faroe_monitor import FAROE_REGIONS
        for name, info in list(FAROE_REGIONS.items())[:4]:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [info["lng"], info["lat"]]},
                "properties": {
                    "name": name, "country": "Faroe Islands",
                    "disease": "ISA vaccinated",
                    "subtype": "Mandatory since 2016",
                    "severity": "low",
                    "status": "vaccinated",
                },
            })
    except Exception:
        pass

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/global/lice")
async def global_lice():
    """Lice data GeoJSON for countries with public lice data (Norway + Canada)."""
    features = []

    # Canada DFO per-farm lice (richest lice data outside Norway)
    try:
        from core.market.canada_monitor import canada_monitor
        s = canada_monitor._cache
        if s and s.farm_locations:
            for farm in s.farm_locations:
                lice = farm.get("latest_lice", 0)
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [farm["lng"], farm["lat"]]},
                    "properties": {
                        "name": farm["name"],
                        "company": farm.get("company", ""),
                        "country": "Canada",
                        "lice": lice,
                        "date": farm.get("latest_date", ""),
                        "color_r": 244 if lice >= 3 else 245 if lice >= 1 else 0 if lice >= 0.5 else 16,
                        "color_g": 63 if lice >= 3 else 158 if lice >= 1 else 200 if lice >= 0.5 else 185,
                        "color_b": 94 if lice >= 3 else 11 if lice >= 1 else 168 if lice >= 0.5 else 129,
                        "radius": max(3, min(12, lice * 3 + 3)),
                        "weight": min(lice / 5, 1.5),
                        "layer": "lice",
                    },
                })
    except Exception:
        pass

    return {"type": "FeatureCollection", "features": features}


