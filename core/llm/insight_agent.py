"""
Autonomous Insight Agent
=========================
Background OpenClaw agent that:
  1. Monitors new API data for threshold breaches
  2. Triggers LLM analysis on notable events
  3. Pushes personalized insights via dashboard and notifications

Runs every 15 minutes alongside the data ingest agent.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select, func

from agents.base import BaseAgent
from core.llm.client import llm_client
from core.llm.prompts import SYSTEM_AQUACULTURE_EXPERT, INSIGHT_ALERT_PROMPT
from core.models import LiceRecord, Locality, CompanyExposure
from core.async_db import get_async_session

import structlog

log = structlog.get_logger(__name__)

# ── Alert thresholds ─────────────────────────────────────────────────
LICE_CRITICAL = 1.0       # alert on any site above this
LICE_REGULATORY = 0.5     # regulatory limit
LICE_JUMP_PCT = 50        # alert if weekly avg jumps >50%
TEMP_ANOMALY_C = 2.0      # alert if temp deviates >2°C from seasonal norm


@dataclass
class Insight:
    """A generated insight for the dashboard."""
    id: str
    timestamp: dt.datetime
    urgency: str  # routine/notable/urgent/critical
    title: str
    body: str
    ticker: str | None = None
    locality_no: int | None = None
    data_points: dict = field(default_factory=dict)


class InsightAgent(BaseAgent):
    name = "insight_agent"
    interval_seconds = 900  # 15 min

    def __init__(self) -> None:
        super().__init__()
        self.latest_insights: list[Insight] = []
        self._prev_averages: dict[str, float] = {}

    async def tick(self) -> None:
        self.log.info("insight.tick_start")
        alerts = await self._detect_alerts()

        if not alerts:
            self.log.info("insight.no_alerts")
            return

        new_insights = []
        for alert in alerts[:5]:  # max 5 LLM calls per cycle
            insight = await self._generate_insight(alert)
            if insight:
                new_insights.append(insight)

        self.latest_insights = new_insights + self.latest_insights
        self.latest_insights = self.latest_insights[:50]  # keep recent 50

        self.log.info("insight.tick_done", new_insights=len(new_insights))

    async def _detect_alerts(self) -> list[dict]:
        """Scan for threshold breaches and notable patterns."""
        alerts = []

        async with get_async_session() as s:
            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            if not latest:
                return []

            year, week = latest

            # 1. Critical lice levels (any site > 1.0)
            result = await s.execute(
                select(LiceRecord, Locality)
                .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                .where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice > LICE_CRITICAL,
                )
            )
            critical = result.all()

            for lice, loc in critical:
                # Find which company
                result = await s.execute(
                    select(CompanyExposure.ticker)
                    .where(CompanyExposure.locality_no == lice.locality_no)
                )
                comp = result.scalar_one_or_none()

                alerts.append({
                    "type": "critical_lice",
                    "urgency": "critical",
                    "locality_no": lice.locality_no,
                    "locality_name": loc.name,
                    "ticker": comp,
                    "lice_value": lice.avg_adult_female_lice,
                    "temperature": lice.sea_temp_c,
                    "week": f"{year}-W{week:02d}",
                })

            # 2. Company-level weekly jumps
            for ticker in ["MOWI", "SALM", "LSG", "GSF"]:
                result = await s.execute(
                    select(CompanyExposure.locality_no)
                    .where(CompanyExposure.ticker == ticker)
                )
                locs = result.scalars().all()

                if not locs:
                    continue

                result = await s.execute(
                    select(func.avg(LiceRecord.avg_adult_female_lice))
                    .where(
                        LiceRecord.year == year,
                        LiceRecord.week == week,
                        LiceRecord.locality_no.in_(list(locs)),
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                )
                current_avg = result.scalar() or 0

                prev_avg = self._prev_averages.get(ticker, 0)
                if prev_avg > 0.05 and current_avg > 0:
                    change_pct = (current_avg - prev_avg) / prev_avg * 100
                    if abs(change_pct) > LICE_JUMP_PCT:
                        alerts.append({
                            "type": "weekly_jump",
                            "urgency": "urgent" if change_pct > 0 else "notable",
                            "ticker": ticker,
                            "prev_avg": round(prev_avg, 3),
                            "current_avg": round(current_avg, 3),
                            "change_pct": round(change_pct, 1),
                            "week": f"{year}-W{week:02d}",
                        })

                self._prev_averages[ticker] = current_avg

            # 3. Sites newly above regulatory limit
            result = await s.execute(
                select(func.count(LiceRecord.id))
                .where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice > LICE_REGULATORY,
                )
            )
            above_limit = result.scalar() or 0

            if above_limit > 10:
                alerts.append({
                    "type": "regulatory_breach_count",
                    "urgency": "notable",
                    "count": above_limit,
                    "week": f"{year}-W{week:02d}",
                })

        return sorted(alerts, key=lambda a: {"critical": 0, "urgent": 1, "notable": 2, "routine": 3}.get(a.get("urgency", "routine"), 4))

    async def _generate_insight(self, alert: dict) -> Insight | None:
        """Use LLM to generate a contextual insight from an alert."""
        import json

        prompt = INSIGHT_ALERT_PROMPT.format(
            alert_data=json.dumps(alert, indent=2, default=str)
        )

        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=512,
            temperature=0.2,
        )

        if not resp.content or resp.content.startswith("[LLM"):
            return None

        # Build title from alert type
        titles = {
            "critical_lice": f"Critical lice at locality {alert.get('locality_no', '?')}",
            "weekly_jump": f"{alert.get('ticker', '?')} lice {alert.get('change_pct', 0):+.0f}% week-over-week",
            "regulatory_breach_count": f"{alert.get('count', 0)} sites above regulatory limit",
        }

        return Insight(
            id=f"ins_{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M%S')}_{alert.get('type', '')}",
            timestamp=dt.datetime.now(dt.UTC),
            urgency=alert.get("urgency", "routine"),
            title=titles.get(alert["type"], alert["type"]),
            body=resp.content,
            ticker=alert.get("ticker"),
            locality_no=alert.get("locality_no"),
            data_points=alert,
        )
