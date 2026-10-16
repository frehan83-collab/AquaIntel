"""
Base agent class for AquaIntel multi-agent architecture.

Each agent is an autonomous unit with its own run-loop, health status,
and structured logging. Agents communicate via the shared database and
an in-process event bus (asyncio.Queue).
"""
from __future__ import annotations

import asyncio
import datetime as dt
from abc import ABC, abstractmethod
from typing import Any

import structlog

log = structlog.get_logger()


class AgentStatus:
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


class BaseAgent(ABC):
    """Every AquaIntel agent inherits from this."""

    name: str = "base_agent"
    interval_seconds: int = 900  # default 15 min

    def __init__(self) -> None:
        self.status = AgentStatus.IDLE
        self.last_run: dt.datetime | None = None
        self.run_count: int = 0
        self.error_count: int = 0
        self._stop_event = asyncio.Event()
        self.log = log.bind(agent=self.name)

    # ── lifecycle ─────────────────────────────────────────────────────
    async def start(self) -> None:
        """Run the agent loop until stopped."""
        self.log.info("agent.start", interval=self.interval_seconds)
        self.status = AgentStatus.RUNNING
        while not self._stop_event.is_set():
            try:
                await self.tick()
                self.last_run = dt.datetime.now(dt.UTC)
                self.run_count += 1
            except Exception as exc:
                self.error_count += 1
                self.status = AgentStatus.ERROR
                self.log.error("agent.tick_error", error=str(exc), exc_info=True)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.interval_seconds
                )
            except asyncio.TimeoutError:
                pass  # normal — timeout means "time for next tick"

        self.status = AgentStatus.STOPPED
        self.log.info("agent.stopped")

    def stop(self) -> None:
        self._stop_event.set()

    @abstractmethod
    async def tick(self) -> None:
        """One cycle of the agent's work. Subclasses implement this."""
        ...

    def health(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "status": self.status,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
        }
