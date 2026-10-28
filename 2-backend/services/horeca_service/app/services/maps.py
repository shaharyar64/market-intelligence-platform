import polars as pl
from shared.database import db
from typing import Optional



async def fetch_restaurants(
    cuisine: Optional[str] = None,
    horeca_type: Optional[str] = None,
    price_range: Optional[str] = None,
    rating_min: Optional[float] = None,
    rating_max: Optional[float] = None
):
    query = """
        SELECT
            latitude,
            longitude,
            name,
            main_category AS cuisine,
            rating,
            price_range,
            horeca_type,
            total_reviews,
            place_id
        FROM horeka.restaurants
        WHERE
            is_temporarily_closed = false
        AND is_permanently_closed = false
    """

    # IMPORTANT: build filters as raw SQL strings
    if cuisine:
        query += f" AND main_category = '{cuisine}'"

    if horeca_type:
        query += f" AND horeca_type = '{horeca_type}'"

    if price_range:
        query += f" AND price_range = '{price_range}'"

    if rating_min is not None:
        query += f" AND rating >= {rating_min}"

    if rating_max is not None:
        query += f" AND rating <= {rating_max}"

    df = db.query(query)

    df = df.with_columns(
        (
            pl.lit("https://www.google.com/maps/place/?q=place_id:")
            + pl.col("place_id")
        ).alias("google_maps_url")
    )

    return df.to_dicts()

