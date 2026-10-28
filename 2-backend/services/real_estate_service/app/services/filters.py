from services.real_estate_service.app.utils.database import db


async def fetch_banks():
    query = """
        SELECT DISTINCT brand_name
        FROM realestate_dbh.social_data
        ORDER BY brand_name;
    """
    df = db.query(query)
    return df.to_series().to_list()


async def fetch_products():
    # No realestate_dbh equivalent of saudi_banks.search_products exists yet.
    return []


async def fetch_associations():
    # No realestate_dbh equivalent of saudi_banks.associations exists yet.
    return []


async def fetch_regions():
    query = """
        SELECT DISTINCT "Region"
        FROM realestate_dbh.metadata
        ORDER BY "Region";
    """
    df = db.query(query)
    return df.to_series().to_list()
