from shared.database import db
from typing import Optional



async def get_kpis(cluster=None, sub_cluster=None, zone=None, country=None, category=None):

    conditions = []

    if cluster:
        conditions.append(f"cluster = '{cluster}'")

    if sub_cluster:
        conditions.append(f"\"sub_cluster\" = '{sub_cluster}'")

    if zone:
        conditions.append(f"area = '{zone}'")

    if country:
        conditions.append(f"country_code = '{country}'")
    
    if category:
        conditions.append(f"category = '{category}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COUNT(DISTINCT cluster) AS total_clusters,
            COUNT(DISTINCT "sub_cluster") AS total_sub_clusters,
            COUNT(DISTINCT area) AS total_zones,
            COUNT(DISTINCT category) AS total_categories,
            SUM(reviews) AS total_reviews,

            ROUND(
                CASE 
                    WHEN SUM(star_1 + star_2 + star_3 + star_4 + star_5) = 0 THEN 0
                    ELSE
                        (
                            SUM(
                                1*star_1 +
                                2*star_2 +
                                3*star_3 +
                                4*star_4 +
                                5*star_5
                            )
                        )::numeric
                        /
                        SUM(star_1 + star_2 + star_3 + star_4 + star_5)
                END
            , 2) AS average_rating,

            COUNT(DISTINCT country_code) AS total_countries,

            (
                SELECT SUM(population)
                FROM (
                    SELECT DISTINCT area, population
                    FROM bankspatial.banks
                    {where_clause}
                ) z
            ) AS total_population

        FROM bankspatial.banks
        {where_clause}
    """

    return db.query(sql).to_dicts()[0]


async def get_categories(cluster=None, sub_cluster=None, zone=None, country=None, category=None):

    conditions = []

    if cluster:
        conditions.append(f"cluster = '{cluster}'")

    if sub_cluster:
        conditions.append(f"\"sub_cluster\" = '{sub_cluster}'")

    if zone:
        conditions.append(f"area = '{zone}'")

    if country:
        conditions.append(f"country_code = '{country}'")
    
    if category:
        conditions.append(f"category = '{category}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT 
            category AS name, 
            COUNT(*) AS value
        FROM bankspatial.banks
        {where_clause}
        GROUP BY category
    """

    return db.query(sql).to_dicts()

async def get_rating_distribution(cluster=None, sub_cluster=None, zone=None, country=None, category=None):

    conditions = []

    if cluster:
        conditions.append(f"cluster = '{cluster}'")

    if sub_cluster:
        conditions.append(f"\"sub_cluster\" = '{sub_cluster}'")

    if zone:
        conditions.append(f"area = '{zone}'")

    if country:
        conditions.append(f"country_code = '{country}'")
    
    if category:
        conditions.append(f"category = '{category}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            SUM(star_1) AS star_1,
            SUM(star_2) AS star_2,
            SUM(star_3) AS star_3,
            SUM(star_4) AS star_4,
            SUM(star_5) AS star_5,

            SUM(star_1 + star_2 + star_3 + star_4 + star_5) AS total_ratings
        FROM bankspatial.banks
        {where_clause}
    """

    result = db.query(sql).to_dicts()[0]

    total = result["total_ratings"] or 0

    # Prepare pie chart structure
    pie_data = [
        {
            "name": "1 Star",
            # "count": result["star_1"] or 0,
            "value": round(((result["star_1"] or 0) / total) * 100, 2) if total else 0
        },
        {
            "name": "2 Stars",
            # "count": result["star_2"] or 0,
            "value": round(((result["star_2"] or 0) / total) * 100, 2) if total else 0
        },
        {
            "name": "3 Stars",
            # "count": result["star_3"] or 0,
            "value": round(((result["star_3"] or 0) / total) * 100, 2) if total else 0
        },
        {
            "name": "4 Stars",
            # "count": result["star_4"] or 0,
            "value": round(((result["star_4"] or 0) / total) * 100, 2) if total else 0
        },
        {
            "name": "5 Stars",
            # "count": result["star_5"] or 0,
            "value": round(((result["star_5"] or 0) / total) * 100, 2) if total else 0
        }
    ]

    return pie_data


async def get_network_strength_by_branches(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):

    conditions = ["category = 'Bank'"]  # ✅ Always filter only Banks

    if cluster:
        conditions.append(f"cluster = '{cluster}'")

    if sub_cluster:
        conditions.append(f"\"sub_cluster\" = '{sub_cluster}'")

    if zone:
        conditions.append(f"area = '{zone}'")

    if country:
        conditions.append(f"country_code = '{country}'")

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COALESCE(name, title) AS bank_name,
            COUNT(*) AS total_branches,
            ROUND(
                COUNT(*) * 100.0 /
                NULLIF(SUM(COUNT(*)) OVER (), 0),
                2
            ) AS branch_share_percent
        FROM bankspatial.banks
        {where_clause}
        GROUP BY COALESCE(name, title)
        ORDER BY total_branches DESC
    """

    result = db.query(sql).to_dicts()

    return [
        {
            "name": row["bank_name"],
            "value": row["total_branches"],
            "branch_share_percent": row["branch_share_percent"]
        }
        for row in result
    ]


async def get_filters():
    sql = f"""
        SELECT
            ARRAY_AGG(DISTINCT cluster) AS clusters,
            ARRAY_AGG(DISTINCT "sub_cluster") AS sub_clusters,
            ARRAY_AGG(DISTINCT area) AS zones,
            ARRAY_AGG(DISTINCT country_code) AS countries,
            ARRAY_AGG(DISTINCT category) AS categories
        FROM bankspatial.banks
    """

    return db.query(sql).to_dicts()[0]


