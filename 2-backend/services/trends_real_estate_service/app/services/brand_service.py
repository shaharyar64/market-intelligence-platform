from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.db import analysis_store

settings = get_settings()

_EVIDENCE_SAMPLE = 5
_EXAMPLE_POST_SAMPLE = 5


# The cohorts the brand surface covers. Community is a sampled consumer corpus,
# not an account, and must never be addressable as a brand.
TRACKED_ACCOUNT_TYPES = ["brand", "influencer"]


def list_brands(account_type: str | None = "brand") -> dict:
    """Accounts that have enriched data.

    Defaults to brands, so the brand pages keep showing brands. Visual
    intelligence asks for everything: the same enrichment now runs over the
    tracked influencers, and their analysis is the point of that screen. Pass
    None for both tracked types.

    None means brand + influencer, never community. In the food service there
    were only two cohorts, so dropping the filter was the same thing; real
    estate added a third, and an unfiltered query surfaced the community sample
    as a brand called "Consumers" with the whole brand surface addressable at
    its key.
    """
    rows = analysis_store.run_query("""
        SELECT brand_key,
               (array_agg(brand_name ORDER BY posted_at DESC))[1] AS name,
               (array_agg(account_type ORDER BY posted_at DESC))[1] AS account_type,
               COUNT(*) AS post_count,
               array_agg(DISTINCT platform) AS platforms
        FROM realestate_intel.post_analysis
        WHERE account_type = ANY(:account_types)
        GROUP BY brand_key
        ORDER BY name
    """, {"account_types": [account_type] if account_type else TRACKED_ACCOUNT_TYPES})
    return {"brands": [
        {"key": r["brand_key"], "name": r["name"] or r["brand_key"],
         "account_type": r.get("account_type") or "brand",
         "post_count": r["post_count"], "platforms": sorted(r["platforms"])}
        for r in rows if r["brand_key"]
    ]}


_OVERVIEW_SQL = f"""
WITH base AS (
    SELECT (array_agg(brand_name ORDER BY posted_at DESC))[1] AS name,
           (array_agg(account_type ORDER BY posted_at DESC))[1] AS account_type,
           array_agg(DISTINCT platform) AS platforms,
           COUNT(*) AS post_count,
           COALESCE(SUM(engagement_total), 0) AS total_engagement,
           MIN(posted_at) AS first_post_date,
           MAX(posted_at) AS last_post_date
    FROM realestate_intel.post_analysis
    WHERE brand_key = :key
    GROUP BY brand_key
),
theme_count AS (
    SELECT COUNT(DISTINCT elem->>'label') AS n
    FROM realestate_intel.post_analysis pa, jsonb_array_elements(pa.analysis->'themes') AS elem
    WHERE pa.brand_key = :key
),
offering_count AS (
    SELECT COUNT(DISTINCT elem->>'offering') AS n
    FROM realestate_intel.post_analysis pa, jsonb_array_elements(pa.analysis->'offering_focus') AS elem
    WHERE pa.brand_key = :key
),
semiotic AS (
    SELECT COALESCE(jsonb_object_agg(axis, score), '{{}}'::jsonb) AS axes
    FROM (
        SELECT kv.key AS axis, ROUND(AVG((kv.value)::numeric) * 100, 1) AS score
        FROM realestate_intel.post_analysis pa, jsonb_each_text(pa.analysis->'semiotic'->'visual') AS kv
        WHERE pa.brand_key = :key
        GROUP BY kv.key
    ) s
),
accounts AS (
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'platform', bp.platform,
               'account_username', bp.account_username,
               'followers', COALESCE(lp.followers, 0),
               'is_verified', COALESCE(lp.is_verified, false))
           ORDER BY bp.platform), '[]'::jsonb) AS accounts,
           COALESCE(SUM(lp.followers), 0) AS followers_total
    FROM ({analysis_store.BRAND_ACCOUNTS_SQL}) bp
    LEFT JOIN ({analysis_store.LIVE_PROFILE_SQL}) lp
      ON lp.platform = bp.platform AND lp.username = bp.account_username
    WHERE bp.brand_key = :key
)
SELECT base.*, theme_count.n AS theme_count, offering_count.n AS offering_count,
       semiotic.axes, accounts.accounts, accounts.followers_total
FROM base, theme_count, offering_count, semiotic, accounts
"""


def get_overview(key: str) -> dict | None:
    rows = analysis_store.run_query(_OVERVIEW_SQL, {"key": key})
    if not rows:
        return None
    row = rows[0]

    accounts = [{
        "platform": a["platform"], "account_username": a["account_username"],
        "followers": int(a.get("followers") or 0), "is_verified": bool(a.get("is_verified")),
    } for a in (row["accounts"] or [])]
    followers_total = int(row["followers_total"] or 0)

    post_count = row["post_count"]
    axes = {k: float(v) for k, v in (row["axes"] or {}).items()}
    top_territories = sorted(axes.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
    return {
        "key": key,
        "name": row["name"] or key,
        "account_type": row["account_type"] or "brand",
        "platforms": sorted(row["platforms"]),
        "accounts": accounts,
        "followers_total": followers_total,
        "post_count": post_count,
        "total_engagement": row["total_engagement"],
        "avg_engagement_per_post": round(row["total_engagement"] / post_count, 2) if post_count else 0.0,
        "first_post_date": row["first_post_date"].isoformat() if row["first_post_date"] else None,
        "last_post_date": row["last_post_date"].isoformat() if row["last_post_date"] else None,
        "theme_count": row["theme_count"] or 0,
        "offering_count": row["offering_count"] or 0,
        "visual_territories": [axis for axis, _score in top_territories],
    }


def _aggregate_facet(key: str, json_key: str, label_key: str, min_posts: int,
                     limit: int, canonical: bool = False) -> list[dict]:
    """Counts per label for one brand.

    Grouped on the case-folded label so spelling variants count once; the label
    shown back is the most common spelling in the group. With `canonical`, the
    `canonical` groups on the offering rather than the raw label. There is no
    alias table: an offering is grouped on its own normalised string.
    """
    group = ("lower(btrim(elem->>'offering'))"
             if canonical else f"lower(btrim(elem->>'{label_key}'))")
    join = ""
    exclude = ""
    params: dict = {"key": key, "min_posts": min_posts, "limit": limit}

    label = group if canonical else \
        f"mode() WITHIN GROUP (ORDER BY elem->>'{label_key}')"

    native = (f", mode() WITHIN GROUP (ORDER BY elem->>'{label_key}') "
              f"FILTER (WHERE elem->>'{label_key}' ~ '[؀-ۿ]') AS label_native"
              if canonical else ", NULL::text AS label_native")

    rows = analysis_store.run_query(f"""
        SELECT {label} AS label{native},
               COUNT(DISTINCT pa.post_id) AS post_count,
               COALESCE(SUM(pa.engagement_total), 0) AS engagement,
               AVG((elem->>'confidence')::real) AS avg_confidence,
               array_agg(DISTINCT elem->'evidence'->>0)
                 FILTER (WHERE elem->'evidence'->>0 IS NOT NULL) AS evidence,
               array_agg(DISTINCT pa.post_id) AS post_ids
        FROM realestate_intel.post_analysis pa,
             jsonb_array_elements(pa.analysis->'{json_key}') AS elem
        {join}
        WHERE pa.brand_key = :key
          AND btrim(COALESCE(elem->>'{label_key}', '')) <> ''
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
        "engagement": r["engagement"],
        "avg_confidence": round(float(r["avg_confidence"] or 0.0), 3),
        "evidence": (r["evidence"] or [])[:_EVIDENCE_SAMPLE],
        "example_post_ids": (r["post_ids"] or [])[:_EXAMPLE_POST_SAMPLE],
    } for r in rows]


def get_themes(key: str, min_posts: int, limit: int = 25) -> dict:
    rows = _aggregate_facet(key, "themes", "label", min_posts, limit)
    return {"brand_key": key, "min_posts": min_posts, "themes": rows}


def get_offerings(key: str, min_posts: int, limit: int = 25) -> dict:
    rows = _aggregate_facet(key, "offering_focus", "offering", min_posts, limit,
                            canonical=True)
    offerings = [{**r, "offering": r.pop("label"),
                 "offering_native": r.pop("label_native")} for r in rows]
    return {"brand_key": key, "min_posts": min_posts, "offerings": offerings}


def get_top_content(key: str, limit: int = 10, platform: str | None = None) -> dict:
    sql = """
        SELECT pa.post_id, pa.platform, pa.post_url,
               pa.account_username AS owner_username, pa.brand_name AS owner_name,
               pa.posted_at, pa.caption,
               pa.engagement, pa.engagement_total,
               COALESCE(
                 (SELECT array_agg(DISTINCT elem->>'label')
                  FROM jsonb_array_elements(pa.analysis->'themes') AS elem), '{}'
               ) AS themes,
               COALESCE(
                 (SELECT array_agg(DISTINCT elem->>'offering')
                  FROM jsonb_array_elements(pa.analysis->'offering_focus') AS elem), '{}'
               ) AS offerings
        FROM realestate_intel.post_analysis pa
        WHERE pa.brand_key = :key
    """
    params = {"key": key, "limit": limit}
    if platform:
        sql += " AND pa.platform = :platform"
        params["platform"] = platform
    sql += " ORDER BY pa.engagement_total DESC LIMIT :limit"

    rows = analysis_store.run_query(sql, params)
    items = []
    for r in rows:
        items.append({
            "post_id": r["post_id"], "platform": r["platform"], "post_url": r["post_url"],
            "owner": {"username": r["owner_username"], "name": r["owner_name"]},
            "posted_at": r["posted_at"].isoformat() if r["posted_at"] else None,
            "text": r["caption"] or "",
            "engagement": {**(r["engagement"] or {}), "total": r["engagement_total"]},
            "themes": r["themes"] or [],
            "offerings": r["offerings"] or [],
        })
    return {"brand_key": key, "items": items}


def get_functional_visual(key: str) -> dict:
    rows = analysis_store.run_query("""
        WITH total AS (
            SELECT COUNT(*) AS n FROM realestate_intel.post_analysis WHERE brand_key = :key
        )
        SELECT elem->>'category' AS category, COUNT(DISTINCT pa.post_id) AS post_count,
               (SELECT n FROM total) AS total_posts
        FROM realestate_intel.post_analysis pa,
             jsonb_array_elements(pa.analysis->'functional_visual') AS elem
        WHERE pa.brand_key = :key
        GROUP BY elem->>'category'
        ORDER BY post_count DESC
    """, {"key": key})
    categories = [
        {"category": r["category"], "post_count": r["post_count"],
         "pct": round(100.0 * r["post_count"] / r["total_posts"], 1) if r["total_posts"] else 0.0}
        for r in rows
    ]
    return {"brand_key": key, "categories": categories}


def get_semiotic(key: str) -> dict:
    rows = analysis_store.run_query("""
        SELECT kv.key AS axis, AVG((kv.value)::numeric) AS avg_score
        FROM realestate_intel.post_analysis pa,
             jsonb_each_text(pa.analysis->'semiotic'->'visual') AS kv
        WHERE pa.brand_key = :key
        GROUP BY kv.key
    """, {"key": key})
    axes = {r["axis"]: round(float(r["avg_score"]) * 100, 1) for r in rows}
    return {"brand_key": key, "axes": axes}


def get_trend_participation(key: str, limit: int = 8) -> dict:
    """Which generated trends this brand's own posts ended up in.

    Joined on the account handle rather than the post id. The tracked accounts'
    posts now sit in community_posts under source 'brand', so an id join would
    mostly work — but the handle is what actually defines the brand, and joining
    on it also catches the posts the keyword scrape found independently, which
    carry a different provenance but the same author.

    `share_pct` is the brand's own split - of its posts that reached any trend,
    what portion sits in this one. It is deliberately not "how much of the trend
    is this brand", which would be a fraction of a percent for every brand and
    say nothing about the brand.
    """
    rows = analysis_store.run_query("""
        WITH handles AS (
            SELECT DISTINCT account_username AS handle
            FROM realestate_intel.post_analysis
            WHERE brand_key = :key AND account_username IS NOT NULL
        ),
        latest AS (
            SELECT run_id FROM realestate_intel.trends WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
        )
        SELECT t.trend_id, t.name, t.quadrant, count(*) AS posts
        FROM realestate_intel.trend_member tm
        CROSS JOIN latest
        JOIN handles h ON h.handle = tm.author_username
        JOIN realestate_intel.trends t ON t.trend_id = tm.trend_id
        WHERE tm.run_id = latest.run_id AND tm.level = 'micro'
        GROUP BY t.trend_id, t.name, t.quadrant
        ORDER BY posts DESC
        LIMIT :limit
    """, {"key": key, "limit": limit})

    corpus = analysis_store.run_query("""
        SELECT count(*) AS posts
        FROM realestate_intel.trend_posts cp
        WHERE cp.author_username IN (
            SELECT DISTINCT account_username FROM realestate_intel.post_analysis
            WHERE brand_key = :key AND account_username IS NOT NULL
        )
    """, {"key": key})
    in_corpus = corpus[0]["posts"] if corpus else 0
    in_trends = sum(r["posts"] for r in rows)

    return {
        "brand_key": key,
        "posts_in_corpus": in_corpus,
        "posts_in_trends": in_trends,
        "trends": [{
            "trend_id": r["trend_id"],
            "name": r["name"],
            "quadrant": r["quadrant"],
            "posts": r["posts"],
            "share_pct": round(r["posts"] / in_trends * 100, 1) if in_trends else 0.0,
        } for r in rows],
    }


def get_trend_opportunities(key: str, limit: int = 8, min_competitors: int = 1) -> dict:
    """Trends this brand is absent from that its competitors are already in."""
    rows = analysis_store.run_query("""
        WITH latest AS (
            SELECT run_id FROM realestate_intel.trends WHERE country IS NULL ORDER BY created_at DESC LIMIT 1
        ),
        handles AS (
            SELECT DISTINCT account_username AS handle, brand_key
            FROM realestate_intel.post_analysis
            WHERE account_username IS NOT NULL AND brand_key IS NOT NULL
              AND account_type = 'brand'
        ),
        participation AS (
            SELECT t.trend_id, t.name, t.quadrant, t.post_count,
                   t.growth_index, t.volume_index,
                   t.narrative->>'summary' AS summary,
                   h.brand_key, count(*) AS posts
            FROM realestate_intel.trend_member tm
            CROSS JOIN latest
            JOIN realestate_intel.trends t ON t.trend_id = tm.trend_id
            JOIN handles h ON h.handle = tm.author_username
            WHERE tm.run_id = latest.run_id AND tm.level = 'micro'
            GROUP BY 1,2,3,4,5,6,7,8
        )
        SELECT trend_id, name, quadrant, post_count, growth_index, volume_index, summary,
               count(*) FILTER (WHERE brand_key <> :key) AS competitors,
               sum(posts) FILTER (WHERE brand_key <> :key) AS competitor_posts,
               coalesce(sum(posts) FILTER (WHERE brand_key = :key), 0) AS own_posts,
               array_agg(brand_key ORDER BY posts DESC)
                 FILTER (WHERE brand_key <> :key) AS competitor_keys
        FROM participation
        GROUP BY 1,2,3,4,5,6,7
        HAVING coalesce(sum(posts) FILTER (WHERE brand_key = :key), 0) = 0
           AND count(*) FILTER (WHERE brand_key <> :key) >= :min_competitors
        ORDER BY competitors DESC, growth_index DESC, competitor_posts DESC
        LIMIT :limit
    """, {"key": key, "limit": limit, "min_competitors": min_competitors})

    names = {b["key"]: b["name"] for b in list_brands(None)["brands"]}
    return {
        "brand_key": key,
        "opportunities": [{
            "trend_id": r["trend_id"],
            "name": r["name"],
            "quadrant": r["quadrant"],
            "growth": round(r["growth_index"]),
            "volume": round(r["volume_index"]),
            "trend_posts": r["post_count"],
            "competitors": r["competitors"],
            "competitor_posts": int(r["competitor_posts"] or 0),
            "competitor_names": [names.get(k, k) for k in (r["competitor_keys"] or [])][:4],
            "summary": r["summary"] or "",
        } for r in rows],
    }
