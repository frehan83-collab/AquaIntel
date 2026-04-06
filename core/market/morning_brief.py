"""
Morning Brief Engine
=====================
Generates a daily market intelligence digest in under 60 seconds of reading.
This is the #1 retention feature — creates the Bloomberg-style daily check-in habit.

Components (all from live data):
  1. SSB salmon spot price + change
  2. Oslo Børs equity movers (MOWI, SALM, LSG, GSF, BAKKA)
  3. Lice pressure summary (national avg, sites above threshold)
  4. Regime alerts (traffic light changes predicted)
  5. Feed cost pressure (FRED composite index)
  6. AIS vessel activity (harvest/treatment signals)
  7. Bloom risk status (CRITICAL/HIGH count)
  8. Currency exposure (NOK/USD)
  9. Top actionable insight (AI-generated one-liner)
  10. ESG movers (biggest score changes)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass
class BriefSection:
    """One section of the morning brief."""
    title: str
    icon: str  # emoji for display
    headline: str
    detail: str = ""
    sentiment: str = "neutral"  # bullish / bearish / neutral / alert
    value: str = ""


@dataclass
class MorningBrief:
    """Complete daily morning brief."""
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    greeting: str = ""
    sections: list[BriefSection] = field(default_factory=list)
    top_insight: str = ""
    market_mood: str = "neutral"  # bullish / bearish / mixed / cautious


class MorningBriefEngine:
    """Compiles the daily morning brief from all platform data sources."""

    _cache: MorningBrief | None = None
    _cache_time: dt.datetime | None = None
    _cache_ttl = dt.timedelta(minutes=30)
    _prev_esg_scores: dict[str, float] = {}  # day-over-day ESG tracking

    async def generate(self) -> MorningBrief:
        """Generate a fresh morning brief from live data."""
        now = dt.datetime.now(dt.UTC)
        if self._cache and self._cache_time and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        sections: list[BriefSection] = []
        signals_bullish = 0
        signals_bearish = 0

        # ── 1. Salmon Price ──────────────────────────────────────────
        try:
            from core.market.ssb_price_client import ssb_price_client
            spot = await ssb_price_client.get_current_spot()
            history = await ssb_price_client.get_price_history(n_weeks=4)
            prev = history[-2]["price_nok"] if len(history) >= 2 else spot
            change = ((spot - prev) / max(prev, 1)) * 100 if prev > 0 else 0
            direction = "up" if change > 0.5 else "down" if change < -0.5 else "flat"
            sentiment = "bullish" if change > 1 else "bearish" if change < -1 else "neutral"
            if sentiment == "bullish": signals_bullish += 1
            elif sentiment == "bearish": signals_bearish += 1

            sections.append(BriefSection(
                title="Salmon Price",
                icon="fish",
                headline=f"NOK {spot:.1f}/kg ({'+' if change > 0 else ''}{change:.1f}% WoW)",
                detail=f"SSB export price {'rose' if direction == 'up' else 'fell' if direction == 'down' else 'stable'} week-on-week",
                sentiment=sentiment,
                value=f"{spot:.1f}",
            ))
        except Exception as exc:
            log.debug("brief.price_failed", error=str(exc)[:60])

        # ── 2. Equity Movers ─────────────────────────────────────────
        try:
            from core.market.salmon_price import get_latest_prices
            prices = await get_latest_prices()
            equities = {k: v for k, v in prices.items() if k.endswith(".OL") and v}
            if equities:
                top = max(equities.items(), key=lambda x: x[1])
                sections.append(BriefSection(
                    title="Oslo Equities",
                    icon="chart",
                    headline=f"{len(equities)} tickers tracked",
                    detail=", ".join(f"{k.replace('.OL','')}: NOK {v:.0f}" for k, v in equities.items()),
                    sentiment="neutral",
                ))
        except Exception as exc:
            log.debug("brief.equity_failed", error=str(exc)[:60])

        # ── 3. Lice Pressure ─────────────────────────────────────────
        try:
            from core.models import LiceRecord
            from core.async_db import get_async_session
            from sqlalchemy import select, func
            async with get_async_session() as s:
                latest = (await s.execute(
                    select(LiceRecord.year, LiceRecord.week)
                    .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                    .limit(1)
                )).first()
                if latest:
                    stats = (await s.execute(
                        select(
                            func.avg(LiceRecord.avg_adult_female_lice),
                            func.count(LiceRecord.id),
                        ).where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                            LiceRecord.avg_adult_female_lice.isnot(None),
                        )
                    )).first()
                    above = (await s.execute(
                        select(func.count(LiceRecord.id)).where(
                            LiceRecord.year == latest[0],
                            LiceRecord.week == latest[1],
                            LiceRecord.avg_adult_female_lice > 0.5,
                        )
                    )).scalar() or 0

                    avg_lice = float(stats[0] or 0)
                    n_sites = int(stats[1] or 0)
                    pct_above = (above / max(n_sites, 1)) * 100

                    lice_sentiment = "alert" if pct_above > 20 else "bearish" if avg_lice > 0.3 else "neutral"
                    if lice_sentiment == "alert": signals_bearish += 2
                    elif lice_sentiment == "bearish": signals_bearish += 1

                    sections.append(BriefSection(
                        title="Lice Pressure",
                        icon="bug",
                        headline=f"Avg {avg_lice:.3f} lice/fish — {above} sites above 0.5 limit ({pct_above:.0f}%)",
                        detail=f"Week {latest[1]}/{latest[0]} — {n_sites} reporting sites",
                        sentiment=lice_sentiment,
                        value=f"{avg_lice:.3f}",
                    ))
        except Exception as exc:
            log.debug("brief.lice_failed", error=str(exc)[:60])

        # ── 4. Regime Alerts ─────────────────────────────────────────
        try:
            from core.market.regime_detector import regime_detector
            alerts = regime_detector.get_alerts()
            if alerts:
                signals_bearish += len(alerts)
                alert_text = ", ".join(
                    f"PA{a['production_area']}: {a['current']}\u2192{a['predicted']}"
                    for a in alerts[:3]
                )
                sections.append(BriefSection(
                    title="Regime Alerts",
                    icon="shield",
                    headline=f"{len(alerts)} color-change prediction{'s' if len(alerts) > 1 else ''}",
                    detail=alert_text,
                    sentiment="alert",
                ))
            else:
                sections.append(BriefSection(
                    title="Regime Status",
                    icon="shield",
                    headline="All 13 PAs stable — no color changes predicted",
                    sentiment="neutral",
                ))
        except Exception as exc:
            log.debug("brief.regime_failed", error=str(exc)[:60])

        # ── 4b. Disease Outbreaks (Mattilsynet) ──────────────────────
        try:
            from core.market.mattilsynet_client import mattilsynet_client
            cases = await mattilsynet_client.fetch_disease_cases(limit=50)
            active = [c for c in cases if c.status == "active"]
            isa_count = sum(1 for c in active if "ILA" in c.disease_type or "ISA" in c.disease_type or "LAKSEANEMI" in c.disease_type)
            pd_count = sum(1 for c in active if "PANKREAS" in c.disease_type)

            if active:
                disease_sentiment = "alert" if isa_count > 0 else "bearish"
                if disease_sentiment == "alert": signals_bearish += 2
                else: signals_bearish += 1

                headline = f"{len(active)} active outbreaks"
                if isa_count > 0:
                    headline += f" — {isa_count} ISA (trade-restricting)"
                if pd_count > 0:
                    headline += f", {pd_count} PD"

                sections.append(BriefSection(
                    title="Disease Outbreaks",
                    icon="shield",
                    headline=headline,
                    detail="Source: Mattilsynet (Norwegian Food Safety Authority)",
                    sentiment=disease_sentiment,
                ))
            else:
                sections.append(BriefSection(
                    title="Disease Status",
                    icon="shield",
                    headline="No active disease outbreaks reported",
                    sentiment="neutral",
                ))
        except Exception as exc:
            log.debug("brief.disease_failed", error=str(exc)[:60])

        # ── 5. Feed Cost ─────────────────────────────────────────────
        try:
            from core.market.feed_cost_engine import feed_cost_engine
            feed = await feed_cost_engine.fetch_prices()
            latest_feed = feed_cost_engine.get_latest()
            if latest_feed:
                margin = latest_feed["margin_pct"]
                trend = latest_feed["margin_trend"]
                feed_sentiment = "bearish" if margin < 15 else "bullish" if trend == "improving" else "neutral"
                if feed_sentiment == "bearish": signals_bearish += 1

                sections.append(BriefSection(
                    title="Feed & Margins",
                    icon="wheat",
                    headline=f"Feed NOK {latest_feed['feed_cost_nok_per_kg']:.1f}/kg — Margin {margin:.0f}% ({trend})",
                    detail=f"Production cost NOK {latest_feed['production_cost_nok_per_kg_salmon']:.1f}/kg salmon",
                    sentiment=feed_sentiment,
                    value=f"{margin:.0f}%",
                ))
        except Exception as exc:
            log.debug("brief.feed_failed", error=str(exc)[:60])

        # ── 6. AIS Activity ──────────────────────────────────────────
        try:
            from core.market.ais_tracker import ais_tracker
            tracks = ais_tracker.get_active_tracks()
            harvest = ais_tracker.get_harvest_signals(72)
            treatment = ais_tracker.get_treatment_signals(72)
            if tracks:
                sections.append(BriefSection(
                    title="Vessel Activity",
                    icon="ship",
                    headline=f"{len(tracks)} vessels tracked — {len(harvest)} harvest, {len(treatment)} treatment signals (72h)",
                    sentiment="neutral" if len(harvest) < 3 else "bearish",
                ))
        except Exception as exc:
            log.debug("brief.ais_failed", error=str(exc)[:60])

        # ── 7. Bloom Risk ────────────────────────────────────────────
        try:
            from core.bloom.models import BloomRiskAssessment
            from core.models import Session as S2
            with S2() as s:
                high_risk = s.query(BloomRiskAssessment).filter(
                    BloomRiskAssessment.risk_level.in_(["HIGH", "CRITICAL"])
                ).count()
                if high_risk > 0:
                    signals_bearish += 1
                    sections.append(BriefSection(
                        title="Bloom Risk",
                        icon="leaf",
                        headline=f"{high_risk} sites at HIGH/CRITICAL bloom risk",
                        sentiment="alert",
                    ))
                else:
                    sections.append(BriefSection(
                        title="Bloom Status",
                        icon="leaf",
                        headline="All clear — no high-risk bloom events",
                        sentiment="neutral",
                    ))
        except Exception as exc:
            log.debug("brief.bloom_failed", error=str(exc)[:60])

        # ── 8. Currency ──────────────────────────────────────────────
        try:
            from core.market.macro_intelligence import macro_intelligence
            snap = await macro_intelligence.fetch()
            nok = snap.series.get("nok_usd", 0)
            nok_yoy = snap.yoy_changes.get("nok_usd", 0)
            if nok > 0:
                sections.append(BriefSection(
                    title="Currency",
                    icon="currency",
                    headline=f"NOK/USD {nok:.2f} ({'+' if nok_yoy > 0 else ''}{nok_yoy:.1f}% YoY)",
                    detail="Weaker NOK = higher export revenue, costlier feed imports" if nok_yoy > 2 else "",
                    sentiment="neutral",
                ))
        except Exception as exc:
            log.debug("brief.currency_failed", error=str(exc)[:60])

        # ── 9. ESG Movers ───────────────────────────────────────────
        try:
            from core.market.esg_scorer import esg_scorer
            esg_all = esg_scorer.compute_all()
            current_esg = {s.company_name: s.total for s in esg_all}

            if self._prev_esg_scores:
                movers = []
                for name, score in current_esg.items():
                    prev = self._prev_esg_scores.get(name, score)
                    delta = score - prev
                    if abs(delta) >= 1.0:
                        movers.append((name, delta, score))
                movers.sort(key=lambda x: abs(x[1]), reverse=True)

                if movers:
                    top3 = movers[:3]
                    detail_lines = [f"{m[0]}: {'+'if m[1]>0 else ''}{m[1]:.1f} → {m[2]:.0f}" for m in top3]
                    best = top3[0]
                    sections.append(BriefSection(
                        title="ESG Movers",
                        icon="leaf",
                        headline=f"{len(movers)} ESG score changes — {best[0]} {'improved' if best[1] > 0 else 'dropped'} by {abs(best[1]):.1f} pts",
                        detail="; ".join(detail_lines),
                        sentiment="bullish" if best[1] > 0 else "bearish",
                    ))
                else:
                    sections.append(BriefSection(
                        title="ESG Movers",
                        icon="leaf",
                        headline="ESG scores stable — no significant changes",
                        sentiment="neutral",
                    ))

            self._prev_esg_scores = current_esg
        except Exception as exc:
            log.debug("brief.esg_movers_failed", error=str(exc)[:60])

        # ── 10. Marine Heatwave Risk (Session 25) ─────────────────────
        try:
            from core.market.climate_risk_engine import climate_risk_engine
            hw_result = await climate_risk_engine.marine_heatwave_risk()
            if isinstance(hw_result, dict):
                hw_warnings = hw_result.get("warning_count", 0) + hw_result.get("critical_count", 0)
                if hw_warnings > 0:
                    sections.append(BriefSection(
                        title="Marine Heatwave",
                        icon="thermometer",
                        headline=f"{hw_result.get('overall_status', 'WATCH')} — {hw_warnings} PA(s) elevated SST",
                        detail=f"Warm water accelerates lice reproduction and disease risk. "
                               f"{hw_result.get('critical_count', 0)} critical, "
                               f"{hw_result.get('warning_count', 0)} warning PAs.",
                        sentiment="alert" if hw_result.get("critical_count", 0) > 0 else "bearish",
                    ))
                    signals_bearish += 1
        except Exception as exc:
            log.debug("brief.heatwave_failed", error=str(exc)[:60])

        # ── 11. Treatment Resistance Alert (Session 25) ────────────────
        try:
            from core.market.resistance_tracker import resistance_tracker
            res_map = await resistance_tracker.get_resistance_map()
            if isinstance(res_map, dict):
                high_risk = [
                    p for p in res_map.get("production_areas", [])
                    if any(m.get("risk_level") == "HIGH" for m in p.get("methods", []))
                ]
                if high_risk:
                    sections.append(BriefSection(
                        title="Resistance Alert",
                        icon="shield",
                        headline=f"High treatment resistance in {len(high_risk)} PA(s)",
                        detail=f"Consider rotating treatment methods. "
                               f"Affected: {', '.join(f'PA-{p['pa']}' for p in high_risk[:3])}.",
                        sentiment="bearish",
                    ))
        except Exception as exc:
            log.debug("brief.resistance_failed", error=str(exc)[:60])

        # ── 12. Early Warning (Anomaly Detection) ─────────────────────
        try:
            from core.market.anomaly_engine import anomaly_engine
            report = await anomaly_engine.compute()
            if report.composite_score >= 30:
                sections.append(BriefSection(
                    title="Early Warning",
                    icon="alert",
                    headline=f"Risk Score {report.composite_score}/100 — {report.risk_level}",
                    detail=report.summary,
                    sentiment="alert" if report.composite_score >= 70 else "bearish" if report.composite_score >= 50 else "neutral",
                ))
        except Exception as exc:
            log.debug("brief.anomaly_failed", error=str(exc)[:60])

        # ── Market Mood ──────────────────────────────────────────────
        if signals_bullish > signals_bearish + 1:
            mood = "bullish"
        elif signals_bearish > signals_bullish + 1:
            mood = "bearish"
        elif signals_bearish > 0 and signals_bullish > 0:
            mood = "mixed"
        else:
            mood = "neutral"

        # ── Top Insight (AI-synthesized multi-signal) ──────────────
        drivers = []
        for sec in sections:
            if sec.sentiment == "alert":
                drivers.append(sec.headline.split("—")[0].strip() if "—" in sec.headline else sec.headline[:50])
            elif sec.sentiment == "bearish":
                drivers.append(sec.headline.split("—")[0].strip() if "—" in sec.headline else sec.headline[:50])
        bullish_drivers = []
        for sec in sections:
            if sec.sentiment == "bullish":
                bullish_drivers.append(sec.headline.split("—")[0].strip() if "—" in sec.headline else sec.headline[:50])

        if drivers:
            top_insight = f"Key risks: {'; '.join(drivers[:3])}."
            if bullish_drivers:
                top_insight += f" Offsetting: {bullish_drivers[0]}."
        elif bullish_drivers:
            top_insight = f"Positive signals: {'; '.join(bullish_drivers[:2])}. No urgent risks detected."
        else:
            top_insight = "Markets stable — no urgent signals today. All biological and supply indicators within normal ranges."

        # ── Greeting ─────────────────────────────────────────────────
        hour = now.hour
        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        weekday = now.strftime("%A")
        date_str = now.strftime("%B %d, %Y")

        brief = MorningBrief(
            greeting=f"{time_greeting} — {weekday}, {date_str}",
            sections=sections,
            top_insight=top_insight,
            market_mood=mood,
        )

        self._cache = brief
        self._cache_time = now
        log.info("brief.generated", sections=len(sections), mood=mood)
        return brief

    def to_dict(self, brief: MorningBrief) -> dict:
        """Convert to API-friendly dict."""
        return {
            "generated_at": brief.generated_at.isoformat(),
            "greeting": brief.greeting,
            "market_mood": brief.market_mood,
            "top_insight": brief.top_insight,
            "sections": [
                {
                    "title": s.title,
                    "icon": s.icon,
                    "headline": s.headline,
                    "detail": s.detail,
                    "sentiment": s.sentiment,
                    "value": s.value,
                }
                for s in brief.sections
            ],
        }


# Singleton
morning_brief_engine = MorningBriefEngine()
