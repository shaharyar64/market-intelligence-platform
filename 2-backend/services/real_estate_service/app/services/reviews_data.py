from services.real_estate_service.app.utils.database import db

# realestate_dbh.google_reviews has no computed `sentiment` column (unlike banking's
# saudi_banks.google_reviews_topic_sentiment) — AVG(rating) is used as a proxy,
# labeled avg_sentiment to keep the same response shape.

# realestate_dbh.metadata (Developer -> Region) matches google_reviews.title exactly
# for all 22 developers, so the region filter here is a clean join with no gaps —
# unlike search-data/social-data, where developer naming doesn't line up as cleanly.


def escape_sql(value: str) -> str:
    return value.replace("'", "''")


def region_join(region: str | None) -> tuple[str, str]:
    """Returns (join_clause, where_clause) — both empty when no region filter."""
    if not region:
        return "", ""
    join_clause = 'JOIN realestate_dbh.metadata m ON r.title = m."Developer"'
    where_clause = f"AND m.\"Region\" = '{escape_sql(region)}'"
    return join_clause, where_clause


async def fetch_reviews_per_bank(region: str | None = None):
    join_clause, region_filter = region_join(region)
    query = f"""
    SELECT r.title AS bank, COUNT(*) AS ratings
    FROM realestate_dbh.google_reviews r
    {join_clause}
    WHERE 1=1
    {region_filter}
    GROUP BY bank
    ORDER BY ratings DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_top_rated_banks(region: str | None = None):
    join_clause, region_filter = region_join(region)
    query = f"""
    SELECT
        r.title AS bank,
        ROUND(AVG(r.rating)::numeric, 2) AS avg_rating
    FROM realestate_dbh.google_reviews r
    {join_clause}
    WHERE r.rating IS NOT NULL
    {region_filter}
    GROUP BY bank
    ORDER BY avg_rating DESC, COUNT(*) DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_rated_banks(rating: int, region: str | None = None):
    join_clause, region_filter = region_join(region)
    query = f"""
    SELECT
        r.title AS bank,
        COUNT(*) AS total_ratings
    FROM realestate_dbh.google_reviews r
    {join_clause}
    WHERE r.rating = {int(rating)}
    {region_filter}
    GROUP BY bank
    ORDER BY total_ratings DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_avg_sentiment_by_bank(region: str | None = None):
    join_clause, region_filter = region_join(region)
    query = f"""
        SELECT
            r.title AS bank,
            ROUND(AVG(r.rating)::numeric, 2) AS avg_sentiment,

            COUNT(*) FILTER (WHERE r.rating = 1) AS rating_1,
            COUNT(*) FILTER (WHERE r.rating = 2) AS rating_2,
            COUNT(*) FILTER (WHERE r.rating = 3) AS rating_3,
            COUNT(*) FILTER (WHERE r.rating = 4) AS rating_4,
            COUNT(*) FILTER (WHERE r.rating = 5) AS rating_5

        FROM realestate_dbh.google_reviews r
        {join_clause}
        WHERE r.rating IS NOT NULL
        {region_filter}
        GROUP BY bank
        ORDER BY bank;
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_review_topics_distribution(bank: str | None = None):
    bank_filter = f"AND title = '{escape_sql(bank)}'" if bank else ""
    query = f"""
        SELECT
            topic,
            COUNT(*) AS review_count
        FROM realestate_dbh.google_reviews
        WHERE topic IS NOT NULL
        {bank_filter}
        GROUP BY topic
        ORDER BY review_count DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_avg_rating_by_topic(bank: str | None = None):
    bank_filter = f"AND title = '{escape_sql(bank)}'" if bank else ""
    query = f"""
        SELECT
            topic,
            ROUND(AVG(rating)::numeric, 2) AS avg_rating,
            COUNT(*) AS review_count
        FROM realestate_dbh.google_reviews
        WHERE rating IS NOT NULL AND topic IS NOT NULL
        {bank_filter}
        GROUP BY topic
        ORDER BY avg_rating DESC
    """
    df = db.query(query)
    return df.to_dicts()
