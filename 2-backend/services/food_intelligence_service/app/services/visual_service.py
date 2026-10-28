from concurrent.futures import ThreadPoolExecutor

from services.food_intelligence_service.app.db import analysis_store
from services.food_intelligence_service.app.services import s3_media
from services.food_intelligence_service.app.services.brand_service import _NOT_A_PRODUCT


def get_gallery(limit: int = 12, keys: list[str] | None = None,
                account_type: str | None = None) -> dict:
    """Recent imagery, for a cohort and optionally a chosen set of accounts.

    Takes the cohort for the same reason the panels around it do: without it
    this is a global "newest images" query, and because influencers post most
    recently they filled all three tabs with the same twelve posts.

    Several keys rather than one, because the picker above it is a multi-select
    and honouring only the first key silently dropped the rest of the selection.
    """
    keys = keys or None
    rows = analysis_store.run_query("""
        SELECT post_id, platform, image_key, caption, brand_name
        FROM food_intel.post_analysis
        WHERE image_key IS NOT NULL
          AND (:account_type IS NULL OR account_type = :account_type)
          AND (:keys IS NULL OR brand_key = ANY(:keys))
        ORDER BY posted_at DESC
        LIMIT :limit
    """, {"limit": limit, "keys": keys, "account_type": account_type})
    items = [{
        "post_id": r["post_id"], "platform": r["platform"], "brand_name": r["brand_name"],
        "caption": r["caption"], "image_url": s3_media.presigned_url(r["image_key"]),
    } for r in rows]
    return {"account_type": account_type, "keys": keys, "items": items}


def get_brand_territories(limit: int = 8, account_type: str = "brand") -> dict:
    """Each account's two strongest visual axes, for the cohort being viewed.

    Takes the cohort because the page has one: showing brands while the user is
    looking at influencers invites them to read one as the other.
    """
    rows = analysis_store.run_query("""
        WITH scored AS (
            SELECT pa.brand_key,
                   (array_agg(pa.brand_name))[1] AS brand_name,
                   kv.key AS axis,
                   AVG((kv.value)::numeric) AS score
            FROM food_intel.post_analysis pa,
                 jsonb_each_text(pa.analysis->'semiotic'->'visual') AS kv
            WHERE pa.account_type = :account_type
            GROUP BY pa.brand_key, kv.key
        ),
        ranked AS (
            SELECT brand_key, brand_name, axis, score,
                   ROW_NUMBER() OVER (PARTITION BY brand_key ORDER BY score DESC, axis ASC) AS rn
            FROM scored
        )
        SELECT brand_key, (array_agg(brand_name))[1] AS brand_name,
               array_agg(axis ORDER BY score DESC, axis ASC) FILTER (WHERE rn <= 2) AS territories
        FROM ranked
        GROUP BY brand_key
        ORDER BY brand_key
        LIMIT :limit
    """, {"limit": limit, "account_type": account_type})
    return {"brands": [
        {"brand_key": r["brand_key"], "brand_name": r["brand_name"] or r["brand_key"],
         "visual_territories": list(r["territories"] or [])}
        for r in rows
    ]}


# ── cohort analysis ──────────────────────────────────────────────────────
# Brands, influencers and consumers are enriched by the same pipeline into the
# same table, which is what lets these three read side by side. They are not
# measured the same way, though, and the difference has to reach the screen:
# every tracked brand and influencer post is analysed, while consumers are
# sampled - 354,912 food posts is too many to send through seven LLM nodes for
# an answer a stratified sample already gives. `sampled` says which is which.
COHORTS = ("brand", "influencer", "community")

_MIN_POSTS_DEFAULT = 2
_EVIDENCE = 3


def cohort_counts() -> dict:
    """Posts, accounts and coverage per cohort — the tab labels."""
    rows = analysis_store.run_query("""
        SELECT account_type,
               COUNT(*) AS analysed_posts,
               COUNT(DISTINCT account_username) AS accounts,
               COALESCE(SUM(engagement_total), 0) AS engagement
        FROM food_intel.post_analysis
        WHERE account_type IS NOT NULL
        GROUP BY account_type
    """)
    by_type = {r["account_type"]: r for r in rows}
    out = []
    for cohort in COHORTS:
        r = by_type.get(cohort)
        out.append({
            "account_type": cohort,
            "analysed_posts": r["analysed_posts"] if r else 0,
            "accounts": r["accounts"] if r else 0,
            "engagement": int(r["engagement"]) if r else 0,
            "sampled": cohort == "community",
        })
    return {"cohorts": out}


def _cohort_facet(account_type: str, keys: list[str] | None, json_key: str,
                  label_key: str, min_posts: int, limit: int,
                  canonical: bool = False) -> list[dict]:
    """One facet of the analysis, rolled up over a whole cohort.

    Narrowing to a single account is optional: the cohort view is the point of
    these panels, and for consumers there is no account to pick - the sample
    spans 178k of them.

    `canonical` uses the product names the enrichment wrote: one English name
    per product, its Arabic name, and a kind that marks brands and hashtags.
    """
    # Grouped on the case-folded label. The model writes the same idea three
    # ways - "Ingredients", "Ingredients list", "Ingredients List" - and left
    # raw they split one theme into three rows that each look minor. The label
    # shown back is the most common spelling of the group.
    group = f"lower(btrim(elem->>'{label_key}'))"
    label = group if canonical \
        else f"mode() WITHIN GROUP (ORDER BY elem->>'{label_key}')"
    join = ""
    exclude = ("AND COALESCE(elem->>'kind', 'product') <> ALL(:not_product)"
               if canonical else "")
    params: dict = {"account_type": account_type, "keys": keys,
                    "min_posts": min_posts, "limit": limit}
    if canonical:
        params["not_product"] = list(_NOT_A_PRODUCT)

    native = (", mode() WITHIN GROUP (ORDER BY elem->>'product_ar') "
              "FILTER (WHERE COALESCE(elem->>'product_ar', '') <> '') AS label_native"
              if canonical else ", NULL::text AS label_native")

    rows = analysis_store.run_query(f"""
        SELECT {label} AS label{native},
               COUNT(DISTINCT pa.post_id) AS post_count,
               COALESCE(SUM(pa.engagement_total), 0) AS engagement,
               AVG((elem->>'confidence')::real) AS avg_confidence,
               array_agg(DISTINCT elem->'evidence'->>0)
                 FILTER (WHERE elem->'evidence'->>0 IS NOT NULL) AS evidence
        FROM food_intel.post_analysis pa,
             jsonb_array_elements(pa.analysis->'{json_key}') AS elem
        {join}
        WHERE pa.account_type = :account_type
          AND (:keys IS NULL OR pa.brand_key = ANY(:keys))
          AND elem->>'{label_key}' IS NOT NULL
          AND btrim(elem->>'{label_key}') <> ''
          {exclude}
        GROUP BY {group}
        HAVING COUNT(DISTINCT pa.post_id) >= :min_posts
        ORDER BY post_count DESC, engagement DESC
        LIMIT :limit
    """, params)
    def native_of(r: dict) -> str | None:
        """The original wording, suppressed when it just repeats the label."""
        got = (r.get("label_native") or "").strip()
        return got or None if got.lower() != (r["label"] or "").strip().lower() else None

    return [{
        "label": r["label"],
        **({"label_native": native_of(r)} if canonical else {}),
        "post_count": r["post_count"],
        "engagement": int(r["engagement"]),
        "avg_confidence": round(float(r["avg_confidence"] or 0.0), 3),
        "evidence": (r["evidence"] or [])[:_EVIDENCE],
    } for r in rows]


_HEAD_SQL = """
    SELECT COUNT(*) AS analysed_posts,
           COUNT(DISTINCT account_username) AS accounts,
           COALESCE(SUM(engagement_total), 0) AS engagement,
           MIN(posted_at) AS first_post,
           MAX(posted_at) AS last_post
    FROM food_intel.post_analysis
    WHERE account_type = :account_type
      AND (:keys IS NULL OR brand_key = ANY(:keys))
"""

_LANGUAGES_SQL = """
    SELECT COALESCE(language, 'unknown') AS language, COUNT(*) AS post_count
    FROM food_intel.post_analysis
    WHERE account_type = :account_type
      AND (:keys IS NULL OR brand_key = ANY(:keys))
    GROUP BY 1 ORDER BY post_count DESC
"""


def get_cohort_analysis(account_type: str, keys: list[str] | None = None,
                        min_posts: int = _MIN_POSTS_DEFAULT,
                        limit: int = 15) -> dict:
    """Themes, products and language for a cohort, or a chosen set of accounts.

    Several accounts rather than one: comparing three creators is a question
    people actually have, and running it one at a time and adding up the bars by
    eye is not an answer.
    """
    keys = keys or None
    if account_type not in COHORTS:
        raise ValueError(f"Unknown cohort: {account_type}")

    # These four reads do not depend on each other, and against a database in
    # another region latency dominates: run one after another they cost four
    # round trips end to end, overlapped they cost one. The connection pool is
    # sized well above this fan-out, so nobody queues waiting for a slot.
    params = {"account_type": account_type, "keys": keys}
    with ThreadPoolExecutor(max_workers=4) as pool:
        head_f = pool.submit(analysis_store.run_query, _HEAD_SQL, params)
        languages_f = pool.submit(analysis_store.run_query, _LANGUAGES_SQL, params)
        themes_f = pool.submit(_cohort_facet, account_type, keys, "themes",
                               "label", min_posts, limit)
        products_f = pool.submit(_cohort_facet, account_type, keys,
                                 "product_focus", "product", min_posts, limit,
                                 True)
        # .result() re-raises in the caller, so a failed query still surfaces
        # as it did when these ran inline.
        head = head_f.result()
        languages = languages_f.result()
        themes = themes_f.result()
        products = products_f.result()

    h = head[0] if head else {}
    total = sum(r["post_count"] for r in languages) or 1
    return {
        "account_type": account_type,
        "keys": keys,
        "sampled": account_type == "community",
        "analysed_posts": h.get("analysed_posts", 0) or 0,
        "accounts": h.get("accounts", 0) or 0,
        "engagement": int(h.get("engagement") or 0),
        "first_post": str(h["first_post"])[:10] if h.get("first_post") else None,
        "last_post": str(h["last_post"])[:10] if h.get("last_post") else None,
        "themes": themes,
        "products": [{**p, "product": p.pop("label")} for p in products],
        "languages": [{"language": r["language"], "post_count": r["post_count"],
                       "pct": round(100.0 * r["post_count"] / total, 1)}
                      for r in languages],
    }


# ── visual territories over time ─────────────────────────────────────────
# A territory is one axis of the visual analysis - indulgent, modern, natural
# and so on - and a post belongs to it when it scores at least TERRITORY_FLOOR.
# The axes are not exclusive: a post can be both indulgent and traditional, so
# the shares below do not sum to 100 and are not meant to.
TERRITORY_FLOOR = 0.5
TERRITORY_WINDOW_DAYS = 56


def _territory_basis(account_type: str | None, key: str | None) -> str:
    if key:
        return f"{key} only"
    if account_type == "brand":
        return "tracked brand accounts"
    if account_type == "influencer":
        return "tracked influencer accounts"
    if account_type == "community":
        return "the consumer sample"
    return "tracked brand and influencer accounts"


def get_territory_growth(limit: int = 8, account_type: str | None = None,
                         key: str | list[str] | None = None) -> dict:
    """Which visual territories are gaining share, and which are losing it.

    Measured over the tracked brand and influencer accounts only. Every post
    those accounts published is analysed, so their coverage is continuous and a
    change over time means something. The consumer sample is deliberately
    excluded: it was drawn by engagement within each trend rather than by date,
    so it carries posts from 2017 alongside 2026 and would read as a trend when
    it is an artefact of how the sample was chosen.

    Growth is the change in a territory's SHARE of the window, not its raw
    count - the same definition the trends use, and for the same reason: raw
    counts move with how much was collected, share moves with what was said.
    """
    # Territories are a per-account view; with several selected this reports
    # the cohort rather than silently showing one of them.
    if isinstance(key, (list, tuple)):
        key = key[0] if len(key) == 1 else None

    rows = analysis_store.run_query("""
        WITH tracked AS (
            SELECT pa.post_id, pa.platform, pa.posted_at, pa.analysis
            FROM food_intel.post_analysis pa
            WHERE pa.posted_at IS NOT NULL
              AND (:account_type IS NULL
                   OR pa.account_type = :account_type)
              AND (:account_type IS NOT NULL
                   OR pa.account_type IN ('brand', 'influencer'))
              AND (:key IS NULL OR pa.brand_key = :key)
        ),
        bounds AS (SELECT max(posted_at) AS as_of FROM tracked),
        -- How many posts each window holds, counted once per post. This is the
        -- denominator: a post carries several territories at a time, so
        -- counting territory tags instead would answer a question nobody asked
        -- and read four times smaller than it should.
        totals AS (
            SELECT count(*) FILTER (WHERE t.posted_at > b.as_of - (:days || ' days')::interval)
                     AS recent_posts,
                   count(*) FILTER (WHERE t.posted_at <= b.as_of - (:days || ' days')::interval
                                      AND t.posted_at > b.as_of - (2 * :days || ' days')::interval)
                     AS previous_posts
            FROM tracked t CROSS JOIN bounds b
        ),
        scored AS (
            SELECT t.post_id, t.platform, t.posted_at, kv.key AS axis,
                   (kv.value)::numeric AS score
            FROM tracked t, jsonb_each_text(t.analysis->'semiotic'->'visual') AS kv
        )
        SELECT s.axis,
               count(DISTINCT (s.platform, s.post_id))
                 FILTER (WHERE s.score >= :floor
                           AND s.posted_at > b.as_of - (:days || ' days')::interval) AS recent,
               count(DISTINCT (s.platform, s.post_id))
                 FILTER (WHERE s.score >= :floor
                           AND s.posted_at <= b.as_of - (:days || ' days')::interval
                           AND s.posted_at > b.as_of - (2 * :days || ' days')::interval) AS previous,
               (SELECT as_of FROM bounds) AS as_of,
               (SELECT recent_posts FROM totals) AS recent_total,
               (SELECT previous_posts FROM totals) AS previous_total
        FROM scored s CROSS JOIN bounds b
        GROUP BY s.axis
        ORDER BY recent DESC
    """, {"floor": TERRITORY_FLOOR, "days": TERRITORY_WINDOW_DAYS,
          "account_type": account_type, "key": key})

    if not rows:
        return {"territories": [], "as_of": None,
                "window_days": TERRITORY_WINDOW_DAYS,
                "basis": _territory_basis(account_type, key),
                "time_ordered": account_type != "community"}

    from services.food_intelligence_service.app.trends import metrics

    as_of = rows[0]["as_of"]
    total_recent = int(rows[0]["recent_total"] or 0)
    total_previous = int(rows[0]["previous_total"] or 0)

    territories = []
    for r in rows:
        recent, previous = int(r["recent"]), int(r["previous"])
        # Penetration: the share of posts in the window that read this way.
        # Dividing by the window's post count is what cancels collection
        # volume, so a territory can only rise here by appearing in a larger
        # proportion of what was published - not because more was published.
        # The territories overlap, so these do not sum to 100.
        share = 100.0 * recent / total_recent if total_recent else 0.0
        territories.append({
            "territory": r["axis"],
            "recent_posts": recent,
            "previous_posts": previous,
            "share_pct": round(share, 1),
            "growth_pct": round(metrics.compute_growth_pct(
                recent, previous, total_recent, total_previous, 1), 1),
        })
    territories.sort(key=lambda t: t["growth_pct"], reverse=True)
    return {
        "territories": territories[:limit],
        "as_of": str(as_of)[:10] if as_of else None,
        "window_days": TERRITORY_WINDOW_DAYS,
        "basis": _territory_basis(account_type, key),
        # The consumer sample was drawn by engagement within each trend rather
        # than by date, so it holds posts from 2017 beside 2026. Its mix is
        # meaningful; its movement between two windows is not, and the screen
        # has to say which of the two it is showing.
        "time_ordered": account_type != "community",
    }
