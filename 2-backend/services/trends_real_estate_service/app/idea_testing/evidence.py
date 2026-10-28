"""Deterministic, per-6C-factor evidence retrieval (spec §4), mapping the
brief's evidence-emphasis table onto assistant.tools.dispatch calls. Fixed
queries per factor, run in a fixed order -- never an agentic tool loop --
so retrieval for the same concept is repeatable (brief §8).
"""
from collections.abc import Callable

from services.trends_real_estate_service.app.assistant import tools as assistant_tools
from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.idea_testing.schema import (
    FACTOR_IDS,  # noqa: F401
    ConceptExtraction,
)
from services.trends_real_estate_service.app.knowledge.store import (
    search_knowledge_chunks as _search_knowledge_chunks,
)
from services.trends_real_estate_service.app.trends.store import model_tag

Dispatch = Callable[[str, dict, Callable], dict]

_TRENDS_ENABLED_FACTORS = {"clutter", "competitive", "credibility"}


def _clutter_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.proposition} {c.category}", {"sources": ["brand", "influencer"]}


def _connect_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.need} {c.proposition}", {"sources": ["community"]}


def _clarity_query(c: ConceptExtraction) -> tuple[str, dict]:
    return c.proposition, {"sources": ["community"]}


def _competitive_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.proposition} {c.category}", {"sources": ["brand"]}


def _credibility_query(c: ConceptExtraction) -> tuple[str, dict]:
    return (" ".join(c.claims) or c.proposition), {}


def _conversion_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.need} {c.proposition}", {"sources": ["community"]}


_FACTOR_QUERIES: dict[str, Callable[[ConceptExtraction], tuple[str, dict]]] = {
    "clutter": _clutter_query,
    "connect": _connect_query,
    "clarity": _clarity_query,
    "competitive": _competitive_query,
    "credibility": _credibility_query,
    "conversion": _conversion_query,
}


def gather_evidence(
    concept: ConceptExtraction,
    embed_query,
    dispatch: Dispatch = assistant_tools.dispatch,
    countries: list[str] | None = None,
) -> dict[str, dict]:
    settings = get_settings()
    model = model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)

    result: dict[str, dict] = {}
    for factor_id, build_query in _FACTOR_QUERIES.items():
        query, source_args = build_query(concept)
        post_args: dict = {"query": query, "limit": 8, **source_args}
        if countries:
            post_args["countries"] = countries
        posts = dispatch("search_posts", post_args, embed_query)

        trends = None
        if factor_id in _TRENDS_ENABLED_FACTORS:
            trend_args: dict = {"query": query, "limit": 5}
            if countries:
                trend_args["countries"] = countries
            trends = dispatch("search_trends", trend_args, embed_query)

        vector = embed_query(query)
        # Every factor keeps whatever it retrieved. Filtering out chunks an earlier
        # factor already took starves the rest whenever the library is small, and the
        # factors that most need market data sort last. Repetition is handled where it
        # actually costs something, in the prompt rendering.
        document_chunks = _search_knowledge_chunks(vector, model, limit=3)
        documents = {"ok": bool(document_chunks), "data": document_chunks, "count": len(document_chunks)}

        result[factor_id] = {"posts": posts, "trends": trends, "documents": documents}
    return result
