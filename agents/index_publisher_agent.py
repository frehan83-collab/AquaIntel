"""
Index Publisher Agent (WS-2)
============================
Publishes the published indices (AI-STI; AI-LPI v1.0 is withdrawn, WS-19)
once per ISO week: ``build()``
computes the digest, ``readiness()`` decides per index whether its value may
become the week's immutable observation, ``store_digest()`` stores the ready
ones. The admin endpoint ``POST /api/indices/publish`` goes through the same
gate (``publish_week()``); only an explicit, audited ``force`` overrides the
grace, and no writer can store a null value.

Why an agent and not a cron line: the production topology already runs
``python main.py --agents-only`` as its ``agents`` service, so this is the one
place scheduled work lives, and the agent's health (``last_failure``,
``last_published_week``, ``waiting``) is visible to the orchestrator.

Behaviour (contracts in core/market/index_publication.py):
  * ticks hourly; acts only when ``status()`` says an index is missing for the
    current ISO week at the current method version — so a restart never
    double-publishes (the unique constraint is the second line of defence, and
    losing that race is reported as a duplicate, not a failure);
  * stores an index only when it is ready; a withheld index is named in
    ``waiting`` and retried next tick (a valid index is not withheld because
    another index's source is down);
  * a failed or incomplete publication is an error log, an ``index_publication``
    audit row and ``last_failure`` in ``health()``, and the tick raises so the
    orchestrator's error counters reflect it. Paging a human on that state
    (webhook / notification) is WS-9 — this agent logs, audits and exposes.
"""
from __future__ import annotations

import datetime as dt

import structlog

from agents.base import BaseAgent
from core.async_db import get_async_session
from core.market.bio_price_weekly import build, store_digest
from core.market.index_publication import INDEX_CODES, PUBLISH_TICK_HOURS, readiness
from core.market.index_publication import status as publication_status
from core.models import AuditLog
from core.source_lineage import to_utc

log = structlog.get_logger(__name__)


class IndexPublisherAgent(BaseAgent):
    """Publishes the published indices once per ISO week; records when it cannot."""

    name = "index_publisher"
    interval_seconds = PUBLISH_TICK_HOURS * 3600

    def __init__(self) -> None:
        super().__init__()
        self.last_failure: dict | None = None
        self.last_published_week: str | None = None
        self.waiting: dict | None = None

    async def _fail(self, now: dt.datetime, week: str, stage: str, exc: Exception) -> None:
        self.last_failure = {
            "week": week, "stage": stage, "reason": str(exc)[:200], "at": now.isoformat(),
        }
        self.log.error("index_publisher.publication_failed", week=week, stage=stage, error=str(exc))
        await self._audit(f"Index publication FAILED for {week} ({stage}): {exc}")

    async def _safe_status(self, now: dt.datetime) -> dict:
        """status() reports store errors itself; guard against anything else."""
        try:
            return await publication_status(now=now)
        except Exception as exc:  # pragma: no cover - programming errors only
            return {
                "week": None, "current_week_published": False,
                "missing": list(INDEX_CODES), "reason": f"status unreadable: {exc}",
            }

    async def tick(self, now: dt.datetime | None = None) -> None:
        now = to_utc(now)
        state = await publication_status(now=now)
        week = state["week"]
        if state["current_week_published"]:
            self.last_failure = None
            self.waiting = None
            self.log.debug("index_publisher.current_week_published", week=week)
            return

        try:
            digest = await build(as_of=now)  # compute only; nothing stored yet
        except Exception as exc:
            await self._fail(now, week, "build", exc)
            raise

        ready = readiness(digest, now=now)
        to_store = [code for code in ready["store"] if code in state["missing"]]
        if not to_store:
            self.waiting = {"week": week, "reason": ready["reason"], "at": now.isoformat()}
            self.log.info("index_publisher.waiting", week=week, reason=ready["reason"])
            return

        self.log.info(
            "index_publisher.publishing", week=week, store=to_store,
            withheld=ready["withheld"], degraded=ready["degraded"],
        )
        try:
            storage = await store_digest(digest, codes=to_store)
        except Exception as exc:
            after = await self._safe_status(now)
            if not after.get("reason") and not any(
                code in after.get("missing", []) for code in to_store
            ):
                # Lost the race to another writer (admin publish, a second replica):
                # every index we tried IS published, so this is not a failure.
                self.last_failure = None
                self.last_published_week = week
                self.log.info(
                    "index_publisher.published_by_another_writer", week=week, error=str(exc)
                )
                await self._audit(f"Indices for {week} were published by another writer ({exc})")
                return
            await self._fail(now, week, "store", exc)
            raise

        after = await self._safe_status(now)
        if after.get("reason"):
            # The write succeeded (store_digest returned) but the store could not be
            # re-read: report that — never claim the rows are missing.
            self.last_failure = None
            self.last_published_week = week
            self.log.warning(
                "index_publisher.store_unreadable_after_publish",
                week=week, storage=storage, reason=after["reason"],
            )
            await self._audit(
                f"Published indices for {week} ({self._fmt(storage)}); store unreadable "
                f"afterwards: {after['reason']}"
            )
            return

        unexpected = [code for code in after["missing"] if code in to_store]
        if not unexpected:
            self.last_failure = None
            self.last_published_week = week
            self.waiting = (
                {"week": week, "reason": ready["reason"], "at": now.isoformat()}
                if ready["withheld"]
                else None
            )
            self.log.info(
                "index_publisher.published", week=week, storage=storage,
                withheld=ready["withheld"],
            )
            notes = []
            if ready["degraded"]:
                notes.append(
                    f"degraded this week: {', '.join(ready['degraded'])} (provenance says why)"
                )
            if ready["withheld"]:
                notes.append("withheld: " + ready["reason"])
            await self._audit(
                f"Published indices for {week}: {self._fmt(storage)}"
                + ("; " + "; ".join(notes) if notes else "")
            )
            return

        # store_digest returned, yet the store still lacks an index we stored: a
        # store inconsistency — fail loudly so the orchestrator counts it.
        exc = RuntimeError(
            f"index publication incomplete for {week}: still missing after store: "
            + ", ".join(unexpected)
        )
        await self._fail(now, week, "verify", exc)
        raise exc

    @staticmethod
    def _fmt(storage: dict) -> str:
        return ", ".join(f"{code}={status}" for code, status in storage.items())

    def health(self) -> dict:
        data = super().health()
        data["last_failure"] = self.last_failure
        data["last_published_week"] = self.last_published_week
        data["waiting"] = self.waiting
        return data

    @staticmethod
    async def _audit(detail: str) -> None:
        """Best-effort audit trail; an audit failure must not mask the publication."""
        try:
            async with get_async_session() as session:
                session.add(AuditLog(event_type="index_publication", detail=detail))
        except Exception as exc:
            log.warning("index_publisher.audit_failed", error=str(exc))
