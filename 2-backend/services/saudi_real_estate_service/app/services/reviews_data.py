from services.saudi_real_estate_service.app.utils.database import db

# realestate_saudi_dbh.google_reviews has no computed `sentiment` column —
# AVG(rating) is used as a proxy, labeled avg_sentiment to keep the same
# response shape as banking's equivalent.
#
# realestate_saudi_dbh.metadata (region lookup) doesn't exist yet, so `region`
# is accepted on every function below for API compatibility but has nothing
# to filter against.


def escape_sql(value: str) -> str:
    return value.replace("'", "''")


async def fetch_reviews_per_bank(region: str | None = None):
    query = """
        SELECT title AS bank, COUNT(*) AS ratings
        FROM realestate_saudi_dbh.google_reviews
        GROUP BY bank
        ORDER BY ratings DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_top_rated_banks(region: str | None = None):
    query = """
        SELECT
            title AS bank,
            ROUND(AVG(rating)::numeric, 2) AS avg_rating
        FROM realestate_saudi_dbh.google_reviews
        WHERE rating IS NOT NULL
        GROUP BY bank
        ORDER BY avg_rating DESC, COUNT(*) DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_rated_banks(rating: int, region: str | None = None):
    query = f"""
        SELECT
            title AS bank,
            COUNT(*) AS total_ratings
        FROM realestate_saudi_dbh.google_reviews
        WHERE rating = {int(rating)}
        GROUP BY bank
        ORDER BY total_ratings DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_avg_sentiment_by_bank(region: str | None = None):
    query = """
        SELECT
            title AS bank,
            ROUND(AVG(rating)::numeric, 2) AS avg_sentiment,
            COUNT(*) FILTER (WHERE rating = 1) AS rating_1,
            COUNT(*) FILTER (WHERE rating = 2) AS rating_2,
            COUNT(*) FILTER (WHERE rating = 3) AS rating_3,
            COUNT(*) FILTER (WHERE rating = 4) AS rating_4,
            COUNT(*) FILTER (WHERE rating = 5) AS rating_5
        FROM realestate_saudi_dbh.google_reviews
        WHERE rating IS NOT NULL
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
        FROM realestate_saudi_dbh.google_reviews
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
        FROM realestate_saudi_dbh.google_reviews
        WHERE rating IS NOT NULL AND topic IS NOT NULL
        {bank_filter}
        GROUP BY topic
        ORDER BY avg_rating DESC
    """
    df = db.query(query)
    return df.to_dicts()
