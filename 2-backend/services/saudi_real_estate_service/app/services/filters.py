from services.saudi_real_estate_service.app.utils.database import db


async def fetch_banks():
    query = """
        SELECT DISTINCT brand_name
        FROM realestate_saudi_dbh.social_data
        ORDER BY brand_name;
    """
    df = db.query(query)
    return df.to_series().to_list()


async def fetch_products():
    # No realestate_saudi_dbh equivalent of saudi_banks.search_products exists yet.
    return []


async def fetch_associations():
    # No realestate_saudi_dbh equivalent of saudi_banks.associations exists yet.
    return []


async def fetch_regions():
    # No realestate_saudi_dbh equivalent of metadata exists yet.
    return []
