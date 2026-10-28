from shared.database import db
from typing import Optional



async def fetch_themes_quadrants(country: str = "Overall"):
    query = f"""
        SELECT
            category,
            theme AS label,
            ROUND(
                (total_volume / MAX(total_volume) OVER (PARTITION BY category)) * 100,
                2
            ) AS percentage,
            ROUND(growth_rate::numeric, 4) AS growth_rate
        FROM ev.theme_growth_volume
        WHERE country = '{country}'
        ORDER BY category, percentage DESC
    """

    df = db.query(query)
    return df.to_dicts()
