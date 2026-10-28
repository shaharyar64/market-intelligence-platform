from services.uae_bank_brand_health.app.utils.database import db
from services.uae_bank_brand_health.app.services.search_data import BANK_NAME_MAP, EXCLUDED_BANKS_CLAUSE


async def fetch_banks():
    query = f"""
        SELECT DISTINCT keyword
        FROM google_trends
        WHERE project = 'uae_banks_dbh'
          AND {EXCLUDED_BANKS_CLAUSE}
        ORDER BY keyword;
    """
    df = db.query(query)
    keywords = df.to_series().to_list()
    return sorted({BANK_NAME_MAP.get(k, k) for k in keywords})


async def fetch_products():
    query = """
        SELECT DISTINCT category
        FROM uae_banks_dbh.search_products
        WHERE category IS NOT NULL
        ORDER BY category;
    """
    df = db.query(query)
    return df.to_series().to_list()


async def fetch_associations():
    query = """
        SELECT DISTINCT theme
        FROM uae_banks_dbh.social_data_posts
        WHERE theme IS NOT NULL
        ORDER BY theme;
    """
    df = db.query(query)
    return df.to_series().to_list()
