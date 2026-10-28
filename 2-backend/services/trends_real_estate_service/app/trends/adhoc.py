"""Build one trend on demand, from a question instead of from clustering.

The batch pipeline discovers trends bottom-up: cluster the corpus, then name
whatever falls out. This does the opposite - the user names the thing first and
the corpus is searched for it. Both write the same row into realestate_intel.trends,
which is the whole design constraint here: the explorer, the detail view, the
date-range recompute and the assistant's own tools all read that table, and they
work on an ad-hoc trend without a single change only if its shape and its
arithmetic match a pipeline trend's exactly.

Three things that are easy to get wrong, and what is done about them:

Ranking. `volume_index` and `growth_index` are percentile ranks *within a run* -
`metrics.percentile_index` over a set of one returns 50.0, so a trend built
alone would always report itself as precisely average. Here the raw volume and
growth are ranked into the live run's existing distribution, so "84th
percentile" means the same thing on both kinds of trend.

Retrieval. A query is short English; the corpus is mostly long Arabic captions.
Nearest neighbours of the query text alone skew to whatever happens to be
phrased like the query. So the query's own hits are used to compute a centroid,
and the neighbourhood is searched again around that - the topic's centre rather
than the question's wording.

Refusal. Vector search always returns something. Without a distance gate and a
floor on the number of posts, asking for a trend about bitcoin would produce a
confident, entirely fictional property trend. Below either threshold this returns
None and the caller says it found nothing.
"""
import hashlib
import logging
import re
import unicodedata
from datetime import date, datetime

import numpy as np

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.trends import metrics, store

logger = logging.getLogger("trends.adhoc")

# Calibrated on the same scale the assistant's context retrieval uses: in-scope
# questions land at 0.22-0.36 and off-topic ones at 0.60 and beyond. This sits
# just below that gap.
MAX_DISTANCE = 0.52
MIN_POSTS = 12
CANDIDATES = 400
EF_SEARCH = 400

ORIGIN = "chat"


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "trend")[:48]


def _vector_literal(vec) -> str:
    return "[" + ",".join(f"{float(v):.6f}" for v in vec) + "]"


def _neighbours(vec, tag: str, limit: int) -> list[dict]:
    """Nearest relevant posts to a vector, with everything the metrics need.

    Runs against the base tables rather than the trend_posts view: ordering by
    distance through a UNION view cannot use the HNSW index (it has to build the
    union before it can sort), which is a timeout rather than a slow query.
    """
    sql = """
        WITH near AS (
            SELECT e.platform, e.post_id, (e.embedding <=> %(vec)s::vector) AS distance
            FROM realestate_intel.post_embedding e
            WHERE e.model = %(tag)s
            ORDER BY e.embedding <=> %(vec)s::vector
            LIMIT %(k)s
        )
        SELECT p.platform, p.post_id, p.source, p.caption, p.hashtags, p.posted_at,
               p.author_username, p.engagement_total, p.likes, p.comments, p.views,
               p.media_keys, p.post_url, n.distance
        FROM near n
        JOIN realestate_intel.trend_posts p
          ON p.platform = n.platform AND p.post_id = n.post_id
        WHERE p.posted_at IS NOT NULL
        ORDER BY n.distance
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
        cur.execute(sql, {"vec": _vector_literal(vec), "tag": tag, "k": limit})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _embeddings_for(posts: list[dict], tag: str) -> dict:
    if not posts:
        return {}
    keys = tuple((p["platform"], p["post_id"]) for p in posts)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT platform, post_id, embedding::text
                       FROM realestate_intel.post_embedding
                       WHERE model = %s AND (platform, post_id) IN %s""", (tag, keys))
        return {(r[0], r[1]): np.fromstring(r[2][1:-1], sep=",", dtype=np.float32)
                for r in cur.fetchall()}


def _live_run() -> tuple[str | None, date | None]:
    """The run an ad-hoc trend is measured against and ranked inside."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT run_id, metrics->>'as_of'
                       FROM realestate_intel.trends
                       WHERE origin = 'pipeline' AND country IS NULL
                       ORDER BY created_at DESC LIMIT 1""")
        row = cur.fetchone()
    if not row:
        return None, None
    as_of = None
    if row[1]:
        try:
            as_of = datetime.fromisoformat(row[1]).date()
        except ValueError:
            as_of = None
    return row[0], as_of


def _run_totals(run_id: str) -> tuple[int, int, int]:
    """The run's own window totals, so share-of-voice means the same thing here.

    Growth is a change in share of the conversation, not in raw volume, so it
    needs the totals across every trend in the window. Passing the trend's own
    counts as the totals makes both shares 1.0 and every trend report exactly
    0% - which is what happened before this existed.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT coalesce(sum((metrics->>'recent_posts')::int), 0),
                              coalesce(sum((metrics->>'previous_posts')::int), 0),
                              count(*)
                       FROM realestate_intel.trends
                       WHERE run_id = %s AND level = 'micro' AND origin = 'pipeline'""",
                    (run_id,))
        r = cur.fetchone()
    return int(r[0]), int(r[1]), max(int(r[2]), 1)


def _rank_within_run(run_id: str, volume_raw: float,
                     growth_pct: float | None) -> tuple[float, float]:
    """Where this trend's raw numbers fall among the run's own micro trends.

    Ranking against the live distribution is what makes the index comparable.
    A percentile over a set of one is 50.0 by definition and would say nothing.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT (metrics->>'volume_raw')::float,
                              (metrics->>'growth_pct')::float
                       FROM realestate_intel.trends
                       WHERE run_id = %s AND level = 'micro' AND origin = 'pipeline'""",
                    (run_id,))
        rows = cur.fetchall()
    if not rows:
        return 50.0, 50.0
    volumes = [r[0] for r in rows if r[0] is not None]
    growths = [r[1] for r in rows if r[1] is not None]

    def pct(value: float, population: list[float]) -> float:
        if not population:
            return 50.0
        below = sum(1 for v in population if v < value)
        equal = sum(1 for v in population if v == value)
        return round((below + equal / 2.0) / len(population) * 100.0, 1)

    growth_index = 0.0 if growth_pct is None else pct(growth_pct, growths)
    return pct(volume_raw, volumes), growth_index


KEYWORD_MIN_DF = 3
KEYWORD_COUNT = 10
KEYWORD_MAX_ACCOUNT_SHARE = 0.5
KEYWORD_SMOOTHING = 0.01


CORPUS_SAMPLE = 1500


def _corpus_sample(limit: int = CORPUS_SAMPLE) -> list[dict]:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '30s'")
        cur.execute("""SELECT caption, author_username FROM realestate_intel.trend_posts
                       WHERE caption IS NOT NULL AND abs(hashtext(post_id)) %% 10 = 0
                       LIMIT %s""", (limit,))
        return [{"caption": r[0], "author_username": r[1]} for r in cur.fetchall()]


def _keywords(posts: list[dict], background: list[dict]) -> list[str]:
    """Terms far more common in the trend's posts than in the corpus at large."""
    from sklearn.feature_extraction.text import CountVectorizer

    from services.trends_real_estate_service.app.trends import clusterer
    pool = posts + background
    try:
        vectorizer = CountVectorizer(token_pattern=clusterer._TOKEN, lowercase=True,
                                     stop_words=list(clusterer._stopwords()),
                                     min_df=KEYWORD_MIN_DF, binary=True)
        present = vectorizer.fit_transform([p.get("caption") or "" for p in pool]).tocsr()
    except ValueError:
        return []
    terms = vectorizer.get_feature_names_out()
    in_trend = np.asarray(present[:len(posts)].sum(axis=0)).ravel() / max(len(posts), 1)
    corpus = (np.asarray(present[len(posts):].sum(axis=0)).ravel() / len(background)
              if background else np.zeros(len(terms)))
    score = in_trend * np.log((in_trend + KEYWORD_SMOOTHING) / (corpus + KEYWORD_SMOOTHING))
    score[clusterer.one_account_terms(present, [p.get("author_username") or "" for p in pool],
                                      KEYWORD_MAX_ACCOUNT_SHARE)] = 0.0
    top = np.argsort(score)[::-1][:KEYWORD_COUNT]
    return [str(terms[i]) for i in top if score[i] > 0]


def _narrative(label: str, query: str, keywords: list[str], summary: str | None,
               interpret: dict, client=None) -> dict:
    """The same narrative fields a pipeline trend carries, written the same way."""
    narrative = {"summary": summary or f"Posts retrieved for the question: {query}",
                 "related_themes": [], "offering_entities": [], "keywords": keywords,
                 "naming_confidence": None}
    if not keywords:
        return narrative
    from openai import OpenAI

    from services.trends_real_estate_service.app.trends import namer
    settings = get_settings()
    model = settings.TREND_NAMING_MODEL or settings.OPENAI_MODEL
    try:
        client = client or OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=4, timeout=60)
        named = namer.name_cluster(keywords, client, model)
        if named.summary and not summary:
            narrative["summary"] = named.summary
        narrative["related_themes"] = named.related_themes
        narrative["offering_entities"] = named.offering_entities
        narrative["naming_confidence"] = named.confidence
        opportunity = namer.opportunity_summary(
            {**interpret, "summary": narrative["summary"]}, client, model)
        if opportunity:
            narrative["opportunity_summary"] = opportunity
    except Exception:
        logger.warning("could not write a narrative for ad-hoc trend %r", label, exc_info=True)
    return narrative


def build(query: str, embed_query, name: str | None = None,
          created_by: str | None = None, summary: str | None = None) -> dict | None:
    """Retrieve, measure and store one trend for `query`.

    Returns the stored row, or None when the corpus has too little to say —
    which is the honest answer far more often than a generated trend would be.
    """
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    run_id, as_of = _live_run()
    if not run_id:
        logger.warning("no pipeline run to measure against")
        return None

    seed = np.array(embed_query(query), dtype=np.float32)
    hits = [h for h in _neighbours(seed, tag, CANDIDATES) if h["distance"] <= MAX_DISTANCE]
    if len(hits) < MIN_POSTS:
        logger.info("query %r found only %s posts within %.2f", query, len(hits), MAX_DISTANCE)
        return None

    # Second pass around the centre of what came back, not the wording of the
    # question. Captions are mostly Arabic and queries mostly English, so the
    # first pass finds the topic but under-recalls it.
    vectors = _embeddings_for(hits[:60], tag)
    if vectors:
        centroid = np.mean(np.stack(list(vectors.values())), axis=0)
        merged = {(h["platform"], h["post_id"]): h for h in hits}
        for h in _neighbours(centroid, tag, CANDIDATES):
            if h["distance"] <= MAX_DISTANCE:
                merged.setdefault((h["platform"], h["post_id"]), h)
        hits = sorted(merged.values(), key=lambda h: h["distance"])

    posts = [h for h in hits if h.get("posted_at")]
    if len(posts) < MIN_POSTS:
        return None
    if as_of is None:
        as_of = max(p["posted_at"] for p in posts).date()

    label = (name or query).strip()[:120]
    keywords = _keywords(posts, _corpus_sample())
    terms = metrics.topical_terms(label, {"keywords": keywords})
    facts = metrics._post_facts(posts, as_of, terms)
    # Measured against the run's totals, and counted into them: this trend is
    # one more claimant on the same conversation, so it belongs in the
    # denominator alongside the trends it is being compared with.
    total_recent, total_previous, cohort_size = _run_totals(run_id)
    growth_pct = metrics.compute_growth_pct(
        facts["recent_posts"], facts["previous_posts"],
        total_recent + facts["recent_posts"],
        total_previous + facts["previous_posts"],
        cohort_size + 1)
    volume_index, growth_index = _rank_within_run(run_id, facts["volume_raw"], growth_pct)

    # Deterministic, so asking the same thing twice updates that trend instead
    # of littering the explorer with duplicates. Python's hash() is salted per
    # process and produced a fresh id on every call.
    fingerprint = hashlib.md5(f"{label}|{created_by or ''}".encode(),
                              usedforsecurity=False).hexdigest()[:8]
    trend_id = f"c-{_slug(label)}--{fingerprint}"
    quadrant = metrics.assign_quadrant(volume_index, growth_index)
    narrative = _narrative(label, query, keywords, summary, {
        "name": label, "level": "micro", "quadrant": quadrant,
        "post_count": facts["post_count"], "unique_creators": facts["unique_authors"],
        "growth_pct_8w": growth_pct, "platform_mix": facts["platform_mix"],
        "source_mix": facts["source_mix"]})
    row = {
        "trend_id": trend_id,
        "run_id": run_id,
        "level": "micro",
        "parent_trend_id": None,
        "name": label,
        "quadrant": quadrant,
        "volume_index": volume_index,
        "growth_index": growth_index,
        "post_count": facts["post_count"],
        "unique_authors": facts["unique_authors"],
        "narrative": narrative,
        "metrics": {
            "volume_raw": facts["volume_raw"],
            "growth_pct": growth_pct,
            "engagement_total": facts["engagement_total"],
            "platform_mix": facts["platform_mix"],
            "source_mix": facts["source_mix"],
            "months": facts["months"],
            "recent_posts": facts["recent_posts"],
            "previous_posts": facts["previous_posts"],
            "first_post": facts["first_post"],
            "is_new": facts["is_new"],
            "as_of": as_of.isoformat(),
            "match_distance": round(float(np.mean([p["distance"] for p in posts])), 4),
        },
        "timeline": facts["timeline"],
        "example_posts": {"top": facts["example_posts"],
                          "by_source": facts["example_posts_by_source"]},
        "member_posts": facts["member_posts"],
        "origin": ORIGIN,
        "created_by": created_by,
        "source_query": query,
    }
    store.upsert_trends([row])
    try:
        from services.trends_real_estate_service.app.trends import trend_embedding
        trend_embedding.save(run_id, tag, [(trend_id, embed_query(
            trend_embedding._text(label, f"{query}. {narrative['summary']}",
                                  narrative["keywords"], narrative["offering_entities"])))])
    except Exception:
        logger.warning("could not embed ad-hoc trend %s", trend_id, exc_info=True)
    logger.info("stored ad-hoc trend %s (%s posts, volume p%s, growth p%s)",
                trend_id, facts["post_count"], volume_index, growth_index)
    return row


def refresh_narratives(embed_query) -> list[str]:
    """Write the narrative for chat-created trends that were stored without one."""
    import json

    from services.trends_real_estate_service.app.trends import trend_embedding
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT run_id, trend_id, name, source_query, quadrant, post_count,
                              unique_authors, narrative, metrics, member_posts
                       FROM realestate_intel.trends
                       WHERE origin = %s
                         AND coalesce(jsonb_array_length(narrative->'related_themes'), 0) = 0""",
                    (ORIGIN,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    done = []
    sample = _corpus_sample()
    for row in rows:
        members = row["member_posts"]
        members = members if isinstance(members, list) else json.loads(members)
        keys = tuple((m["platform"], m["post_id"]) for m in members)
        if not keys:
            continue
        with store.get_conn() as conn, conn.cursor() as cur:
            cur.execute("""SELECT caption, author_username FROM realestate_intel.trend_posts
                           WHERE (platform, post_id) IN %s""", (keys,))
            posts = [{"caption": r[0], "author_username": r[1]} for r in cur.fetchall()]
        query = row["source_query"] or row["name"]
        m = row["metrics"] if isinstance(row["metrics"], dict) else json.loads(row["metrics"])
        narrative = _narrative(row["name"], query, _keywords(posts, sample), None, {
            "name": row["name"], "level": "micro", "quadrant": row["quadrant"],
            "post_count": row["post_count"], "unique_creators": row["unique_authors"],
            "growth_pct_8w": m.get("growth_pct"), "platform_mix": m.get("platform_mix"),
            "source_mix": m.get("source_mix")})
        if not narrative["related_themes"]:
            continue
        store.update_trend_narrative(row["trend_id"], narrative)
        trend_embedding.save(row["run_id"], tag, [(row["trend_id"], embed_query(
            trend_embedding._text(row["name"], f"{query}. {narrative['summary']}",
                                  narrative["keywords"], narrative["offering_entities"])))])
        done.append(row["trend_id"])
    return done


REUSE_DISTANCE = 0.36


def existing_chat_trend(query: str, embed_query,
                        max_distance: float = REUSE_DISTANCE) -> dict | None:
    """The chat-created trend in the live run closest to `query`, if close enough."""
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    run_id, _ = _live_run()
    if not run_id:
        return None
    vec = _vector_literal(embed_query(query))
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT t.trend_id, t.name, (e.embedding <=> %(vec)s::vector) AS distance
            FROM realestate_intel.trends t
            JOIN realestate_intel.trend_embedding e
              ON e.run_id = t.run_id AND e.trend_id = t.trend_id AND e.model = %(tag)s
            WHERE t.run_id = %(run)s AND t.origin = %(origin)s
            ORDER BY distance
            LIMIT 1
        """, {"vec": vec, "tag": tag, "run": run_id, "origin": ORIGIN})
        row = cur.fetchone()
    if not row or row[2] is None or row[2] > max_distance:
        return None
    return {"trend_id": row[0], "name": row[1], "distance": round(float(row[2]), 3)}


def similar_existing(query: str, embed_query, limit: int = 3) -> list[dict]:
    """Pipeline trends whose members overlap what this query retrieves.

    Offered so the answer can say "this is already covered by X" instead of
    quietly creating a near-duplicate of a trend the run already found.
    """
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    seed = np.array(embed_query(query), dtype=np.float32)
    hits = [h for h in _neighbours(seed, tag, 120) if h["distance"] <= MAX_DISTANCE]
    if not hits:
        return []
    keys = {(h["platform"], h["post_id"]) for h in hits}
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT trend_id, name, member_posts
                       FROM realestate_intel.trends
                       WHERE origin = 'pipeline' AND level = 'micro'
                         AND run_id = (SELECT run_id FROM realestate_intel.trends
                                       WHERE origin = 'pipeline' AND country IS NULL
                                       ORDER BY created_at DESC LIMIT 1)""")
        rows = cur.fetchall()
    import json
    scored = []
    for tid, tname, mp in rows:
        mp = mp if isinstance(mp, list) else json.loads(mp)
        members = {(m["platform"], m["post_id"]) for m in mp}
        if not members:
            continue
        overlap = len(keys & members)
        if overlap:
            scored.append({"trend_id": tid, "name": tname, "overlap_posts": overlap,
                           "overlap_pct": round(100.0 * overlap / len(keys), 1)})
    scored.sort(key=lambda r: -r["overlap_posts"])
    return scored[:limit]
