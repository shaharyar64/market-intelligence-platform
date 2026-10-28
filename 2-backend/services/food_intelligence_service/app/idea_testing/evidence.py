"""Deterministic, per-6C-factor evidence retrieval (spec §4), mapping the
brief's evidence-emphasis table onto assistant.tools.dispatch calls. Fixed
queries per factor, run in a fixed order -- never an agentic tool loop --
so retrieval for the same concept is repeatable (brief §8).
"""
from collections.abc import Callable

from services.food_intelligence_service.app.assistant import tools as assistant_tools
from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.idea_testing.schema import (
    FACTOR_IDS,  # noqa: F401
    ConceptExtraction,
)
from services.food_intelligence_service.app.knowledge.store import (
    search_knowledge_chunks as _search_knowledge_chunks,
)
from services.food_intelligence_service.app.services import trend_service
from services.food_intelligence_service.app.trends.trend_posts_view import MEMBER_COUNTRY_JOIN
from services.food_intelligence_service.app.trends.store import get_conn, model_tag

Dispatch = Callable[[str, dict, Callable], dict]

_TRENDS_ENABLED_FACTORS = {"clutter", "competitive", "credibility"}

POSTS_PER_FACTOR = 8
TRENDS_PER_FACTOR = 5
DOCS_PER_FACTOR = 5
OWN_DOCS_PER_FACTOR = 3

_NEAREST_TRENDS_SQL = """
    WITH near AS (
        SELECT t.trend_id, t.name, t.quadrant, t.post_count, t.unique_authors,
               t.volume_index, t.growth_index, t.narrative->>'summary' AS summary,
               t.member_posts, (e.embedding <=> %(vec)s::vector) AS distance
        FROM food_intel.trends t
        JOIN food_intel.trend_embedding e
          ON e.run_id = t.run_id AND e.trend_id = t.trend_id AND e.model = %(tag)s
        WHERE t.run_id = %(run_id)s AND t.level = 'micro'
        ORDER BY distance
        LIMIT %(k)s
    )
    SELECT near.trend_id, near.name, near.quadrant, near.post_count, near.unique_authors,
           near.volume_index, near.growth_index, near.summary, near.distance{market_cols}
    FROM near{market_join}
    ORDER BY near.distance
"""

_MARKET_COLS = """,
           m.country_posts,
           round(100.0 * m.country_posts / NULLIF(m.attributed, 0), 1) AS country_share_pct,
           round(100.0 * m.attributed / NULLIF(m.members, 0), 1) AS country_coverage_pct"""

_MARKET_JOIN = f"""
    LEFT JOIN LATERAL (
        SELECT count(*) FILTER (WHERE mcc.member_country = ANY(%(countries)s)) AS country_posts,
               count(*) FILTER (WHERE mcc.member_country IS NOT NULL) AS attributed,
               count(*) AS members
        FROM jsonb_array_elements(near.member_posts) mp
        {MEMBER_COUNTRY_JOIN}
    ) m ON true"""


def nearest_trends(vector: list[float], limit: int,
                   countries: list[str] | None = None) -> list[dict]:
    settings = get_settings()
    run_id = trend_service.latest_run_id(None)
    if run_id is None:
        return []
    params = {"vec": "[" + ",".join(f"{v:.6f}" for v in vector) + "]",
              "tag": model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM),
              "run_id": run_id, "k": limit}
    if countries:
        params["countries"] = list(countries)
        sql = _NEAREST_TRENDS_SQL.format(market_cols=_MARKET_COLS, market_join=_MARKET_JOIN)
    else:
        sql = _NEAREST_TRENDS_SQL.format(market_cols="", market_join="")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '40s'")
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _envelope(rows: list[dict], what: str) -> dict:
    if not rows:
        return {"ok": False, "data": [], "count": 0, "message": f"No {what} found."}
    return {"ok": True, "data": rows, "count": len(rows), "message": ""}


def _specifics(c: ConceptExtraction) -> str:
    return " ".join(c.specifics)


def _with_specific_chunks(own: list[dict], specific: list[dict]) -> list[dict]:
    picked = own[:OWN_DOCS_PER_FACTOR]
    for chunk in specific + own[OWN_DOCS_PER_FACTOR:]:
        if len(picked) >= DOCS_PER_FACTOR:
            break
        if all(chunk["chunk_id"] != p["chunk_id"] for p in picked):
            picked.append(chunk)
    return picked


def _clutter_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.proposition} {c.category} {_specifics(c)}", {"sources": ["brand", "influencer"]}


def _connect_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.need} {c.proposition} {_specifics(c)}", {"sources": ["community"]}


def _clarity_query(c: ConceptExtraction) -> tuple[str, dict]:
    return c.proposition, {"sources": ["community"]}


def _competitive_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.proposition} {c.category} {_specifics(c)}", {"sources": ["brand"]}


def _credibility_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{' '.join(c.claims) or c.proposition} {_specifics(c)}", {}


def _conversion_query(c: ConceptExtraction) -> tuple[str, dict]:
    return f"{c.need} {c.proposition} {_specifics(c)}", {"sources": ["community"]}


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
    specific_chunks = []
    if concept.specifics:
        specific_chunks = _search_knowledge_chunks(
            embed_query(f"{concept.subject} {_specifics(concept)}"), model, limit=DOCS_PER_FACTOR)

    result: dict[str, dict] = {}
    for factor_id, build_query in _FACTOR_QUERIES.items():
        query, source_args = build_query(concept)
        post_args: dict = {"query": query, "limit": POSTS_PER_FACTOR, **source_args}
        if countries:
            post_args["countries"] = countries
        posts = dispatch("search_posts", post_args, embed_query)
        posts = {**posts, "requested": POSTS_PER_FACTOR}

        vector = embed_query(query)
        trends = None
        if factor_id in _TRENDS_ENABLED_FACTORS:
            trends = _envelope(nearest_trends(vector, TRENDS_PER_FACTOR, countries), "trends")

        # Every factor keeps whatever it retrieved. Filtering out chunks an earlier
        # factor already took starves the rest whenever the library is small, and the
        # factors that most need market data sort last. Repetition is handled where it
        # actually costs something, in the prompt rendering.
        document_chunks = _with_specific_chunks(
            _search_knowledge_chunks(vector, model, limit=DOCS_PER_FACTOR), specific_chunks)
        documents = {"ok": bool(document_chunks), "data": document_chunks, "count": len(document_chunks)}

        result[factor_id] = {"posts": posts, "trends": trends, "documents": documents,
                             "source_filter": source_args.get("sources")}
    return result
