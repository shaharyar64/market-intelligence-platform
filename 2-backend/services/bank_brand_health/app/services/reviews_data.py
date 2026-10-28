from services.bank_brand_health.app.utils.database import db
from services.bank_brand_health.app.services.search_data import to_raw_keyword, BANK_NAME_MAP
import polars as pl


# Excluded from all bank-related review results.
EXCLUDED_REVIEW_BANKS = ("barq",)
EXCLUDED_REVIEW_BANKS_CLAUSE = "title NOT IN (" + ", ".join(f"'{b}'" for b in EXCLUDED_REVIEW_BANKS) + ")"


def review_title_matches(bank: str) -> str:
    """Build a `title IN (...)` value list for a caller-provided bank name.

    google_reviews / google_reviews_topic_sentiment mostly store the display
    name (e.g. 'SNB', 'Al Rajhi Bank') but at least one bank ('Al Bilad Bank')
    is stored in its raw keyword form, so match on both the display and raw
    forms to be safe regardless of which one the caller sends.
    """
    candidates = {bank, to_raw_keyword(bank), BANK_NAME_MAP.get(bank, bank)}
    escaped = [c.replace("'", "''") for c in candidates]
    return "(" + ", ".join(f"'{c}'" for c in escaped) + ")"


async def fetch_reviews_per_bank():
    query = f"""
    SELECT title AS bank, COUNT(*) AS ratings
    FROM google_reviews
    WHERE {EXCLUDED_REVIEW_BANKS_CLAUSE}
    GROUP BY bank
    ORDER BY ratings DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_top_rated_banks():
    query = f"""
    SELECT
        title AS bank,
        ROUND(AVG(rating)::numeric, 2) AS avg_rating
    FROM google_reviews
    WHERE rating IS NOT NULL
      AND {EXCLUDED_REVIEW_BANKS_CLAUSE}
    GROUP BY bank
    ORDER BY avg_rating DESC, COUNT(*) DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_rated_banks(rating: int):
    query = f"""
    SELECT
        title AS bank,
        COUNT(*) AS total_ratings
    FROM google_reviews
    WHERE rating = {rating}
      AND {EXCLUDED_REVIEW_BANKS_CLAUSE}
    GROUP BY bank
    ORDER BY total_ratings DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_avg_sentiment_by_bank():
    query = """
        SELECT 
            title AS bank,
            ROUND(AVG(sentiment)::numeric, 2) AS avg_sentiment,

            COUNT(*) FILTER (WHERE rating = 1) AS rating_1,
            COUNT(*) FILTER (WHERE rating = 2) AS rating_2,
            COUNT(*) FILTER (WHERE rating = 3) AS rating_3,
            COUNT(*) FILTER (WHERE rating = 4) AS rating_4,
            COUNT(*) FILTER (WHERE rating = 5) AS rating_5

        FROM saudi_banks.google_reviews_topic_sentiment
        WHERE sentiment IS NOT NULL
        GROUP BY bank
        ORDER BY bank;
    """
    df = db.query(query)
    return df.to_dicts()



async def fetch_review_topics_distribution(bank: str | None = None):
    bank_filter = f"AND title IN {review_title_matches(bank)}" if bank else ""
    query = f"""
        SELECT
            topic,
            COUNT(*) AS review_count
        FROM saudi_banks.google_reviews_topic_sentiment
        WHERE topic IS NOT NULL
        {bank_filter}
        GROUP BY topic
        ORDER BY review_count DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_avg_rating_by_topic(bank: str | None = None):
    bank_filter = f"AND title IN {review_title_matches(bank)}" if bank else ""
    query = f"""
        SELECT
            topic,
            ROUND(AVG(rating)::numeric, 2) AS avg_rating,
            COUNT(*) AS review_count
        FROM saudi_banks.google_reviews_topic_sentiment
        WHERE rating IS NOT NULL AND topic IS NOT NULL
        {bank_filter}
        GROUP BY topic
        ORDER BY avg_rating DESC
    """
    df = db.query(query)
    return df.to_dicts()