import polars as pl
from shared.database import db


def sql_list(values):
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)



def build_filters_where_clause(filters: dict):
    conditions = []

    # Always exclude closed restaurants
    conditions.append("is_temporarily_closed = false")
    conditions.append("is_permanently_closed = false")

    if not filters:
        return "WHERE " + " AND ".join(conditions)

    if filters.get("cuisine"):
        values = sql_list(filters["cuisine"])
        conditions.append(f"main_category IN ({values})")

    if filters.get("horeca_type"):
        values = sql_list(filters["horeca_type"])
        conditions.append(f"horeca_type IN ({values})")

    if filters.get("price_range"):
        values = sql_list(filters["price_range"])
        conditions.append(f"price_range IN ({values})")

    if filters.get("rating"):
        min_rating = filters["rating"].get("min")
        max_rating = filters["rating"].get("max")

        if min_rating is not None:
            conditions.append(f"rating >= {float(min_rating)}")

        if max_rating is not None:
            conditions.append(f"rating <= {float(max_rating)}")

    return "WHERE " + " AND ".join(conditions)



# ===============================
# RICE KPI ANALYSIS
# ===============================

async def fetch_rice_kpis(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        COUNT(*) AS total_rice_items,
        COUNT(DISTINCT m.place_id) AS restaurants_with_rice,
        ROUND(
            AVG(
                substring(m."price_SAR" from '[0-9]+(\\.[0-9]+)?')::numeric
            ),
            2
        ) AS avg_rice_price
    FROM horeka.menu m
    JOIN filtered_restaurants r
        ON m.place_id = r.place_id
    WHERE m.is_rice_item = true
    """

    df = db.query(query)

    return df.to_dicts()[0]



# ===============================
# RICE PRICE DISTRIBUTION
# ===============================

async def fetch_rice_price_distribution(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        m."price_SAR" AS price,
        COUNT(*) AS item_count
    FROM horeka.menu m
    JOIN filtered_restaurants r
        ON m.place_id = r.place_id
    WHERE m.is_rice_item = true
    GROUP BY m."price_SAR"
    ORDER BY m."price_SAR"
    """

    df = db.query(query)

    return df.to_dicts()


# ===============================
# TOP RICE DISHES
# ===============================

async def fetch_top_rice_dishes(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        m.item_name,
        COUNT(*) AS restaurant_count,
        ROUND(
            AVG(
                substring(m."price_SAR" from '[0-9]+(\\.[0-9]+)?')::numeric
            ),
            2
        ) AS avg_price
    FROM horeka.menu m
    JOIN filtered_restaurants r
        ON m.place_id = r.place_id
    WHERE m.is_rice_item = true
    GROUP BY m.item_name
    ORDER BY restaurant_count DESC
    LIMIT 20
    """

    df = db.query(query)

    return df.to_dicts()


# ===============================
# RICE BY CUISINE
# ===============================

async def fetch_rice_by_cuisine(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id, main_category
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        r.main_category AS cuisine,
        COUNT(m.item_id) AS rice_items,
        ROUND(
            AVG(
                substring(m."price_SAR" from '[0-9]+(\\.[0-9]+)?')::numeric
            ),
            2
        ) AS avg_price
    FROM horeka.menu m
    JOIN filtered_restaurants r
        ON m.place_id = r.place_id
    WHERE m.is_rice_item = true
    GROUP BY r.main_category
    ORDER BY rice_items DESC
    """

    df = db.query(query)

    return df.to_dicts()


# ===============================
# RICE VS NON RICE MENU MIX
# ===============================

async def fetch_rice_menu_mix(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    ),
    counts AS (
        SELECT
            COUNT(*) FILTER (WHERE m.is_rice_item = true) AS rice_items,
            COUNT(*) FILTER (WHERE m.is_rice_item = false) AS non_rice_items,
            COUNT(*) AS total_items
        FROM horeka.menu m
        JOIN filtered_restaurants r
            ON m.place_id = r.place_id
    )
    SELECT
        'Rice Items' AS name,
        rice_items AS count,
        ROUND((rice_items::numeric / NULLIF(total_items,0)) * 100, 2) AS percentage
    FROM counts

    UNION ALL

    SELECT
        'Non Rice Items' AS name,
        non_rice_items AS count,
        ROUND((non_rice_items::numeric / NULLIF(total_items,0)) * 100, 2) AS percentage
    FROM counts
    """

    df = db.query(query)

    return df.to_dicts()

