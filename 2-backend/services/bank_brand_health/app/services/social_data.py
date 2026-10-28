from services.bank_brand_health.app.utils.database import db
from services.bank_brand_health.app.services.search_data import to_raw_keyword

DEFAULT_START_DATE = "2025-01-01"


def date_range_clause(column: str, start_date=None, end_date=None) -> str:
    """Build a `column >= ... [AND column <= ...]` clause. Defaults start to 2025-01-01."""
    clauses = [f"{column} >= '{start_date or DEFAULT_START_DATE}'"]
    if end_date:
        clauses.append(f"{column} <= '{end_date}'")
    return " AND ".join(clauses)


# ✅ Frequency mapping
# uploaded_at is stored as text on social_data_posts, so date_trunc/EXTRACT
# need an explicit ::timestamp cast (same reason the associations section
# below casts date::timestamp).
FREQUENCY_PERIOD = {
    "1m": "TO_CHAR(date_trunc('month', uploaded_at::timestamp), 'YYYY-MM')",
    "3m": "TO_CHAR(date_trunc('quarter', uploaded_at::timestamp), 'YYYY-MM')",
    "6m": """CASE
                WHEN EXTRACT(MONTH FROM uploaded_at::timestamp) <= 6
                THEN CONCAT(EXTRACT(YEAR FROM uploaded_at::timestamp), '-H1')
                ELSE CONCAT(EXTRACT(YEAR FROM uploaded_at::timestamp), '-H2')
            END""",
    "1y": "TO_CHAR(date_trunc('year', uploaded_at::timestamp), 'YYYY')"
}

###########################################################
# ✅ 0. SOCIAL OVERVIEW
###########################################################
async def fetch_social_overview(bank=None, platform=None, start_date=None, end_date=None):
    filters = [date_range_clause("uploaded_at", start_date, end_date)]
    if bank:
        filters.append(f"brand_name = '{bank}'")
    if platform:
        filters.append(f"platform = '{platform}'")

    where_clause = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT
            total_volume,
            total_banks,
            total_engagement,
            total_reach,
            ROUND(total_engagement::numeric / total_volume, 2) AS avg_engagement
        FROM (
            SELECT 
                COUNT(*) AS total_volume,
                COUNT(DISTINCT brand_name) AS total_banks,
                SUM(likes + shares + comments + views) AS total_engagement,
                SUM(views) AS total_reach
            FROM saudi_banks.social_data_posts
            {where_clause}
        ) AS sub;
    """

    df = db.query(query)
    return df.to_dicts()[0]


###########################################################
# ✅ 1. POSTS DISTRIBUTION
###########################################################
async def fetch_post_distribution(bank=None, platform=None, start_date=None, end_date=None):
    """
    If bank is provided: return engagement breakdown for that bank (likes, shares, comments, views, total_engagement).
    If bank is not provided: return total_posts per bank (distribution).
    Platform filter is applied in either case if provided.
    """
    filters = [date_range_clause("uploaded_at", start_date, end_date)]
    if bank:
        filters.append(f"brand_name = '{bank}'")
    if platform:
        filters.append(f"platform = '{platform}'")

    where_clause = "WHERE " + " AND ".join(filters)

    # Case A: detailed engagement for single bank
    if bank:
        query = f"""
            SELECT
                COALESCE(SUM(likes),0)   AS likes,
                COALESCE(SUM(shares),0)  AS shares,
                COALESCE(SUM(comments),0) AS comments,
                COALESCE(SUM(views),0)   AS views,
                COALESCE(SUM(likes + shares + comments + views),0) AS total_engagement
            FROM saudi_banks.social_data_posts
            {where_clause};
        """
        df = db.query(query)
        rows = df.to_dicts()
        # return a single dict with engagement slices
        return rows

    # Case B: distribution of posts by bank, including engagement breakdown
    query = f"""
        SELECT
            brand_name AS bank,
            COUNT(*) AS total_posts,
            COALESCE(SUM(likes),0)    AS likes,
            COALESCE(SUM(shares),0)   AS shares,
            COALESCE(SUM(comments),0) AS comments,
            COALESCE(SUM(views),0)    AS views,
            COALESCE(SUM(likes + shares + comments + views),0) AS total_engagement
        FROM saudi_banks.social_data_posts
        {where_clause}
        GROUP BY brand_name
        ORDER BY total_posts DESC;
    """
    df = db.query(query)
    return df.to_dicts()


###########################################################
# ✅ 2. LAST 6 MONTHS VOLUME
###########################################################
async def fetch_post_volume_last6months(bank=None, platform=None):
    filters = []
    if bank:
        filters.append(f"brand_name = '{bank}'")
    if platform:
        filters.append(f"platform = '{platform}'")

    extra_filters = (" AND " + " AND ".join(filters)) if filters else ""

    query = f"""
        WITH last_date AS (
            SELECT MAX(uploaded_at::timestamp) AS max_date
            FROM saudi_banks.social_data_posts
        ),
        range AS (
            SELECT
                DATE_TRUNC('month', max_date) - INTERVAL '5 months' AS start_date,
                max_date
            FROM last_date
        )
        SELECT
            TO_CHAR(DATE_TRUNC('month', uploaded_at::timestamp), 'YYYY-MM') AS month,
            COUNT(*) AS volume
        FROM saudi_banks.social_data_posts, range
        WHERE uploaded_at::timestamp >= range.start_date
        AND uploaded_at::timestamp <= range.max_date
        {extra_filters}
        GROUP BY month
        ORDER BY month;
    """
    df = db.query(query)
    return df.to_dicts()


###########################################################
# ✅ 3. VOLUME TREND
###########################################################
async def fetch_volume_trend(frequency, bank=None, platform=None, start_date=None, end_date=None):
    period_expr = FREQUENCY_PERIOD[frequency]

    filters = [date_range_clause("uploaded_at", start_date, end_date)]
    if bank:
        filters.append(f"brand_name = '{bank}'")
    if platform:
        filters.append(f"platform = '{platform}'")

    where_clause = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT
            {period_expr} AS period,
            COUNT(*) AS volume
        FROM saudi_banks.social_data_posts
        {where_clause}
        GROUP BY period
        ORDER BY period;
    """
    df = db.query(query)
    return df.to_dicts()


###########################################################
# ✅ 4. ENGAGEMENT TREND
###########################################################
async def fetch_engagement_trend(frequency, bank=None, platform=None, start_date=None, end_date=None):
    period_expr = FREQUENCY_PERIOD[frequency]

    filters = [date_range_clause("uploaded_at", start_date, end_date)]
    if bank:
        filters.append(f"brand_name = '{bank}'")
    if platform:
        filters.append(f"platform = '{platform}'")

    where_clause = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT
            {period_expr} AS period,
            SUM(likes + shares + comments + views) AS engagement
        FROM saudi_banks.social_data_posts
        {where_clause}
        GROUP BY period
        ORDER BY period;
    """
    df = db.query(query)
    return df.to_dicts()


###########################################################
# ✅ 4b. BANK VOLUME GROWTH ("Fastest Growing" KPI)
###########################################################
async def fetch_bank_volume_growth(
    start_date=None,
    end_date=None,
    platform=None,
    banks: list[str] | None = None,
    limit: int | None = None,
):
    """Mirrors search-data/top-growing: growth is the slope (REGR_SLOPE) of
    monthly Share of Volume (0-100 scale) against sequential month number,
    i.e. percentage POINTS of share change per month. Share is always
    computed across ALL banks so proportions are correct; an optional bank
    filter narrows which rows are returned, and `limit` caps the row count
    (ordered by growth desc) when no specific banks are given. No positivity
    filter: banks with declining share are included.
    """
    filters = [date_range_clause("uploaded_at", start_date, end_date)]
    if platform:
        filters.append(f"platform = '{platform}'")
    where_clause = "WHERE " + " AND ".join(filters)

    bank_filter = ""
    limit_clause = ""
    if banks:
        escaped = [b.replace("'", "''") for b in banks]
        bank_list = "(" + ", ".join(f"'{b}'" for b in escaped) + ")"
        bank_filter = f"WHERE g.bank IN {bank_list}"
    elif limit:
        limit_clause = f"LIMIT {int(limit)}"

    query = f"""
        WITH monthly AS (
            SELECT
                brand_name AS bank,
                {FREQUENCY_PERIOD["1m"]} AS period,
                COUNT(*) AS volume
            FROM saudi_banks.social_data_posts
            {where_clause}
            GROUP BY bank, period
        ),
        with_share AS (
            SELECT
                bank,
                period,
                DENSE_RANK() OVER (ORDER BY period) AS period_num,
                volume::numeric / NULLIF(SUM(volume) OVER (PARTITION BY period), 0) * 100 AS share_pct
            FROM monthly
        ),
        current_share AS (
            SELECT bank, ROUND(share_pct::numeric, 2) AS current_share_of_volume
            FROM with_share
            WHERE period_num = (SELECT MAX(period_num) FROM with_share)
        ),
        growth AS (
            SELECT
                bank,
                ROUND(REGR_SLOPE(share_pct, period_num)::numeric, 4) AS growth
            FROM with_share
            GROUP BY bank
        )
        SELECT
            g.bank,
            g.growth,
            c.current_share_of_volume
        FROM growth g
        JOIN current_share c ON g.bank = c.bank
        {bank_filter}
        ORDER BY g.growth DESC
        {limit_clause};
    """
    df = db.query(query)
    return df.to_dicts()


###########################################################
# ✅ 5. BANK FOLLOWERS
###########################################################
async def fetch_bank_followers(platform=None):
    # followers isn't on social_data_posts (per-post data) — it lives on
    # saudi_banks.social_data, a per-bank/platform snapshot with no date
    # column, so there's no date range to filter by.
    where_clause = f"WHERE platform = '{platform}'" if platform else ""

    query = f"""
        SELECT
            brand_name AS bank,
            MAX(followers) AS followers
        FROM saudi_banks.social_data
        {where_clause}
        GROUP BY brand_name
        ORDER BY followers DESC;
    """

    df = db.query(query)
    return df.to_dicts()


###########################################################
# ✅ 6. BANKS AND PLATFORMS FILTERS
###########################################################
async def fetch_banks_and_platforms():
    query = """
        SELECT 
            ARRAY_AGG(DISTINCT brand_name ORDER BY brand_name) AS banks,
            ARRAY_AGG(DISTINCT platform ORDER BY platform) AS platforms
        FROM saudi_banks.social_data_posts;
    """
    df = db.query(query)
    return df.to_dicts()[0]


###########################################################
# SENTIMENT ANALYSIS QUERIES
###########################################################

async def fetch_avg_sentiment_by_topic(start_date=None, end_date=None):
    date_filter = date_range_clause("date::timestamp", start_date, end_date)
    query = f"""
        SELECT
            topic AS name,
            ROUND(AVG(sentiment)::numeric, 2) AS avg_sentiment,
            COUNT(*) AS mentions
        FROM saudi_banks.social_data_comments_sentiment_topic
        WHERE {date_filter}
        GROUP BY topic
        ORDER BY avg_sentiment DESC;
    """
    return db.query(query).to_dicts()


async def fetch_avg_sentiment_by_bank(start_date=None, end_date=None):
    date_filter = date_range_clause("date::timestamp", start_date, end_date)
    query = f"""
        SELECT
            bank_name_original AS name,
            ROUND(AVG(sentiment)::numeric, 2) AS avg_sentiment
        FROM saudi_banks.social_data_comments_sentiment_topic
        WHERE {date_filter}
        GROUP BY bank_name_original
        ORDER BY avg_sentiment DESC;
    """
    return db.query(query).to_dicts()


async def fetch_top_topics_by_sentiment(limit=10, start_date=None, end_date=None):
    date_filter = date_range_clause("date::timestamp", start_date, end_date)
    query = f"""
        SELECT
            topic AS name,
            ROUND(AVG(sentiment)::numeric, 2) AS avg_sentiment,
            COUNT(*) AS mentions
        FROM saudi_banks.social_data_comments_sentiment_topic
        WHERE {date_filter}
        GROUP BY topic
        ORDER BY avg_sentiment DESC
        LIMIT {limit};
    """
    return db.query(query).to_dicts()


async def fetch_top_banks_by_sentiment(limit=10, start_date=None, end_date=None):
    date_filter = date_range_clause("date::timestamp", start_date, end_date)
    query = f"""
        SELECT
            bank_name_original AS name,
            ROUND(AVG(sentiment)::numeric, 2) AS avg_sentiment,
            COUNT(*) AS mentions
        FROM saudi_banks.social_data_comments_sentiment_topic
        WHERE {date_filter}
        GROUP BY bank_name_original
        ORDER BY avg_sentiment DESC
        LIMIT {limit};
    """
    return db.query(query).to_dicts()





###########################################################
# ASSOCIATIONS QUERIES
###########################################################


def associations_filters(platform=None, start_date=None, end_date=None, associations=None, bank=None):
    filters = [f"date::timestamp >= '{start_date or '2025-01-01'}'"]
    if end_date:
        filters.append(f"date::timestamp <= '{end_date}'")
    if platform:
        filters.append(f"social_media = '{platform}'")
    if bank:
        # associations.bank_name_original stores the raw keyword form (e.g.
        # 'Saudi National Bank', not 'SNB') — reverse-map display names.
        raw = to_raw_keyword(bank).replace("'", "''")
        filters.append(f"bank_name_original = '{raw}'")
    if associations:
        escaped = [a.replace("'", "''") for a in associations]
        theme_list = "(" + ", ".join(f"'{a}'" for a in escaped) + ")"
        filters.append(f"theme IN {theme_list}")
    return "WHERE " + " AND ".join(filters)


async def fetch_top_5_associations(platform=None, start_date=None, end_date=None, associations=None, bank=None):
    where_clause = associations_filters(platform, start_date, end_date, associations, bank)
    # If specific associations were requested, return all of them rather than only the top 5
    limit_clause = "" if associations else "LIMIT 5"

    query = f"""
        SELECT
            theme AS association,
            COUNT(*) AS total_mentions
        FROM saudi_banks.associations
        {where_clause}
        GROUP BY theme
        ORDER BY total_mentions DESC
        {limit_clause};
    """
    return db.query(query).to_dicts()



async def fetch_association_distribution(platform=None, start_date=None, end_date=None, associations=None, bank=None):
    where_clause = associations_filters(platform, start_date, end_date, associations, bank)

    query = f"""
        SELECT
            theme AS association,
            COUNT(*) AS total_mentions
        FROM saudi_banks.associations
        {where_clause}
        GROUP BY theme
        ORDER BY total_mentions DESC;
    """
    return db.query(query).to_dicts()



ASSOCIATIONS_FREQUENCY_PERIOD = {
    "1m": "TO_CHAR(date_trunc('month', date::timestamp), 'YYYY-MM')",
    "3m": "TO_CHAR(date_trunc('quarter', date::timestamp), 'YYYY-\"Q\"Q')",
    "6m": """CASE 
                WHEN EXTRACT(MONTH FROM date::timestamp) <= 6 
                THEN CONCAT(EXTRACT(YEAR FROM date::timestamp), '-H1')
                ELSE CONCAT(EXTRACT(YEAR FROM date::timestamp), '-H2')
            END""",
    "1y": "TO_CHAR(date_trunc('year', date::timestamp), 'YYYY')"
}



async def fetch_top_5_associations_over_time(
    platform=None,
    frequency="1m",
    start_date=None,
    end_date=None,
    associations=None,
    bank=None,
):
    period_expr = ASSOCIATIONS_FREQUENCY_PERIOD[frequency]

    if associations:
        # Filter to the caller-provided associations (already capped at 5)
        where_clause = associations_filters(platform, start_date, end_date, associations, bank)

        query = f"""
            SELECT
                theme AS association,
                {period_expr} AS period,
                COUNT(*) AS total_mentions
            FROM saudi_banks.associations
            {where_clause}
            GROUP BY theme, period
            ORDER BY period, association;
        """
    else:
        # Default: top 5 associations by total mentions
        where_clause = associations_filters(platform, start_date, end_date, bank=bank)

        query = f"""
            WITH counts AS (
                SELECT
                    theme AS association,
                    {period_expr} AS period,
                    COUNT(*) AS total_mentions
                FROM saudi_banks.associations
                {where_clause}
                GROUP BY theme, period
            ),
            top5 AS (
                SELECT association
                FROM counts
                GROUP BY association
                ORDER BY SUM(total_mentions) DESC
                LIMIT 5
            )
            SELECT
                c.association,
                c.period,
                c.total_mentions
            FROM counts c
            WHERE c.association IN (SELECT association FROM top5)
            ORDER BY c.period, c.association;
        """

    return db.query(query).to_dicts()

