"""Orchestrates one Idea Testing assessment end to end (spec §4): evidence
retrieval, scoring, confidence, persistence, caching, and (for multiple
concepts) comparison. This is the only module the API router calls into.
"""
import uuid
from datetime import date

from services.trends_real_estate_service.app.assistant import tools as assistant_tools
from services.trends_real_estate_service.app.idea_testing import confidence, store
from services.trends_real_estate_service.app.idea_testing.evidence import gather_evidence
from services.trends_real_estate_service.app.idea_testing.schema import (
    FACTOR_IDS,
    FRAMEWORK_VERSION,
    ConceptExtraction,
)
from services.trends_real_estate_service.app.idea_testing.scoring import score_concept
from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.knowledge import store as knowledge_store
from services.trends_real_estate_service.app.services import trend_service

MAX_COMPARE_CONCEPTS = 3

_RESPONSE_FIELDS = (
    "assessment_id", "concept_id", "title", "test_type", "headline", "summary", "factor_scores",
    "overall_score", "confidence_score", "confidence_breakdown", "recommendations",
    "trends_run_id", "country", "model", "framework_version", "created_at",
)


class ConceptNotFoundError(Exception):
    """Raised by assess_concept when concept_id names no idea_concepts row."""


class ComparisonNotFoundError(Exception):
    """Raised by get_comparison_by_id when comparison_id names no idea_comparisons row."""


def _with_evidence_links(factor_scores: list[dict] | None) -> list[dict] | None:
    if not factor_scores:
        return factor_scores
    post_keys = {(c["platform"], c["post_id"])
                for f in factor_scores for c in f.get("citations") or []
                if c.get("evidence_type") == "post" and c.get("platform") and c.get("post_id")}
    urls = store.post_urls(post_keys) if post_keys else {}

    document_ids = {c["document_id"]
                    for f in factor_scores for c in f.get("citations") or []
                    if c.get("evidence_type") == "document" and c.get("document_id")}
    documents = knowledge_store.document_status(document_ids) if document_ids else {}

    shaped = []
    for f in factor_scores:
        citations = []
        for c in f.get("citations") or []:
            url = urls.get((c.get("platform"), c.get("post_id")))
            safe = url if isinstance(url, str) and url.startswith(("https://", "http://")) else None
            enriched = {**c, "post_url": safe}
            if c.get("evidence_type") == "document":
                doc = documents.get(c.get("document_id"))
                enriched["document_title"] = doc["title"] if doc else None
                enriched["document_deleted"] = bool(doc and doc["deleted_at"] is not None)
            citations.append(enriched)
        shaped.append({**f, "citations": citations})
    return shaped


def shape_assessment(row: dict, cached: bool) -> dict:
    """The one client-facing shape for an assessment, used for cache hits,
    cache misses, and GET /assessments/{id}."""
    shaped = {key: row.get(key) for key in _RESPONSE_FIELDS}
    shaped["factor_scores"] = _with_evidence_links(row.get("factor_scores"))
    shaped["cached"] = cached
    score = row.get("confidence_score") or 0
    shaped["confidence_label"] = confidence.confidence_label(score)
    shaped["confidence_explanation"] = confidence.explain_confidence(
        score, row.get("confidence_breakdown") or {})
    return shaped


def _confidence_inputs(evidence_by_factor: dict) -> dict:
    """Flatten every factor's evidence into the raw numbers confidence.py's
    component functions need, deduplicating posts by (platform, post_id)
    across all factor bundles first."""
    posts_by_id: dict[tuple, dict] = {}
    trend_distances: list[float | None] = []
    for bundle in evidence_by_factor.values():
        posts = bundle.get("posts") or {}
        for item in posts.get("data") or []:
            key = (item.get("platform"), item.get("post_id"))
            posts_by_id.setdefault(key, item)
        trends = bundle.get("trends")
        if trends and trends.get("ok"):
            for item in trends.get("data") or []:
                trend_distances.append(item.get("distance"))

    distances = [item.get("distance") for item in posts_by_id.values()] + trend_distances
    sources = {item["source"] for item in posts_by_id.values() if item.get("source")}
    authors = {item["author_username"] for item in posts_by_id.values()
              if item.get("author_username")}
    post_dates = [item.get("posted_at") for item in posts_by_id.values()]
    total_posts = len(posts_by_id)
    return {"distances": distances, "sources": sources, "authors": authors,
            "post_dates": post_dates, "total_posts": total_posts}


def _compute_confidence(evidence_by_factor: dict, as_of: date | None) -> dict:
    inputs = _confidence_inputs(evidence_by_factor)
    total = inputs["total_posts"]
    components = {
        "relevance": confidence.relevance_score(inputs["distances"]),
        "volume": confidence.volume_score(total),
        "spread": confidence.spread_score(inputs["sources"]),
        "recency": confidence.recency_score(
            confidence.count_recent(inputs["post_dates"], as_of), total),
        "quality": confidence.quality_score(len(inputs["authors"]), total),
    }
    return {"score": confidence.combine(components), "components": components}


def assess_concept(concept_id: str, test_type: str, trends_run_id: str | None,
                   country: str | None, embed_query,
                   dispatch=assistant_tools.dispatch) -> dict:
    settings = get_settings()
    concept_row = store.get_concept(concept_id)
    if concept_row is None:
        raise ConceptNotFoundError(f"No concept with id {concept_id!r}.")
    extracted = concept_row["extracted"]

    cache_run_id = trends_run_id if trends_run_id is not None else trend_service.latest_run_id(None)
    cache_key = store.build_cache_key(extracted, cache_run_id, country, settings.OPENAI_MODEL,
                                      FRAMEWORK_VERSION)
    cached = store.get_cached_assessment(cache_key)
    if cached is not None:
        return shape_assessment(cached, cached=True)

    concept = ConceptExtraction(**extracted)
    countries = [country] if country else None
    evidence_by_factor = gather_evidence(concept, embed_query, dispatch=dispatch,
                                         countries=countries)
    scoring_result = score_concept(concept, evidence_by_factor)

    factor_scores = [f.model_dump() for f in scoring_result.factors]
    overall = confidence.overall_score([f["score"] for f in factor_scores])
    conf = _compute_confidence(evidence_by_factor, store.data_as_of(cache_run_id))

    assessment_id = uuid.uuid4().hex
    store.save_assessment(
        assessment_id=assessment_id, concept_id=concept_id, test_type=test_type,
        headline=scoring_result.headline, summary=scoring_result.summary,
        factor_scores=factor_scores, overall_score=overall,
        confidence_score=conf["score"], confidence_breakdown=conf["components"],
        recommendations=scoring_result.recommendations, trends_run_id=trends_run_id,
        country=country, model=settings.OPENAI_MODEL, framework_version=FRAMEWORK_VERSION,
        cache_key=cache_key)

    row = store.get_cached_assessment(cache_key)
    return shape_assessment(row, cached=False)


def _build_comparison(comparison_id: str, assessments: list[dict]) -> dict:
    winner = max(assessments, key=lambda a: a["overall_score"])
    factor_leaders = []
    for factor_id in FACTOR_IDS:
        best = max(
            assessments,
            key=lambda a: next(
                (f["score"] for f in a["factor_scores"] if f["factor_id"] == factor_id), -1))
        factor_leaders.append({"factor_id": factor_id, "assessment_id": best["assessment_id"]})
    verdict = f"{winner['title']} scores highest overall ({winner['overall_score']}/100)."
    narrative = " ".join(
        f"{a['title']} scored {a['overall_score']}/100." for a in assessments)
    return {"comparison_id": comparison_id, "winner_assessment_id": winner["assessment_id"],
            "factor_leaders": factor_leaders, "verdict": verdict, "narrative": narrative}


def assess_and_compare(concept_ids: list[str], test_type: str, trends_run_id: str | None,
                       country: str | None, embed_query,
                       dispatch=assistant_tools.dispatch) -> dict:
    if len(concept_ids) > MAX_COMPARE_CONCEPTS:
        raise ValueError(f"Cannot compare more than {MAX_COMPARE_CONCEPTS} concepts "
                         f"(got {len(concept_ids)}).")

    assessments = [assess_concept(cid, test_type, trends_run_id, country, embed_query, dispatch)
                  for cid in concept_ids]

    comparison = None
    if len(assessments) > 1:
        comparison = _build_comparison(uuid.uuid4().hex, assessments)
        store.save_comparison(
            comparison_id=comparison["comparison_id"],
            assessment_ids=[a["assessment_id"] for a in assessments],
            winner_assessment_id=comparison["winner_assessment_id"],
            factor_leaders=comparison["factor_leaders"], verdict=comparison["verdict"],
            narrative=comparison["narrative"])

    return {"assessments": assessments, "comparison": comparison}


def list_history(username: str) -> list[dict]:
    """Recent assessments and comparisons owned by username, newest first,
    shaped for the history list (spec follow-up: refresh-safe deep links
    made a history view viable)."""
    rows = store.list_history(username)
    items = []
    for row in rows:
        if row["kind"] == "assessment":
            items.append({
                "kind": "assessment",
                "assessment_id": row["assessment_id"],
                "title": row["title"],
                "test_type": row["test_type"],
                "overall_score": row["overall_score"],
                "created_at": row["created_at"],
            })
        else:
            items.append({
                "kind": "comparison",
                "comparison_id": row["comparison_id"],
                "titles": row["titles"],
                "scores": row["scores"],
                "verdict": row["verdict"],
                "created_at": row["created_at"],
            })
    return items


def get_comparison_by_id(comparison_id: str) -> dict:
    """Re-fetch a stored comparison and its assessments, in their original
    submission order, for the GET /comparisons/{id} endpoint (refresh-safe
    deep links)."""
    row = store.get_comparison(comparison_id)
    if row is None:
        raise ComparisonNotFoundError(f"No comparison with id {comparison_id!r}.")

    assessments = []
    for assessment_id in row["assessment_ids"]:
        assessment_row = store.get_assessment(assessment_id)
        if assessment_row is None:
            raise ComparisonNotFoundError(
                f"Comparison {comparison_id!r} references missing assessment {assessment_id!r}.")
        assessments.append(shape_assessment(assessment_row, cached=True))

    comparison = {
        "comparison_id": row["comparison_id"], "winner_assessment_id": row["winner_assessment_id"],
        "factor_leaders": row["factor_leaders"], "verdict": row["verdict"],
        "narrative": row["narrative"],
    }
    return {"assessments": assessments, "comparison": comparison}
