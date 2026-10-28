from shared.database import db
from typing import Optional

# =========================
# SAFE HELPERS
# =========================

def escape_sql(value: str) -> str:
    return value.replace("'", "''")


def country_filter(country: Optional[str], table_alias: str):
    if country:
        return f"AND {table_alias}.country = '{escape_sql(country)}'"
    return ""


def theme_filter(theme: Optional[str]):
    if theme:
        return f"AND p.theme = '{escape_sql(theme)}'"
    return ""


# =========================
# OVERVIEW
# =========================

async def fetch_kpis(country: Optional[str] = None):
    query = f"""
    SELECT
        COUNT(DISTINCT brand_name) AS total_brands,
        COUNT(DISTINCT country) AS total_countries,
        SUM(total_posts) AS total_posts,
        SUM(
            COALESCE(total_likes,0)
          + COALESCE(total_comments,0)
          + COALESCE(total_shares,0)
        ) AS total_engagement,
        SUM(
            (COALESCE(total_likes,0) * 8)
          + (COALESCE(total_comments,0) * 12)
          + (COALESCE(total_shares,0) * 5)
        ) AS estimated_total_reach,
        ROUND(
            SUM(
                COALESCE(total_likes,0)
              + COALESCE(total_comments,0)
              + COALESCE(total_shares,0)
            ) / NULLIF(SUM(total_posts),0),
            2
        ) AS avg_engagement_per_post
    FROM ev.social_data sd
    WHERE 1=1
    {country_filter(country, "sd")}
    """
    return db.query(query).to_dicts()


async def fetch_last_6_months_posts(country: Optional[str] = None):
    query = f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', p.uploaded_at::timestamptz), 'YYYY-MM') AS month,
        COUNT(*) AS total_posts,
        SUM(
            CASE
                WHEN COALESCE(p.views,0) > 0 THEN p.views
                ELSE (p.likes * 8) + (p.comments * 12)
            END
        ) AS estimated_reach,
        SUM(p.views + p.likes + p.comments) AS total_engagement
    FROM ev.posts p
    JOIN ev.social_data sd ON sd.username = p.username
    WHERE p.uploaded_at::timestamptz >=
          DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '6 months'
    {country_filter(country, "sd")}
    GROUP BY 1
    ORDER BY 1
    """
    return db.query(query).to_dicts()


async def fetch_engagement_trend(country: Optional[str] = None):
    query = f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', p.uploaded_at::timestamptz), 'YYYY-MM') AS month,
        SUM(p.views + p.likes + p.comments) AS total_engagement,
        ROUND(
            SUM(p.views + p.likes + p.comments) / NULLIF(COUNT(*),0),
            2
        ) AS avg_engagement_per_post
    FROM ev.posts p
    JOIN ev.social_data sd ON sd.username = p.username
    WHERE 1=1
    {country_filter(country, "sd")}
    GROUP BY 1
    ORDER BY 1
    """
    return db.query(query).to_dicts()


async def fetch_posts_trend(country: Optional[str] = None):
    query = f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', p.uploaded_at::timestamptz), 'YYYY-MM') AS month,
        COUNT(*) AS total_posts
    FROM ev.posts p
    JOIN ev.social_data sd ON sd.username = p.username
    WHERE 1=1
    {country_filter(country, "sd")}
    GROUP BY 1
    ORDER BY 1
    """
    return db.query(query).to_dicts()


async def fetch_total_posts_by_brand(country: Optional[str] = None):
    query = f"""
    SELECT
        sd.brand_name AS brand,
        COUNT(*) AS total_posts
    FROM ev.posts p
    JOIN ev.social_data sd ON sd.username = p.username
    WHERE 1=1
    {country_filter(country, "sd")}
    GROUP BY sd.brand_name
    ORDER BY total_posts DESC
    """
    return db.query(query).to_dicts()


# =========================
# THEMES
# =========================

async def fetch_top5_themes_by_volume(country=None, theme=None):
    query = f"""
    SELECT p.theme, COUNT(*) AS current_volume
    FROM ev.posts p
    WHERE 1=1
    {country_filter(country, "p")}
    {theme_filter(theme)}
    GROUP BY p.theme
    ORDER BY current_volume DESC
    LIMIT 5
    """
    return db.query(query).to_dicts()


async def fetch_theme_distribution(country=None, theme=None):
    query = f"""
    SELECT
        p.theme,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
    FROM ev.posts p
    WHERE 1=1
    {country_filter(country, "p")}
    {theme_filter(theme)}
    GROUP BY p.theme
    ORDER BY percentage DESC
    """
    return db.query(query).to_dicts()


async def fetch_themes_multiline(country=None, theme=None):
    query = f"""
    WITH top AS (
        SELECT p.theme
        FROM ev.posts p
        WHERE 1=1
        {country_filter(country, "p")}
        {theme_filter(theme)}
        GROUP BY p.theme
        ORDER BY SUM(p.likes + p.comments) DESC
        LIMIT 5
    )
    SELECT
        DATE_TRUNC('month', p.uploaded_at::timestamptz)::date AS month,
        p.theme,
        SUM(p.likes + p.comments) AS engagement
    FROM ev.posts p
    JOIN top t ON p.theme = t.theme
    GROUP BY 1,2
    ORDER BY 1,2
    """
    return db.query(query).to_dicts()


async def fetch_growing_themes_multiline(country=None, theme=None):
    query = f"""
    WITH m AS (
        SELECT
            DATE_TRUNC('month', p.uploaded_at::timestamptz)::date AS month,
            p.theme,
            SUM(p.likes + p.comments) AS engagement
        FROM ev.posts p
        WHERE 1=1
        {country_filter(country, "p")}
        {theme_filter(theme)}
        GROUP BY 1,2
    ),
    g AS (
        SELECT *,
               engagement - LAG(engagement) OVER (PARTITION BY theme ORDER BY month) AS growth
        FROM m
    ),
    top AS (
        SELECT theme
        FROM g
        GROUP BY theme
        ORDER BY SUM(growth) DESC
        LIMIT 5
    )
    SELECT g.month, g.theme, g.engagement
    FROM g
    JOIN top t ON g.theme = t.theme
    ORDER BY g.month, g.theme
    """
    return db.query(query).to_dicts()


async def fetch_growing_themes_bar(country=None, theme=None):
    query = f"""
    WITH m AS (
        SELECT
            DATE_TRUNC('month', p.uploaded_at::timestamptz) AS month,
            p.theme,
            SUM(p.likes + p.comments) AS engagement
        FROM ev.posts p
        WHERE 1=1
        {country_filter(country, "p")}
        {theme_filter(theme)}
        GROUP BY 1,2
    )
    SELECT
        theme,
        SUM(engagement - LAG(engagement) OVER (PARTITION BY theme ORDER BY month)) AS total_growth
    FROM m
    GROUP BY theme
    ORDER BY total_growth DESC
    LIMIT 5
    """
    return db.query(query).to_dicts()


# =========================
# SUB-THEMES
# =========================

async def fetch_top5_sub_themes_by_volume(country=None):
    query = f"""
    SELECT p.sub_theme, COUNT(*) AS current_volume
    FROM ev.posts p
    WHERE p.sub_theme IS NOT NULL
    {country_filter(country, "p")}
    GROUP BY p.sub_theme
    ORDER BY current_volume DESC
    LIMIT 5
    """
    return db.query(query).to_dicts()


async def fetch_sub_theme_distribution(country=None):
    query = f"""
    SELECT
        p.sub_theme,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
    FROM ev.posts p
    WHERE p.sub_theme IS NOT NULL
    {country_filter(country, "p")}
    GROUP BY p.sub_theme
    ORDER BY percentage DESC
    """
    return db.query(query).to_dicts()


async def fetch_sub_themes_multiline(country=None):
    query = f"""
    WITH top AS (
        SELECT p.sub_theme
        FROM ev.posts p
        WHERE p.sub_theme IS NOT NULL
        {country_filter(country, "p")}
        GROUP BY p.sub_theme
        ORDER BY SUM(p.likes + p.comments) DESC
        LIMIT 5
    )
    SELECT
        DATE_TRUNC('month', p.uploaded_at::timestamptz)::date AS month,
        p.sub_theme,
        SUM(p.likes + p.comments) AS engagement
    FROM ev.posts p
    JOIN top t ON p.sub_theme = t.sub_theme
    GROUP BY 1,2
    ORDER BY 1,2
    """
    return db.query(query).to_dicts()


async def fetch_growing_sub_themes_multiline(country=None):
    query = f"""
    WITH m AS (
        SELECT
            DATE_TRUNC('month', p.uploaded_at::timestamptz)::date AS month,
            p.sub_theme,
            SUM(p.likes + p.comments) AS engagement
        FROM ev.posts p
        WHERE p.sub_theme IS NOT NULL
        {country_filter(country, "p")}
        GROUP BY 1,2
    ),
    g AS (
        SELECT *,
               engagement - LAG(engagement) OVER (PARTITION BY sub_theme ORDER BY month) AS growth
        FROM m
    ),
    top AS (
        SELECT sub_theme
        FROM g
        GROUP BY sub_theme
        ORDER BY SUM(growth) DESC
        LIMIT 5
    )
    SELECT g.month, g.sub_theme, g.engagement
    FROM g
    JOIN top t ON g.sub_theme = t.sub_theme
    ORDER BY g.month, g.sub_theme
    """
    return db.query(query).to_dicts()


async def fetch_growing_sub_themes_bar(country=None):
    query = f"""
    WITH m AS (
        SELECT
            DATE_TRUNC('month', p.uploaded_at::timestamptz) AS month,
            p.sub_theme,
            SUM(p.likes + p.comments) AS engagement
        FROM ev.posts p
        WHERE p.sub_theme IS NOT NULL
        {country_filter(country, "p")}
        GROUP BY 1,2
    )
    SELECT
        sub_theme,
        SUM(engagement - LAG(engagement) OVER (PARTITION BY sub_theme ORDER BY month)) AS total_growth
    FROM m
    GROUP BY sub_theme
    ORDER BY total_growth DESC
    LIMIT 5
    """
    return db.query(query).to_dicts()
