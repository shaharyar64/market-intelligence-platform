"""Postgres persistence for Idea Testing (spec §6). Uses the same pooled
get_conn() every other read/write in this service uses (app.trends.store),
imported by name so tests can monkeypatch it to a scratch connection.
"""
import hashlib
import json
from datetime import date

from services.trends_real_estate_service.app.trends.store import get_conn


def build_cache_key(extracted: dict, trends_run_id: str | None, country: str | None,
                    model: str, framework_version: str) -> str:
    """A concept's extracted fields + the market/dataset/model/framework
    version it was scored against, hashed. Spec §6/§8: an unchanged concept
    against an unchanged dataset/model/framework returns the cached result.
    """
    payload = json.dumps(
        {"extracted": extracted, "run_id": trends_run_id, "country": country, "model": model,
         "framework_version": framework_version},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_concept(concept_id: str, created_by: str, title: str, input_format: str,
                 raw_text: str | None, file_s3_key: str | None, extracted: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO realestate_intel.idea_concepts
               (concept_id, created_by, title, input_format, raw_text, file_s3_key, extracted)
               VALUES (%(concept_id)s, %(created_by)s, %(title)s, %(input_format)s,
                       %(raw_text)s, %(file_s3_key)s, %(extracted)s::jsonb)""",
            {"concept_id": concept_id, "created_by": created_by, "title": title,
             "input_format": input_format, "raw_text": raw_text, "file_s3_key": file_s3_key,
             "extracted": json.dumps(extracted)})


def _row(cur) -> dict | None:
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row, strict=True))


def get_concept(concept_id: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM realestate_intel.idea_concepts WHERE concept_id = %(id)s",
            {"id": concept_id})
        return _row(cur)


def save_assessment(assessment_id: str, concept_id: str, test_type: str, headline: str,
                    summary: str, factor_scores: list[dict], overall_score: int,
                    confidence_score: int, confidence_breakdown: dict, recommendations: list,
                    trends_run_id: str | None, country: str | None, model: str,
                    framework_version: str, cache_key: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO realestate_intel.idea_assessments
               (assessment_id, concept_id, test_type, headline, summary, factor_scores,
                overall_score, confidence_score, confidence_breakdown, recommendations,
                trends_run_id, country, model, framework_version, cache_key)
               VALUES (%(assessment_id)s, %(concept_id)s, %(test_type)s, %(headline)s,
                       %(summary)s, %(factor_scores)s::jsonb, %(overall_score)s,
                       %(confidence_score)s, %(confidence_breakdown)s::jsonb,
                       %(recommendations)s::jsonb, %(trends_run_id)s, %(country)s, %(model)s,
                       %(framework_version)s, %(cache_key)s)
               ON CONFLICT (cache_key) DO NOTHING""",
            {"assessment_id": assessment_id, "concept_id": concept_id, "test_type": test_type,
             "headline": headline, "summary": summary,
             "factor_scores": json.dumps(factor_scores), "overall_score": overall_score,
             "confidence_score": confidence_score,
             "confidence_breakdown": json.dumps(confidence_breakdown),
             "recommendations": json.dumps(recommendations), "trends_run_id": trends_run_id,
             "country": country, "model": model, "framework_version": framework_version,
             "cache_key": cache_key})


_ASSESSMENT_WITH_TITLE = """
    SELECT a.*, c.title
    FROM realestate_intel.idea_assessments a
    JOIN realestate_intel.idea_concepts c ON c.concept_id = a.concept_id
    WHERE {where}
"""


def get_assessment(assessment_id: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            _ASSESSMENT_WITH_TITLE.format(where="a.assessment_id = %(id)s"),
            {"id": assessment_id})
        return _row(cur)


def get_cached_assessment(cache_key: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            _ASSESSMENT_WITH_TITLE.format(where="a.cache_key = %(key)s"),
            {"key": cache_key})
        return _row(cur)


def save_comparison(comparison_id: str, assessment_ids: list[str], winner_assessment_id: str,
                    factor_leaders: list[dict], verdict: str, narrative: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO realestate_intel.idea_comparisons
               (comparison_id, assessment_ids, winner_assessment_id, factor_leaders,
                verdict, narrative)
               VALUES (%(comparison_id)s, %(assessment_ids)s, %(winner_assessment_id)s,
                       %(factor_leaders)s::jsonb, %(verdict)s, %(narrative)s)""",
            {"comparison_id": comparison_id, "assessment_ids": assessment_ids,
             "winner_assessment_id": winner_assessment_id,
             "factor_leaders": json.dumps(factor_leaders), "verdict": verdict,
             "narrative": narrative})


def post_urls(keys: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
    if not keys:
        return {}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT platform, post_id, post_url FROM realestate_intel.trend_posts
               WHERE (platform, post_id) IN %(keys)s AND post_url IS NOT NULL""",
            {"keys": tuple(keys)})
        return {(platform, post_id): url for platform, post_id, url in cur.fetchall()}


def data_as_of(run_id: str | None) -> date | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT COALESCE(
                 (SELECT NULLIF(metrics->>'as_of', '')::date
                  FROM realestate_intel.trends
                  WHERE run_id = %(run_id)s AND metrics->>'as_of' IS NOT NULL
                  LIMIT 1),
                 (SELECT max(posted_at)::date FROM realestate_intel.trend_posts))""",
            {"run_id": run_id})
        row = cur.fetchone()
        return row[0] if row else None


def get_comparison(comparison_id: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM realestate_intel.idea_comparisons WHERE comparison_id = %(id)s",
            {"id": comparison_id})
        return _row(cur)


_HISTORY_ASSESSMENTS_SQL = """
    SELECT a.assessment_id, a.test_type, a.overall_score, a.created_at, c.title
    FROM realestate_intel.idea_assessments a
    JOIN realestate_intel.idea_concepts c ON c.concept_id = a.concept_id
    WHERE c.created_by = %(username)s
      AND NOT EXISTS (
        SELECT 1 FROM realestate_intel.idea_comparisons cmp
        WHERE a.assessment_id = ANY(cmp.assessment_ids)
      )
    ORDER BY a.created_at DESC
    LIMIT %(limit)s
"""

_HISTORY_COMPARISONS_SQL = """
    SELECT cmp.comparison_id, cmp.verdict, cmp.created_at,
           array_agg(c.title ORDER BY item.ord) AS titles,
           array_agg(a.overall_score ORDER BY item.ord) AS scores
    FROM realestate_intel.idea_comparisons cmp
    CROSS JOIN LATERAL unnest(cmp.assessment_ids) WITH ORDINALITY AS item(assessment_id, ord)
    JOIN realestate_intel.idea_assessments a ON a.assessment_id = item.assessment_id
    JOIN realestate_intel.idea_concepts c ON c.concept_id = a.concept_id
    GROUP BY cmp.comparison_id, cmp.verdict, cmp.created_at
    HAVING bool_and(c.created_by = %(username)s)
    ORDER BY cmp.created_at DESC
    LIMIT %(limit)s
"""


def list_history(username: str, limit: int = 50) -> list[dict]:
    """Every assessment and comparison owned by username, newest first.
    An assessment that belongs to a comparison is represented only once,
    as part of that comparison."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(_HISTORY_ASSESSMENTS_SQL, {"username": username, "limit": limit})
        cols = [d[0] for d in cur.description]
        assessments = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

        cur.execute(_HISTORY_COMPARISONS_SQL, {"username": username, "limit": limit})
        cols = [d[0] for d in cur.description]
        comparisons = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    items = (
        [{"kind": "assessment", **row} for row in assessments]
        + [{"kind": "comparison", **row} for row in comparisons]
    )
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:limit]
