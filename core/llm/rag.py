"""
RAG Knowledge Layer
====================
Retrieval-augmented generation over:
  1. Internal time-series database (lice records, forecasts)
  2. Domain knowledge (Stige et al., regulatory framework)
  3. User-uploaded documents

Uses simple TF-IDF retrieval (no vector DB dependency) with
LLM for synthesis.
"""
from __future__ import annotations


from sqlalchemy import select

from core.llm.client import llm_client
from core.llm.prompts import SYSTEM_AQUACULTURE_EXPERT, RAG_CONTEXT_PROMPT
from core.models import LiceRecord
from core.async_db import get_async_session

import structlog

log = structlog.get_logger(__name__)

# ── Built-in knowledge base ─────────────────────────────────────────
DOMAIN_KNOWLEDGE = [
    {
        "id": "stige_model",
        "title": "Stige et al. (2025) Salmon Lice Prediction Model",
        "content": (
            "The Stige et al. (2025) model jointly predicts three parasitic "
            "lice stage groups (sessile, other motiles, adult females) using "
            "a generalized linear mixed model. Key inputs include current "
            "stage-specific counts, infestation pressure index derived from "
            "adult-female biomass weighted by temperature, fish weight, and "
            "cleaner-fish presence. The model accounts for the biological "
            "development pathway: sessile → mobile → adult female, with "
            "temperature-dependent transition rates following Bělehrádek "
            "functions. Degree-days above 3°C drive development. The model "
            "showed superior short-term (1-2 week) predictive performance "
            "compared to persistence or trend-based forecasts."
        ),
    },
    {
        "id": "regulatory_framework",
        "title": "Norwegian Salmon Lice Regulations",
        "content": (
            "The Norwegian regulatory limit for adult female salmon lice is "
            "0.5 per fish (weekly average). Sites exceeding this must "
            "implement treatment within 2 weeks. The traffic-light system "
            "classifies production areas (PA 1-13) as green, yellow, or red "
            "based on modeled lice-induced wild salmon mortality. Red areas "
            "face a mandatory 6% production capacity reduction. The system "
            "is evaluated annually by an expert group. The minimum reporting "
            "threshold is 0.2 adult female lice. Treatments include: "
            "mechanical (Hydrolicer, Optilicer: 80-95% efficacy, 0.5-2% mortality), "
            "thermal (Thermolicer: 90-97% efficacy, 1-3% mortality), "
            "medicinal bath (azamethiphos: 70-90% efficacy), "
            "medicinal in-feed (emamectin benzoate: 80-95% efficacy, "
            "6-week pre-harvest withdrawal)."
        ),
    },
    {
        "id": "production_areas",
        "title": "Norwegian Salmon Production Areas",
        "content": (
            "Norway's 13 production areas (PAs) span the coast from Rogaland "
            "(PA 1-2) to Finnmark (PA 12-13). PA 3-6 (Hordaland to Møre og "
            "Romsdal) produce approximately 55% of total volume (~1.7M tonnes "
            "HOG annually). Lice pressure peaks in May-September due to warmer "
            "water accelerating larval development. Northern PAs (10-13) "
            "generally have lower lice pressure due to colder temperatures. "
            "Key companies: Mowi ASA (MOWI, ~460kt), SalMar ASA (SALM, ~185kt), "
            "Lerøy Seafood Group ASA (LSG, ~210kt), Grieg Seafood ASA (GSF, ~85kt)."
        ),
    },
    {
        "id": "lice_biology",
        "title": "Salmon Lice Biology",
        "content": (
            "Lepeophtheirus salmonis has 8 developmental stages: 2 naupliar "
            "(free-swimming), 1 copepodid (infectious free-swimming), 4 chalimus "
            "(attached/sessile), and 2 pre-adult + adult (mobile). Development "
            "from egg to adult takes 40-50 days at 10°C. Adult females produce "
            "~30 eggs per degree-day above 3°C. Copepodids are viable for ~150 "
            "degree-days. Infestation pressure depends on local lice density, "
            "sea temperature, and current-driven dispersal (effective up to 30 km). "
            "Lice cause skin damage, stress, reduced growth (up to 10% per 0.1 "
            "lice above 0.2 threshold), and increased mortality at high levels."
        ),
    },
]


class RAGKnowledgeLayer:
    """Simple retrieval-augmented generation without vector DB."""

    def __init__(self) -> None:
        self.knowledge_base = list(DOMAIN_KNOWLEDGE)
        self.user_documents: list[dict] = []

    def add_document(self, title: str, content: str) -> None:
        """Add a user-uploaded document to the knowledge base."""
        self.user_documents.append({
            "id": f"user_{len(self.user_documents)}",
            "title": title,
            "content": content,
        })

    async def query(self, question: str, include_db: bool = True) -> str:
        """Answer a question using RAG over knowledge base + database."""
        # Retrieve relevant knowledge
        context_parts = []

        # 1. Search domain knowledge
        all_docs = self.knowledge_base + self.user_documents
        relevant = self._retrieve(question, all_docs, top_k=3)
        for doc in relevant:
            context_parts.append(f"[{doc['title']}]\n{doc['content']}")

        # 2. Pull relevant DB data
        if include_db:
            db_context = await self._get_db_context(question)
            if db_context:
                context_parts.append(f"[Live Database]\n{db_context}")

        context = "\n\n---\n\n".join(context_parts)

        prompt = RAG_CONTEXT_PROMPT.format(
            context=context,
            question=question,
        )

        resp = await llm_client.complete(
            prompt=prompt,
            system=SYSTEM_AQUACULTURE_EXPERT,
            max_tokens=1500,
        )

        return resp.content

    @staticmethod
    def _retrieve(query: str, documents: list[dict], top_k: int = 3) -> list[dict]:
        """Simple keyword-based retrieval (TF-IDF-like scoring)."""
        query_terms = set(query.lower().split())

        scored = []
        for doc in documents:
            text = (doc["title"] + " " + doc["content"]).lower()
            # Count matching query terms
            score = sum(1 for term in query_terms if term in text)
            # Bonus for exact phrase matches
            if query.lower() in text:
                score += 5
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored[:top_k] if score > 0]

    @staticmethod
    async def _get_db_context(question: str) -> str:
        """Pull relevant database records for the question."""
        parts = []
        q_lower = question.lower()

        async with get_async_session() as s:
            from sqlalchemy import func

            result = await s.execute(
                select(LiceRecord.year, LiceRecord.week)
                .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
                .limit(1)
            )
            latest = result.first()

            if not latest:
                return ""

            year, week = latest

            # Always include national summary
            result = await s.execute(
                select(
                    func.avg(LiceRecord.avg_adult_female_lice),
                    func.max(LiceRecord.avg_adult_female_lice),
                    func.count(LiceRecord.id),
                    func.avg(LiceRecord.sea_temp_c),
                ).where(
                    LiceRecord.year == year,
                    LiceRecord.week == week,
                    LiceRecord.avg_adult_female_lice.isnot(None),
                )
            )
            stats = result.one()

            parts.append(
                f"Week {year}-W{week:02d}: {stats[2]} active sites, "
                f"avg lice={stats[0]:.3f}, max={stats[1]:.3f}, avg temp={stats[3]:.1f}°C"
            )

            # Top lice sites
            if any(w in q_lower for w in ["worst", "highest", "critical", "top", "hot"]):
                result = await s.execute(
                    select(LiceRecord.locality_no, LiceRecord.avg_adult_female_lice)
                    .where(
                        LiceRecord.year == year,
                        LiceRecord.week == week,
                        LiceRecord.avg_adult_female_lice.isnot(None),
                    )
                    .order_by(LiceRecord.avg_adult_female_lice.desc())
                    .limit(10)
                )
                worst = result.all()
                parts.append("Top lice sites: " + ", ".join(
                    f"loc {r[0]}={r[1]:.3f}" for r in worst
                ))

        return "\n".join(parts)


rag_layer = RAGKnowledgeLayer()
