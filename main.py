"""
FishIntel — Aquaculture Intelligence Platform
===============================================
Main orchestrator. Launches all agents concurrently and runs the FastAPI server.
https://fishintel.io

Usage:
    python main.py              # Run all agents + API
    python main.py --api-only   # API server only
    python main.py --agents-only # Agents only (no API)
"""
from __future__ import annotations

import os
os.environ["PYTENSOR_FLAGS"] = "device=cpu,floatX=float64,optimizer=fast_compile,cxx="

import asyncio
import signal
import sys

import click
import structlog
import uvicorn

from config.logging_config import setup_logging
from config.settings import settings
from core.models import init_db
from agents.data_ingest import DataIngestAgent
from agents.exposure_mapper import ExposureMapperAgent
from agents.correlation_engine import CorrelationEngineAgent
from agents.signal_generator import SignalGeneratorAgent
from agents.prediction_agent import PredictionAgent
from agents.historical_backfill import HistoricalBackfillAgent
from execution.execution_agent import ExecutionAgent
from compliance.compliance_agent import ComplianceAgent
from agents.bloom_agent import BloomAgent
from agents.market_hedger_agent import MarketHedgerAgent
from core.twin.self_evolve import SelfEvolvingAgent
from agents.intelligence_agent import IntelligenceAgent

log = structlog.get_logger("openclaw")


async def _sentiment_polling_loop() -> None:
    """Background loop that polls news feeds for sentiment analysis."""
    from core.market.sentiment_engine import sentiment_engine
    log.info("sentiment.polling_started", interval_minutes=15)
    while True:
        try:
            articles = await sentiment_engine.poll_feeds()
            if articles:
                log.info("sentiment.poll_complete", new_articles=len(articles))
        except Exception as exc:
            log.warning("sentiment.poll_error", error=str(exc))
        await asyncio.sleep(15 * 60)  # poll every 15 minutes


async def run_agents() -> None:
    """Start all agents concurrently."""
    log.info("orchestrator.starting_agents")

    # Create agent instances
    ingest = DataIngestAgent()
    exposure = ExposureMapperAgent()
    correlation = CorrelationEngineAgent()
    signal_gen = SignalGeneratorAgent(correlation)
    prediction = PredictionAgent()
    backfill = HistoricalBackfillAgent(start_year=2020)
    execution = ExecutionAgent()
    compliance = ComplianceAgent()
    bloom = BloomAgent()
    hedger = MarketHedgerAgent()
    self_evolve = SelfEvolvingAgent()
    intelligence = IntelligenceAgent()

    agents = [
        ingest, exposure, correlation, signal_gen,
        prediction, backfill, execution, compliance,
        bloom, hedger, self_evolve, intelligence,
    ]

    # Run all agents as concurrent tasks
    tasks = [asyncio.create_task(agent.start()) for agent in agents]

    # Start sentiment engine polling as background task (non-blocking)
    sentiment_task = asyncio.create_task(_sentiment_polling_loop())
    tasks.append(sentiment_task)

    # Graceful shutdown: SIGTERM (docker stop / compose down) and SIGINT must
    # run the cleanup below instead of the process dying mid-run (the arch
    # report's lifespan finding: agents had no shutdown handler at all).
    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_requested.set)
        except (NotImplementedError, RuntimeError):  # Windows ProactorEventLoop
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop_requested.set))

    gather_task = asyncio.ensure_future(asyncio.gather(*tasks))
    stop_task = asyncio.ensure_future(stop_requested.wait())
    try:
        await asyncio.wait({gather_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if stop_task.done() and not gather_task.done():
            log.info("orchestrator.shutdown_signal")
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            gather_task.result()  # propagate agent failures
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("orchestrator.stopping")
    finally:
        for agent in agents:
            agent.stop()
        await ingest.shutdown()
        await exposure.shutdown()
        await backfill.shutdown()
        # Shutdown sentiment engine HTTP client
        try:
            from core.market.sentiment_engine import sentiment_engine
            await sentiment_engine.shutdown()
        except Exception:
            pass
        stop_task.cancel()
        log.info("orchestrator.stopped")


def run_api(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI server."""
    from core.api import app
    uvicorn.run(app, host=host, port=port)


@click.command()
@click.option("--api-only", is_flag=True, help="Run API server only")
@click.option("--agents-only", is_flag=True, help="Run agents only")
@click.option("--api-port", default=8000, help="API server port")
def main(api_only: bool, agents_only: bool, api_port: int) -> None:
    """OpenClaw Lice-Impact Arbitrage Bot"""
    setup_logging()
    init_db()

    log.info(
        "openclaw.start",
        mode="api" if api_only else "agents" if agents_only else "full",
        broker=settings.broker_mode,
        poll_interval=settings.poll_interval_minutes,
    )

    if api_only:
        run_api(port=api_port)
    elif agents_only:
        asyncio.run(run_agents())
    else:
        # Run both: agents in background, API in main thread
        # For production, use separate processes or Docker services
        import threading

        agent_thread = threading.Thread(
            target=lambda: asyncio.run(run_agents()),
            daemon=True,
        )
        agent_thread.start()
        run_api(port=api_port)


if __name__ == "__main__":
    main()
