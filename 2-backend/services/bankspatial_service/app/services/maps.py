from shared.database import db
from typing import Optional



async def fetch_map_data(cluster=None, sub_cluster=None, zone=None, country=None, category=None):

    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")

    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")

    if zone:
        conditions.append(f"b.area = '{zone}'")

    if country:
        conditions.append(f"b.country_code = '{country}'")
    
    if category:
        conditions.append(f"b.category = '{category}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            b.title,
            b.category,
            b.latitude,
            b.longitude,
            b.cluster,
            b.sub_cluster,
            b.area AS zone,
            b.country_code,
            b.affluence_tier,
            b.urban_lifecycle_stage,
            b.population,
            b.state2 AS state,
            b.link,
            COUNT(r."reviewId") AS total_reviews,
            ROUND(AVG(r.sentiment::numeric), 2) AS sentiment_score
        FROM bankspatial.banks b
        LEFT JOIN bankspatial.reviews r 
            ON r."placeId" = b.place_id
        {where_clause}
        GROUP BY
            b.title,
            b.category,
            b.latitude,
            b.longitude,
            b.cluster,
            b.sub_cluster,
            b.area,
            b.country_code,
            b.affluence_tier,
            b.urban_lifecycle_stage,
            b.population,
            b.state2,
            b.link
    """

    return db.query(sql).to_dicts()