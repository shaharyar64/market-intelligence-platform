from datetime import datetime
from typing import Literal

from shared.database import db


ThemeContentType = Literal["post", "audience_comment"]
_THEME_CONTENT_TYPES = {"post", "audience_comment"}
_CEER_TRENDS_PROJECT = "ceer_campaign"


def _escape_sql(value: str) -> str:
    return value.replace("'", "''")


def get_overview() -> dict:
    rows = db.query(
        """
        SELECT
            platform,
            COALESCE(followers, 0) AS followers,
            COALESCE(total_posts, 0) AS total_posts,
            COALESCE(total_likes, 0) AS total_likes,
            COALESCE(total_shares, 0) AS total_shares,
            COALESCE(public_comment_count, 0) AS public_comment_count,
            COALESCE(total_views, 0) AS total_views,
            COALESCE(collected_comments, 0) AS collected_comments
        FROM ceer_campaign.social_data
        ORDER BY platform
        """
    ).to_dicts()
    youtube_rows = db.query(
        """
        SELECT COUNT(*)::bigint AS comments
        FROM ceer_campaign.youtube_comment_theme_labels
        WHERE project = 'ceer_campaign'
        """
    ).to_dicts()

    totals = {
        "followers": 0,
        "posts": 0,
        "likes": 0,
        "shares": 0,
        "public_comments": 0,
        "views": 0,
        "collected_comments": 0,
        "social_collected_comments": 0,
        "youtube_collected_comments": 0,
    }
    for row in rows:
        totals["followers"] += row["followers"]
        totals["posts"] += row["total_posts"]
        totals["likes"] += row["total_likes"]
        totals["shares"] += row["total_shares"]
        totals["public_comments"] += row["public_comment_count"]
        totals["views"] += row["total_views"]
        totals["social_collected_comments"] += row["collected_comments"]
    totals["youtube_collected_comments"] = youtube_rows[0]["comments"] if youtube_rows else 0
    totals["collected_comments"] = (
        totals["social_collected_comments"] + totals["youtube_collected_comments"]
    )

    return {"kpis": totals, "platforms": rows}


def get_before_after_metrics() -> list[dict]:
    return db.query(
        """
        SELECT
            platform,
            posts_before, posts_after,
            total_likes_before, total_likes_after,
            likes_per_post_before, likes_per_post_after,
            public_comments_per_post_before, public_comments_per_post_after,
            views_per_observed_post_before, views_per_observed_post_after,
            median_likes_before, median_likes_after,
            posts_per_day_change_pct,
            likes_per_post_change_pct,
            public_comments_per_post_change_pct,
            views_per_observed_post_change_pct
        FROM ceer_campaign.launch_before_after_metrics
        ORDER BY platform
        """
    ).to_dicts()


def get_launch_impact() -> list[dict]:
    """Return the curated before, launch-day, and after launch windows."""
    return db.query(
        """
        WITH scoped_posts AS (
            SELECT 1 AS sort_order, 'before' AS period,
                   DATE '2026-09-14' AS start_date, DATE '2026-09-20' AS end_date,
                   likes, shares, public_comments AS comments, views, engagements
            FROM ceer_campaign.launch_before_analysis
            UNION ALL
            SELECT 2, 'launch_day', DATE '2026-09-21', DATE '2026-09-21',
                   likes, shares, public_comments AS comments, views, engagements
            FROM ceer_campaign.launch_day_analysis
            UNION ALL
            SELECT 3, 'after', DATE '2026-09-22', DATE '2026-09-28',
                   likes, shares, public_comments AS comments, views, engagements
            FROM ceer_campaign.launch_after_analysis
        )
        SELECT
            period,
            start_date::text AS start_date,
            end_date::text AS end_date,
            COUNT(*)::bigint AS posts,
            COALESCE(SUM(COALESCE(likes, 0)), 0)::bigint AS likes,
            COALESCE(SUM(COALESCE(comments, 0)), 0)::bigint AS comments,
            COALESCE(SUM(COALESCE(shares, 0)), 0)::bigint AS shares,
            COALESCE(SUM(COALESCE(views, 0)), 0)::bigint AS views,
            COALESCE(SUM(COALESCE(engagements, 0)), 0)::bigint AS engagements,
            ROUND(AVG(COALESCE(engagements, 0)), 1) AS engagements_per_post
        FROM scoped_posts
        GROUP BY sort_order, period, start_date, end_date
        ORDER BY sort_order
        """
    ).to_dicts()


def get_launch_themes() -> list[dict]:
    """Return readable post themes for the curated before, launch-day, and after windows."""
    return db.query(
        """
        WITH scoped_posts AS (
            SELECT 1 AS sort_order, 'before' AS period, theme, sub_theme
            FROM ceer_campaign.launch_before_analysis
            UNION ALL
            SELECT 2, 'launch_day', theme, sub_theme
            FROM ceer_campaign.launch_day_analysis
            UNION ALL
            SELECT 3, 'after', theme, sub_theme
            FROM ceer_campaign.launch_after_analysis
        ), readable_posts AS (
            SELECT sort_order, period, BTRIM(theme) AS theme
            FROM scoped_posts
            WHERE BTRIM(COALESCE(theme, '')) <> ''
              AND theme <> 'Other / Limited Signal'
              AND BTRIM(COALESCE(sub_theme, '')) <> ''
              AND LOWER(BTRIM(sub_theme)) <> LOWER('No usable text')
        ), grouped AS (
            SELECT sort_order, period, theme, COUNT(*)::bigint AS items
            FROM readable_posts
            GROUP BY sort_order, period, theme
        )
        SELECT
            period,
            theme,
            items,
            SUM(items) OVER (PARTITION BY period) AS period_items,
            ROUND(
                100.0 * items / NULLIF(SUM(items) OVER (PARTITION BY period), 0),
                1
            ) AS share_pct
        FROM grouped
        ORDER BY sort_order, items DESC, theme
        """
    ).to_dicts()


def get_sentiment() -> list[dict]:
    return db.query(
        """
        SELECT comparison_period, sentiment, comments, usable_comments, share_pct
        FROM ceer_campaign.launch_sentiment_summary
        ORDER BY comparison_period, sentiment
        """
    ).to_dicts()


def get_themes(content_type: ThemeContentType) -> list[dict]:
    if content_type not in _THEME_CONTENT_TYPES:
        raise ValueError("content_type must be 'post' or 'audience_comment'")

    return db.query(
        f"""
        WITH readable_themes AS (
            SELECT comparison_period, theme, sub_theme, items
            FROM ceer_campaign.launch_theme_summary
            WHERE content_type = '{content_type}'
              AND BTRIM(COALESCE(theme, '')) <> ''
              AND theme <> 'Other / Limited Signal'
              AND BTRIM(COALESCE(sub_theme, '')) <> ''
              AND LOWER(BTRIM(sub_theme)) <> LOWER('No usable text')
        )
        SELECT
            comparison_period,
            theme,
            sub_theme,
            items,
            SUM(items) OVER (PARTITION BY comparison_period) AS period_items,
            ROUND(
                100.0 * items / NULLIF(SUM(items) OVER (PARTITION BY comparison_period), 0),
                1
            ) AS share_pct
        FROM readable_themes
        ORDER BY comparison_period, items DESC, theme, sub_theme
        """
    ).to_dicts()


def get_search_interest(keyword: str | None = None, country: str | None = None) -> list[dict]:
    """Return a concise Google Trends time series for CEER search demand.

    With no keyword chosen, limit the chart to the five terms with the highest
    average interest so it stays legible.
    """
    filters = [f"project = '{_CEER_TRENDS_PROJECT}'"]
    if country:
        filters.append(f"country = '{_escape_sql(country)}'")
    if keyword:
        filters.append(f"keyword = '{_escape_sql(keyword)}'")
    where_clause = " AND ".join(filters)

    if keyword:
        query = f"""
            SELECT date, keyword, country, ROUND(AVG(value)::numeric, 2) AS interest
            FROM public.google_trends
            WHERE {where_clause}
            GROUP BY date, keyword, country
            ORDER BY date, keyword, country
        """
    else:
        query = f"""
            WITH filtered AS (
                SELECT date, keyword, country, value
                FROM public.google_trends
                WHERE {where_clause}
            ), top_keywords AS (
                SELECT keyword
                FROM filtered
                GROUP BY keyword
                ORDER BY AVG(value) DESC, keyword
                LIMIT 5
            )
            SELECT f.date, f.keyword, f.country, ROUND(AVG(f.value)::numeric, 2) AS interest
            FROM filtered f
            JOIN top_keywords t ON t.keyword = f.keyword
            GROUP BY f.date, f.keyword, f.country
            ORDER BY f.date, f.keyword, f.country
        """
    return db.query(query).to_dicts()


def get_search_regions(keyword: str | None = None, country: str | None = None) -> list[dict]:
    """Return the newest regional Google Trends snapshot for a CEER map."""
    filters = [f"project = '{_CEER_TRENDS_PROJECT}'"]
    if country:
        filters.append(f"country = '{_escape_sql(country)}'")
    if keyword:
        filters.append(f"keyword = '{_escape_sql(keyword)}'")
    where_clause = " AND ".join(filters)

    if keyword:
        query = f"""
            WITH latest_snapshot AS (
                SELECT MAX(last_updated) AS last_updated
                FROM public.google_trends_regions
                WHERE {where_clause}
            )
            SELECT keyword, geo_code, geo_name, country,
                   ROUND(AVG(value)::numeric, 2) AS score
            FROM public.google_trends_regions
            WHERE {where_clause}
              AND last_updated = (SELECT last_updated FROM latest_snapshot)
            GROUP BY keyword, geo_code, geo_name, country
            ORDER BY score DESC, geo_name
        """
    else:
        query = f"""
            WITH latest_snapshot AS (
                SELECT MAX(last_updated) AS last_updated
                FROM public.google_trends_regions
                WHERE {where_clause}
            ), scored AS (
                SELECT keyword, geo_code, geo_name, country,
                       ROUND(AVG(value)::numeric, 2) AS score
                FROM public.google_trends_regions
                WHERE {where_clause}
                  AND last_updated = (SELECT last_updated FROM latest_snapshot)
                GROUP BY keyword, geo_code, geo_name, country
            ), ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY geo_code, geo_name, country
                    ORDER BY score DESC, keyword
                ) AS rank
                FROM scored
            )
            SELECT keyword, geo_code, geo_name, country, score
            FROM ranked
            WHERE rank = 1
            ORDER BY country, geo_name
        """
    return db.query(query).to_dicts()


def get_content_performance() -> list[dict]:
    return db.query(
        """
        SELECT
            platform,
            COUNT(*) AS posts,
            COUNT(CASE WHEN views > 0 THEN 1 END) AS posts_with_views,
            COALESCE(SUM(likes), 0)::bigint AS likes,
            COALESCE(SUM(shares), 0)::bigint AS shares,
            COALESCE(SUM(comments), 0)::bigint AS comments,
            COALESCE(SUM(views), 0)::bigint AS views
        FROM ceer_campaign.social_data_posts
        GROUP BY platform
        ORDER BY views DESC, likes DESC
        """
    ).to_dicts()


def get_top_posts(limit: int = 6, platform: str = "all", sort: str = "views") -> list[dict]:
    if platform not in {"all", "instagram", "linkedin", "tiktok", "twitter"}:
        raise ValueError("Unsupported platform")
    if sort not in {"views", "engagement"}:
        raise ValueError("Unsupported ranking")
    safe_limit = min(max(limit, 1), 12)
    platform_filter = "" if platform == "all" else f"WHERE platform = '{platform}'"
    ranking = "COALESCE(views, 0)" if sort == "views" else "COALESCE(likes, 0) + COALESCE(shares, 0) + COALESCE(comments, 0)"
    return db.query(
        f"""
        SELECT
            post_id, platform, post_url, post_text,
            COALESCE(likes, 0) AS likes,
            COALESCE(shares, 0) AS shares,
            COALESCE(comments, 0) AS comments,
            views,
            theme, sub_theme
        FROM ceer_campaign.social_data_posts
        {platform_filter}
        ORDER BY {ranking} DESC, likes DESC, shares DESC, comments DESC, platform, post_id
        LIMIT {safe_limit}
        """
    ).to_dicts()


def get_posts_feed(mode: str = "top", limit: int = 12, offset: int = 0, platform: str = "all", period: str = "all", theme: str = "all") -> dict:
    if mode not in {"top", "all"}:
        raise ValueError("mode must be 'top' or 'all'")
    if platform not in {"all", "instagram", "linkedin", "tiktok", "twitter"}:
        raise ValueError("Unsupported platform")
    if period not in {"all", "before", "launch_day", "after"}:
        raise ValueError("Unsupported period")
    safe_limit = min(max(limit, 1), 100)
    safe_offset = max(offset, 0)
    ordering = (
        "COALESCE(views, 0) DESC, likes DESC, shares DESC, comments DESC, platform, post_id"
        if mode == "top"
        else "uploaded_at DESC NULLS LAST, platform, post_id"
    )
    filters = []
    if platform != "all": filters.append(f"platform = '{platform}'")
    if period != "all": filters.append(f"period = '{period}'")
    if theme != "all": filters.append(f"theme = '{_escape_sql(theme)}'")
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db.query(
        f"""
        WITH launch_posts AS (
            SELECT 'before' AS period, post_id, platform, post_url, post_text, likes, shares,
                   public_comments AS comments, views, theme, sub_theme, post_date::text AS uploaded_at
            FROM ceer_campaign.launch_before_analysis
            UNION ALL
            SELECT 'launch_day', post_id, platform, post_url, post_text, likes, shares,
                   public_comments, views, theme, sub_theme, post_date::text
            FROM ceer_campaign.launch_day_analysis
            UNION ALL
            SELECT 'after', post_id, platform, post_url, post_text, likes, shares,
                   public_comments, views, theme, sub_theme, post_date::text
            FROM ceer_campaign.launch_after_analysis
        )
        SELECT * FROM launch_posts
        {where_clause}
        ORDER BY {ordering}
        LIMIT {safe_limit} OFFSET {safe_offset}
        """
    ).to_dicts()
    total = db.query(
        f"""
        WITH launch_posts AS (
            SELECT 'before' AS period, post_id, platform, theme
            FROM ceer_campaign.launch_before_analysis
            UNION ALL
            SELECT 'launch_day', post_id, platform, theme
            FROM ceer_campaign.launch_day_analysis
            UNION ALL
            SELECT 'after', post_id, platform, theme
            FROM ceer_campaign.launch_after_analysis
        )
        SELECT COUNT(*)::bigint AS total
        FROM launch_posts
        {where_clause}
        """
    ).to_dicts()[0]["total"]
    return {"items": rows, "total": total}


def get_comments_feed(
    mode: str = "top",
    limit: int = 12,
    offset: int = 0,
    platform: str = "all",
    period: str = "all",
) -> dict:
    if mode not in {"top", "all"}:
        raise ValueError("mode must be 'top' or 'all'")
    if platform not in {"all", "instagram", "linkedin", "tiktok", "twitter", "youtube"}:
        raise ValueError("Unsupported platform")
    if period not in {"all", "before", "launch_day", "after"}:
        raise ValueError("Unsupported period")
    safe_limit = min(max(limit, 1), 50)
    safe_offset = max(offset, 0)
    ordering = "likes DESC, replies DESC, platform, comment_id" if mode == "top" else "platform, comment_id"
    source = """
        SELECT comment_id, platform, comment_text, COALESCE(likes, 0) AS likes,
               0::bigint AS replies, theme, sub_theme, created_at
        FROM ceer_campaign.social_data_comments
        UNION ALL
        SELECT comment_id, 'youtube' AS platform, comment_text, COALESCE(likes, 0),
               COALESCE(replies, 0), theme, sub_theme, NULL::text AS created_at
        FROM ceer_campaign.youtube_comment_theme_labels
        WHERE project = 'ceer_campaign'
    """
    period_filters = {
        "before": "created_at >= '2026-09-14' AND created_at < '2026-09-21'",
        "launch_day": "created_at >= '2026-09-21' AND created_at < '2026-09-22'",
        "after": "created_at >= '2026-09-22' AND created_at < '2026-09-29'",
    }
    filters = []
    if platform != "all":
        filters.append(f"platform = '{platform}'")
    if period != "all":
        filters.append(period_filters[period])
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db.query(
        f"""
        WITH comments AS ({source})
        SELECT * FROM comments
        {where_clause}
        ORDER BY {ordering}
        LIMIT {safe_limit} OFFSET {safe_offset}
        """
    ).to_dicts()
    total = db.query(
        f"WITH comments AS ({source}) SELECT COUNT(*)::bigint AS total FROM comments {where_clause}"
    ).to_dicts()[0]["total"]
    return {"items": rows, "total": total}


def get_activity() -> dict:
    rows = db.query(
        """
        SELECT uploaded_at, platform, COUNT(*) AS posts,
               COALESCE(SUM(views), 0)::bigint AS views,
               SUM(COALESCE(likes, 0) + COALESCE(shares, 0) + COALESCE(comments, 0))::bigint AS engagements
        FROM ceer_campaign.social_data_posts
        WHERE project = 'ceer_campaign'
          AND post_id <> '2102783013289652567'
        GROUP BY uploaded_at, platform
        """
    ).to_dicts()
    days = {}
    undated_posts = 0
    for row in rows:
        try:
            date = datetime.fromisoformat(row["uploaded_at"]).date().isoformat()
        except (TypeError, ValueError):
            undated_posts += row["posts"]
            continue
        key = (date, row["platform"])
        if key not in days:
            days[key] = {"date": date, "platform": row["platform"], "posts": 0, "views": 0, "engagements": 0}
        for metric in ("posts", "views", "engagements"):
            days[key][metric] += row[metric]
    return {"days": [days[key] for key in sorted(days)], "undated_posts": undated_posts}


def get_community_pulse() -> list[dict]:
    return db.query(
        """
        WITH collected_comments AS (
            SELECT platform, likes, theme
            FROM ceer_campaign.social_data_comments
            UNION ALL
            SELECT
                'youtube' AS platform,
                labels.likes,
                labels.theme
            FROM ceer_campaign.youtube_comment_theme_labels AS labels
            WHERE labels.project = 'ceer_campaign'
        )
        SELECT
            platform,
            COUNT(*) AS comments,
            COALESCE(SUM(likes), 0)::bigint AS comment_likes,
            COUNT(DISTINCT NULLIF(theme, '')) AS themes
        FROM collected_comments
        GROUP BY platform
        ORDER BY comments DESC, comment_likes DESC
        """
    ).to_dicts()


def get_all_audience_themes() -> list[dict]:
    """Return the combined, date-agnostic audience theme mix.

    This intentionally combines the collected social comments with undated
    YouTube comments. It is for overall audience context, not launch-window
    comparisons.
    """
    return db.query(
        """
        WITH combined_comments AS (
            SELECT theme, sub_theme
            FROM ceer_campaign.social_data_comments
            WHERE NOT (platform = 'twitter' AND LOWER(COALESCE(username, '')) = 'ceer')
            UNION ALL
            SELECT theme, sub_theme
            FROM ceer_campaign.youtube_comment_theme_labels
            WHERE project = 'ceer_campaign'
        ), readable_comments AS (
            SELECT BTRIM(theme) AS theme, BTRIM(sub_theme) AS sub_theme
            FROM combined_comments
            WHERE BTRIM(COALESCE(theme, '')) <> ''
              AND theme <> 'Data Quality (Internal)'
              AND theme <> 'Other / Limited Signal'
              AND BTRIM(COALESCE(sub_theme, '')) <> ''
              AND LOWER(BTRIM(sub_theme)) <> LOWER('No usable text')
        ), grouped AS (
            SELECT theme, sub_theme, COUNT(*)::bigint AS items
            FROM readable_comments
            GROUP BY theme, sub_theme
        )
        SELECT
            theme,
            sub_theme,
            items,
            SUM(items) OVER () AS total_items,
            ROUND(100.0 * items / NULLIF(SUM(items) OVER (), 0), 1) AS share_pct
        FROM grouped
        ORDER BY items DESC, theme, sub_theme
        """
    ).to_dicts()


def get_competitor_mentions() -> dict:
    """Summarise automotive references and comparison language in comments."""
    source = """
        SELECT comment_id, platform, comment_text, COALESCE(likes, 0) AS likes
        FROM ceer_campaign.social_data_comments
        UNION ALL
        SELECT comment_id, 'youtube', comment_text, COALESCE(likes, 0)
        FROM ceer_campaign.youtube_comment_theme_labels
        WHERE project = 'ceer_campaign'
    """
    references = """
        VALUES
          ('China / Chinese makers', 'Competitiveness, price, and manufacturing scale', '(\\mchina\\M|\\mchinese\\M|الصين|صيني|صينية)'),
          ('Tesla / Cybertruck', 'Cybertruck styling, angular design, and EV comparison', '(\\mtesla\\M|تسلا|\\mcybertruck\\M|سايبر[ -]?ترك|سايبرترك)'),
          ('Lucid', 'Saudi EV positioning, funding, and market viability', '(\\mlucid\\M|لوسيد)'),
          ('Toyota / Prius', 'Vehicle styling and proportions', '(\\mtoyota\\M|\\mprius\\M|تويوتا|بريوس)'),
          ('Ferrari', 'Design resemblance, including Ferrari Luce', '(\\mferrari\\M|فيراري)'),
          ('BMW', 'Premium-market comparison', '(\\mbmw\\M|بي[ -]?ام[ -]?دبليو)'),
          ('Hyundai', 'Styling and EV design', '(\\mhyundai\\M|هيونداي)'),
          ('Lamborghini', 'Exotic or supercar-like design', '(\\mlamborghini\\M|لامبورغيني|لامبورجيني)'),
          ('Honda', 'Design resemblance and product comparison', '(\\mhonda\\M|هوندا)')
    """
    comparison = "(\\mvs\\.?\\M|\\mversus\\M|compared to|better than|worse than|looks like|similar to|مقارنة|مقابل|مثل|يشبه)"
    rows = db.query(f"""
        WITH comments AS ({source}), reference_catalog(reference, typical_comparison, pattern) AS ({references}), matched AS (
          SELECT c.*, r.reference, r.typical_comparison,
                 (c.comment_text ~* '{comparison}') AS is_comparison
          FROM comments c JOIN reference_catalog r ON c.comment_text ~* r.pattern
        )
        SELECT reference, typical_comparison, COUNT(*)::bigint AS mentions,
               COUNT(*) FILTER (WHERE is_comparison)::bigint AS comparisons,
               COALESCE(SUM(likes), 0)::bigint AS likes
        FROM matched
        GROUP BY reference, typical_comparison
        ORDER BY mentions DESC, comparisons DESC, reference
    """).to_dicts()
    examples = db.query(f"""
        WITH comments AS ({source}), reference_catalog(reference, typical_comparison, pattern) AS ({references}), matched AS (
          SELECT c.*, r.reference, (c.comment_text ~* '{comparison}') AS is_comparison
          FROM comments c JOIN reference_catalog r ON c.comment_text ~* r.pattern
        )
        SELECT comment_id, platform, comment_text, likes, reference, is_comparison
        FROM matched
        ORDER BY is_comparison DESC, likes DESC, reference, comment_id
        LIMIT 30
    """).to_dicts()
    return {"references": rows, "examples": examples}
