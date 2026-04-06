"""
Sentiment Engine — NLP on Aquaculture News
=============================================
Real-time sentiment analysis on aquaculture industry news sources.
Extracts named entities, classifies sentiment, and generates
trading signals from news flow.

Sources monitored:
  - IntraFish (intrafish.com) — global aquaculture news
  - iLaks (ilaks.no) — Norwegian salmon industry
  - Undercurrent News (undercurrentnews.com) — seafood trade
  - Fiskeribladet (fiskeribladet.no) — Norwegian fisheries
  - E24 (e24.no) — Norwegian financial news
  - DN (dn.no) — Norwegian business daily

Alpha: News sentiment moves stocks before data. Disease outbreaks,
regulatory changes, M&A rumors, and executive commentary create
30-60 min lead on market reaction.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)


class Sentiment(str, Enum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


class NewsCategory(str, Enum):
    DISEASE_OUTBREAK = "disease_outbreak"
    LICE_REPORT = "lice_report"
    REGULATORY = "regulatory"
    EARNINGS = "earnings"
    MERGER_ACQUISITION = "merger_acquisition"
    TREATMENT = "treatment"
    SUSTAINABILITY = "sustainability"
    PRICE_MOVEMENT = "price_movement"
    SUPPLY_DEMAND = "supply_demand"
    TECHNOLOGY = "technology"
    EXECUTIVE = "executive"
    CLIMATE = "climate"
    GENERAL = "general"


@dataclass
class NewsArticle:
    """Parsed news article with NLP annotations."""
    id: str  # hash of url
    title: str
    summary: str
    url: str
    source: str
    published_at: Optional[dt.datetime]
    fetched_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    # NLP annotations
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0  # -1 to +1
    category: NewsCategory = NewsCategory.GENERAL
    companies_mentioned: list[str] = field(default_factory=list)
    tickers_affected: list[str] = field(default_factory=list)
    production_areas: list[int] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    market_impact_score: float = 0.0  # 0-1, how much this might move stocks
    confidence: float = 0.0


@dataclass
class SentimentSignal:
    """Aggregated sentiment signal for trading."""
    generated_at: dt.datetime
    ticker: str
    sentiment: Sentiment
    score: float  # -1 to +1
    n_articles: int
    dominant_category: NewsCategory
    top_headlines: list[str]
    signal_strength: float  # 0-1
    rationale: str


# ── RSS Feed Sources ──────────────────────────────────────────────
NEWS_FEEDS = [
    {"name": "IntraFish", "url": "https://www.intrafish.com/rss", "lang": "en", "weight": 1.0},
    {"name": "IntraFish NO", "url": "https://www.intrafish.no/rss", "lang": "no", "weight": 1.2},
    {"name": "iLaks", "url": "https://ilaks.no/feed/", "lang": "no", "weight": 1.3},
    {"name": "Fiskeribladet", "url": "https://www.fiskeribladet.no/rss", "lang": "no", "weight": 1.1},
    {"name": "Undercurrent", "url": "https://www.undercurrentnews.com/feed/", "lang": "en", "weight": 0.9},
    {"name": "Kyst.no", "url": "https://www.kyst.no/rss", "lang": "no", "weight": 1.0},
]

# ── Entity Recognition Patterns ──────────────────────────────────
COMPANY_PATTERNS = {
    "MOWI": [r"\bMowi\b", r"\bMarine Harvest\b", r"\bmowi\b"],
    "SALM": [r"\bSalMar\b", r"\bSALM\b", r"\bsalmar\b", r"\bInnovaMar\b"],
    "LSG": [r"\bLerøy\b", r"\bLeroy\b", r"\bLSG\b", r"\blerøy\b"],
    "GSF": [r"\bGrieg Seafood\b", r"\bGrieg\b", r"\bGSF\b"],
    "NRS": [r"\bNorway Royal Salmon\b", r"\bNRS\b"],
    "AUSS": [r"\bAustralis\b", r"\bAUSS\b"],
    "BAKKA": [r"\bBakkafrost\b", r"\bBAKKA\b"],
    "CERMAQ": [r"\bCermaq\b", r"\bcermaq\b"],
}

PA_PATTERNS = {
    i: [rf"\bPA\s*{i}\b", rf"\bproduksjonsområde\s*{i}\b", rf"\bproduction area\s*{i}\b"]
    for i in range(1, 14)
}

# Keyword-based sentiment indicators
BEARISH_KEYWORDS = [
    r"\bISA\b", r"\binfectious salmon an[ae]mia\b", r"\bPD\b", r"\bpancreas disease\b",
    r"\bmortality\b", r"\bdødelighet\b", r"\bdead\b", r"\bdøde\b",
    r"\boutbreak\b", r"\butbrudd\b", r"\balgal bloom\b", r"\balgeoppblomstring\b",
    r"\brecall\b", r"\btilbakekall\b", r"\bfine\b", r"\bbot\b",
    r"\bdowngrade\b", r"\bnedgradert\b", r"\bban\b", r"\bforbud\b",
    r"\bred zone\b", r"\brødt lys\b", r"\brødt\b.*trafikklys\b",
    r"\breduced\b.*\bgrowth\b", r"\blice.*above.*threshold\b",
    r"\btreatment.*fail\b", r"\bresistance\b", r"\bresistens\b",
    r"\brømming\b", r"\bescape\b", r"\bjellyfish\b", r"\bmanet\b",
]

BULLISH_KEYWORDS = [
    r"\brecord.*price\b", r"\brekord.*pris\b",
    r"\bstrong demand\b", r"\bsterk etterspørsel\b",
    r"\bupgrade\b", r"\boppgradert\b",
    r"\bgreen zone\b", r"\bgrønt lys\b", r"\bgrønt\b.*trafikklys\b",
    r"\bgrowth.*permit\b", r"\bveksttillatelse\b",
    r"\bacquisition\b", r"\boppkjøp\b",
    r"\bdividend\b", r"\butbytte\b",
    r"\blow lice\b", r"\blave luse\b",
    r"\bnew technology\b", r"\bny teknologi\b",
    r"\binnovation\b", r"\binnovasjon\b",
    r"\bexpansion\b", r"\butvidelse\b",
]

HIGH_IMPACT_KEYWORDS = [
    r"\bISA\b", r"\boutbreak\b", r"\butbrudd\b", r"\bmortality\b",
    r"\btraffic light\b", r"\btrafikklys\b", r"\balgal bloom\b",
    r"\brecord price\b", r"\bacquisition\b", r"\bmerger\b",
    r"\bban\b", r"\bforbud\b", r"\bregulatory\b",
]

CATEGORY_KEYWORDS = {
    NewsCategory.DISEASE_OUTBREAK: [r"\bISA\b", r"\bPD\b", r"\boutbreak\b", r"\butbrudd\b", r"\bdisease\b", r"\bsykdom\b"],
    NewsCategory.LICE_REPORT: [r"\blice\b", r"\blus\b", r"\blouse\b", r"\bdelousing\b", r"\bavlusning\b"],
    NewsCategory.REGULATORY: [r"\btraffic light\b", r"\btrafikklys\b", r"\bregulat\b", r"\bforskrift\b", r"\blicen[sc]e\b"],
    NewsCategory.EARNINGS: [r"\bearnings\b", r"\bresultat\b", r"\bprofit\b", r"\brevenue\b", r"\bomsetning\b", r"\bEBITDA\b"],
    NewsCategory.MERGER_ACQUISITION: [r"\bacquisition\b", r"\bmerger\b", r"\boppkjøp\b", r"\bfusjon\b", r"\btakeover\b"],
    NewsCategory.TREATMENT: [r"\btreatment\b", r"\bbehandling\b", r"\bHydrolicer\b", r"\bThermolicer\b", r"\bmechanical\b"],
    NewsCategory.PRICE_MOVEMENT: [r"\bprice\b.*\b(rise|fall|drop|surge|record)\b", r"\bpris\b.*\b(stigning|fall|rekord)\b"],
    NewsCategory.SUPPLY_DEMAND: [r"\bsupply\b", r"\bdemand\b", r"\bharvest\b", r"\bslaughter\b", r"\bbiomass\b"],
    NewsCategory.CLIMATE: [r"\bclimate\b", r"\bklima\b", r"\btemperature\b", r"\bwarming\b", r"\bocean\b"],
}


class SentimentEngine:
    """
    Real-time NLP sentiment analysis on aquaculture news.

    Pipeline:
      1. Poll RSS feeds every 15 minutes
      2. Parse articles, deduplicate by URL hash
      3. Extract named entities (companies, PAs, treatments)
      4. Classify sentiment using keyword rules + optional LLM
      5. Aggregate into per-ticker sentiment signals
      6. Generate trading signals from sentiment shifts
    """

    def __init__(self) -> None:
        self._articles: dict[str, NewsArticle] = {}  # id → article
        self._signals: list[SentimentSignal] = []
        self._last_poll: Optional[dt.datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=20,
                headers={"User-Agent": "OpenClaw/1.0 (Aquaculture Research Bot)"},
                follow_redirects=True,
            )
        return self._client

    async def poll_feeds(self) -> list[NewsArticle]:
        """Fetch and parse all RSS feeds."""
        client = await self._ensure_client()
        new_articles: list[NewsArticle] = []

        tasks = [self._fetch_feed(client, feed) for feed in NEWS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                for article in result:
                    if article.id not in self._articles:
                        self._articles[article.id] = article
                        new_articles.append(article)

        # Prune old articles (keep 7 days)
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=7)
        self._articles = {
            k: v for k, v in self._articles.items()
            if v.fetched_at > cutoff
        }

        self._last_poll = dt.datetime.now(dt.UTC)

        if new_articles:
            # Analyze new articles
            for article in new_articles:
                self._analyze_article(article)

            # Regenerate signals
            self._generate_signals()

            log.info("sentiment.new_articles", n=len(new_articles))

        return new_articles

    async def _fetch_feed(
        self, client: httpx.AsyncClient, feed: dict
    ) -> list[NewsArticle]:
        """Fetch and parse a single RSS feed."""
        articles = []
        try:
            resp = await client.get(feed["url"])
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.text)

            # Handle both RSS 2.0 and Atom formats
            items = root.findall(".//item") or root.findall(
                ".//{http://www.w3.org/2005/Atom}entry"
            )

            for item in items[:20]:  # max 20 per feed
                title = (
                    self._get_text(item, "title")
                    or self._get_text(item, "{http://www.w3.org/2005/Atom}title")
                    or ""
                )
                link = (
                    self._get_text(item, "link")
                    or self._get_attr(item, "{http://www.w3.org/2005/Atom}link", "href")
                    or ""
                )
                summary = (
                    self._get_text(item, "description")
                    or self._get_text(item, "{http://www.w3.org/2005/Atom}summary")
                    or ""
                )
                pub_date = (
                    self._get_text(item, "pubDate")
                    or self._get_text(item, "{http://www.w3.org/2005/Atom}published")
                )

                if not title or not link:
                    continue

                # Clean HTML from summary
                summary = re.sub(r"<[^>]+>", "", summary)[:500]

                article_id = hashlib.md5(link.encode()).hexdigest()

                published = None
                if pub_date:
                    try:
                        # Try common date formats
                        for fmt in [
                            "%a, %d %b %Y %H:%M:%S %z",
                            "%a, %d %b %Y %H:%M:%S GMT",
                            "%Y-%m-%dT%H:%M:%S%z",
                            "%Y-%m-%dT%H:%M:%SZ",
                        ]:
                            try:
                                published = dt.datetime.strptime(pub_date.strip(), fmt)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass

                articles.append(NewsArticle(
                    id=article_id,
                    title=title,
                    summary=summary,
                    url=link,
                    source=feed["name"],
                    published_at=published,
                ))

        except Exception as e:
            log.debug("sentiment.feed_error", feed=feed["name"], error=str(e)[:80])

        return articles

    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        el = element.find(tag)
        return el.text if el is not None and el.text else None

    def _get_attr(self, element: ET.Element, tag: str, attr: str) -> Optional[str]:
        el = element.find(tag)
        return el.get(attr) if el is not None else None

    def _analyze_article(self, article: NewsArticle) -> None:
        """Run NLP analysis on a single article."""
        text = f"{article.title} {article.summary}".lower()
        text_original = f"{article.title} {article.summary}"

        # 1. Extract companies
        for ticker, patterns in COMPANY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_original, re.IGNORECASE):
                    if ticker not in article.companies_mentioned:
                        article.companies_mentioned.append(ticker)
                    if ticker not in article.tickers_affected:
                        article.tickers_affected.append(ticker)
                    break

        # If no specific company mentioned, all major tickers affected
        if not article.tickers_affected:
            # Check if it's a sector-wide article
            sector_words = [
                "salmon", "laks", "aquaculture", "oppdrett",
                "seafood", "sjømat", "fish farm", "fiskeoppdrett",
            ]
            if any(w in text for w in sector_words):
                article.tickers_affected = ["MOWI", "SALM", "LSG"]

        # 2. Extract production areas
        for pa, patterns in PA_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_original, re.IGNORECASE):
                    if pa not in article.production_areas:
                        article.production_areas.append(pa)

        # 3. Classify category
        best_category = NewsCategory.GENERAL
        best_count = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            count = sum(1 for kw in keywords if re.search(kw, text, re.IGNORECASE))
            if count > best_count:
                best_count = count
                best_category = category
        article.category = best_category

        # 4. Sentiment scoring
        bearish_count = sum(
            1 for kw in BEARISH_KEYWORDS if re.search(kw, text, re.IGNORECASE)
        )
        bullish_count = sum(
            1 for kw in BULLISH_KEYWORDS if re.search(kw, text, re.IGNORECASE)
        )

        # Weighted score
        raw_score = (bullish_count - bearish_count) / max(bullish_count + bearish_count, 1)
        article.sentiment_score = max(-1.0, min(1.0, raw_score))

        if article.sentiment_score < -0.5:
            article.sentiment = Sentiment.VERY_BEARISH
        elif article.sentiment_score < -0.15:
            article.sentiment = Sentiment.BEARISH
        elif article.sentiment_score > 0.5:
            article.sentiment = Sentiment.VERY_BULLISH
        elif article.sentiment_score > 0.15:
            article.sentiment = Sentiment.BULLISH
        else:
            article.sentiment = Sentiment.NEUTRAL

        # 5. Market impact score
        impact = 0.0
        high_impact_count = sum(
            1 for kw in HIGH_IMPACT_KEYWORDS if re.search(kw, text, re.IGNORECASE)
        )
        impact += min(0.5, high_impact_count * 0.15)

        # Disease outbreaks have highest impact
        if article.category == NewsCategory.DISEASE_OUTBREAK:
            impact += 0.3
        elif article.category in (NewsCategory.REGULATORY, NewsCategory.MERGER_ACQUISITION):
            impact += 0.2
        elif article.category in (NewsCategory.EARNINGS, NewsCategory.PRICE_MOVEMENT):
            impact += 0.15

        # Specific company mention = more actionable
        if article.companies_mentioned:
            impact += 0.1

        article.market_impact_score = min(1.0, impact)
        article.confidence = min(1.0, 0.3 + bearish_count * 0.1 + bullish_count * 0.1 + high_impact_count * 0.1)

        # 6. Keywords
        article.keywords = []
        all_kw_patterns = BEARISH_KEYWORDS + BULLISH_KEYWORDS
        for kw in all_kw_patterns:
            matches = re.findall(kw, text, re.IGNORECASE)
            article.keywords.extend(matches)
        article.keywords = list(set(article.keywords))[:10]

    def _generate_signals(self) -> None:
        """Generate aggregated sentiment signals per ticker."""
        now = dt.datetime.now(dt.UTC)
        window = now - dt.timedelta(hours=24)

        recent = [
            a for a in self._articles.values()
            if a.fetched_at > window and a.tickers_affected
        ]

        if not recent:
            return

        # Aggregate by ticker
        ticker_articles: dict[str, list[NewsArticle]] = {}
        for article in recent:
            for ticker in article.tickers_affected:
                ticker_articles.setdefault(ticker, []).append(article)

        self._signals = []
        for ticker, articles in ticker_articles.items():
            if not articles:
                continue

            # Weighted average sentiment (higher impact articles count more)
            total_weight = sum(max(0.1, a.market_impact_score) for a in articles)
            weighted_score = sum(
                a.sentiment_score * max(0.1, a.market_impact_score)
                for a in articles
            ) / total_weight if total_weight > 0 else 0

            # Dominant category
            cat_counts: dict[NewsCategory, int] = {}
            for a in articles:
                cat_counts[a.category] = cat_counts.get(a.category, 0) + 1
            dominant_cat = max(cat_counts, key=cat_counts.get) if cat_counts else NewsCategory.GENERAL

            # Classify
            if weighted_score < -0.5:
                sentiment = Sentiment.VERY_BEARISH
            elif weighted_score < -0.15:
                sentiment = Sentiment.BEARISH
            elif weighted_score > 0.5:
                sentiment = Sentiment.VERY_BULLISH
            elif weighted_score > 0.15:
                sentiment = Sentiment.BULLISH
            else:
                sentiment = Sentiment.NEUTRAL

            # Signal strength
            strength = min(1.0, abs(weighted_score) * len(articles) * 0.15)

            # Top headlines
            sorted_articles = sorted(articles, key=lambda a: a.market_impact_score, reverse=True)
            top_headlines = [a.title for a in sorted_articles[:3]]

            # Rationale
            parts = []
            if dominant_cat != NewsCategory.GENERAL:
                parts.append(f"Dominant theme: {dominant_cat.value.replace('_', ' ')}")
            parts.append(f"{len(articles)} articles in 24h")
            if any(a.sentiment == Sentiment.VERY_BEARISH for a in articles):
                parts.append("Strongly negative coverage detected")
            if any(a.sentiment == Sentiment.VERY_BULLISH for a in articles):
                parts.append("Strongly positive coverage detected")

            self._signals.append(SentimentSignal(
                generated_at=now,
                ticker=ticker,
                sentiment=sentiment,
                score=round(weighted_score, 3),
                n_articles=len(articles),
                dominant_category=dominant_cat,
                top_headlines=top_headlines,
                signal_strength=round(strength, 3),
                rationale=". ".join(parts),
            ))

    async def analyze_with_llm(self, article: NewsArticle) -> Optional[dict]:
        """
        Use LLM for deep sentiment analysis on high-impact articles.
        Called for articles with market_impact_score > 0.5.
        """
        if article.market_impact_score < 0.5:
            return None

        try:
            from core.llm.client import get_llm_client

            client = get_llm_client()
            prompt = f"""Analyze this aquaculture news article for trading signals:

Title: {article.title}
Source: {article.source}
Summary: {article.summary[:300]}

Provide:
1. Sentiment (-1 to +1 scale, where -1 = very bearish for salmon stocks, +1 = very bullish)
2. Affected tickers (MOWI, SALM, LSG, GSF)
3. Time horizon (immediate/short/medium/long)
4. Confidence (0-1)
5. One-sentence trading implication

Reply in JSON format only."""

            response = await client.complete(prompt, max_tokens=300)
            # Parse LLM response
            import json
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                return None

        except Exception as e:
            log.debug("sentiment.llm_error", error=str(e)[:80])
            return None

    # ── Public API ───────────────────────────────────────────────

    def get_signals(self) -> list[dict]:
        """Get current sentiment signals per ticker."""
        return [
            {
                "generated_at": s.generated_at.isoformat(),
                "ticker": s.ticker,
                "sentiment": s.sentiment.value,
                "score": s.score,
                "n_articles": s.n_articles,
                "dominant_category": s.dominant_category.value,
                "top_headlines": s.top_headlines,
                "signal_strength": s.signal_strength,
                "rationale": s.rationale,
            }
            for s in self._signals
        ]

    def get_recent_articles(
        self, hours: int = 24, ticker: Optional[str] = None
    ) -> list[dict]:
        """Get recent analyzed articles."""
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
        articles = [
            a for a in self._articles.values()
            if a.fetched_at > cutoff
        ]

        if ticker:
            articles = [a for a in articles if ticker in a.tickers_affected]

        # Sort by market impact
        articles.sort(key=lambda a: a.market_impact_score, reverse=True)

        return [
            {
                "id": a.id,
                "title": a.title,
                "summary": a.summary[:200],
                "url": a.url,
                "source": a.source,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "sentiment": a.sentiment.value,
                "sentiment_score": a.sentiment_score,
                "category": a.category.value,
                "companies": a.companies_mentioned,
                "tickers": a.tickers_affected,
                "production_areas": a.production_areas,
                "market_impact": a.market_impact_score,
                "keywords": a.keywords,
            }
            for a in articles[:50]
        ]

    def get_sentiment_summary(self) -> dict:
        """Get overall market sentiment summary."""
        now = dt.datetime.now(dt.UTC)
        h24 = now - dt.timedelta(hours=24)
        h6 = now - dt.timedelta(hours=6)

        recent_24h = [a for a in self._articles.values() if a.fetched_at > h24]
        recent_6h = [a for a in self._articles.values() if a.fetched_at > h6]

        def avg_sentiment(articles: list[NewsArticle]) -> float:
            if not articles:
                return 0.0
            return sum(a.sentiment_score for a in articles) / len(articles)

        # Category breakdown
        categories: dict[str, int] = {}
        for a in recent_24h:
            cat = a.category.value
            categories[cat] = categories.get(cat, 0) + 1

        # Source breakdown
        sources: dict[str, int] = {}
        for a in recent_24h:
            sources[a.source] = sources.get(a.source, 0) + 1

        return {
            "generated_at": now.isoformat(),
            "articles_24h": len(recent_24h),
            "articles_6h": len(recent_6h),
            "avg_sentiment_24h": round(avg_sentiment(recent_24h), 3),
            "avg_sentiment_6h": round(avg_sentiment(recent_6h), 3),
            "sentiment_trend": "improving" if avg_sentiment(recent_6h) > avg_sentiment(recent_24h) else "deteriorating" if avg_sentiment(recent_6h) < avg_sentiment(recent_24h) else "stable",
            "categories": categories,
            "sources": sources,
            "signals": self.get_signals(),
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "high_impact_articles": len([
                a for a in recent_24h if a.market_impact_score > 0.5
            ]),
        }

    async def shutdown(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton
sentiment_engine = SentimentEngine()
