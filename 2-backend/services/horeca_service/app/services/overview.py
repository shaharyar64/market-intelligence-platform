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




async def fetch_kpis(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT
            place_id,
            total_reviews,
            rating
        FROM horeka.restaurants
        {where_clause}
    ),

    menu_stats AS (
        SELECT
            m.place_id,
            COUNT(*) AS item_count,
            AVG(price_value) AS avg_price_per_restaurant
        FROM (
            SELECT
                place_id,
                (regexp_match("price_SAR", '[0-9]+(\\.[0-9]+)?'))[1]::numeric AS price_value
            FROM horeka.menu
            WHERE "price_SAR" ~ '[0-9]'
        ) m
        JOIN filtered_restaurants r
            ON m.place_id = r.place_id
        GROUP BY m.place_id
    )

    SELECT
        COUNT(DISTINCT r.place_id) AS total_restaurants,
        COALESCE(SUM(r.total_reviews), 0) AS total_reviews,
        ROUND(AVG(r.rating)::numeric, 2) AS avg_rating,
        ROUND(AVG(ms.avg_price_per_restaurant), 2) AS average_price,
        ROUND(AVG(ms.item_count), 2) AS average_menu_items
    FROM filtered_restaurants r
    LEFT JOIN menu_stats ms
        ON r.place_id = ms.place_id
    """

    df = db.query(query)
    return df.to_dicts()[0]





async def fetch_horeca_split(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    SELECT
        horeca_type,
        COUNT(DISTINCT place_id) AS count,
        ROUND(
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (),
            2
        ) AS percentage
    FROM horeka.restaurants
    {where_clause}
    GROUP BY horeca_type
    ORDER BY percentage DESC
    """

    df = db.query(query)
    return df.to_dicts()




async def fetch_rating_distribution(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_places AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    ),
    dedup AS (
        SELECT DISTINCT ON (rd.place_id)
            rd.place_id,
            rd.rating_1,
            rd.rating_2,
            rd.rating_3,
            rd.rating_4,
            rd.rating_5
        FROM horeka.rating_distribution rd
        JOIN filtered_places fp ON rd.place_id = fp.place_id
        ORDER BY rd.place_id
    ),
    totals AS (
        SELECT
            SUM(rating_1) AS r1,
            SUM(rating_2) AS r2,
            SUM(rating_3) AS r3,
            SUM(rating_4) AS r4,
            SUM(rating_5) AS r5
        FROM dedup
    ),
    unpivot AS (
        SELECT 1 AS rating, r1 AS count FROM totals
        UNION ALL SELECT 2, r2 FROM totals
        UNION ALL SELECT 3, r3 FROM totals
        UNION ALL SELECT 4, r4 FROM totals
        UNION ALL SELECT 5, r5 FROM totals
    ),
    grand_total AS (
        SELECT SUM(count) AS total FROM unpivot
    )
    SELECT
        u.rating,
        u.count,
        ROUND(u.count::numeric / NULLIF(g.total, 0) * 100, 2) AS percentage
    FROM unpivot u
    CROSS JOIN grand_total g
    ORDER BY u.rating;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_popular_times(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    ),
    dedup AS (
        SELECT DISTINCT ON (pt.place_id, pt.day, pt.hour_of_day)
            pt.place_id,
            pt.day,
            pt.hour_of_day,
            pt.popularity_percentage
        FROM horeka.popular_times pt
        JOIN filtered_restaurants r
            ON pt.place_id = r.place_id
        ORDER BY pt.place_id, pt.day, pt.hour_of_day
    )
    SELECT
        day AS y,
        CASE
            WHEN hour_of_day = 0 THEN 24
            ELSE hour_of_day
        END AS x,
        ROUND(AVG(popularity_percentage)::numeric, 0) AS value
    FROM dedup
    GROUP BY day, x
    ORDER BY
        CASE day
            WHEN 'Monday' THEN 1
            WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5
            WHEN 'Saturday' THEN 6
            WHEN 'Sunday' THEN 7
        END,
        x
    """

    df = db.query(query)
    return df.to_dicts()



async def fetch_filters():
    query = """
        SELECT
            ARRAY_AGG(DISTINCT main_category)
                FILTER (WHERE main_category IS NOT NULL) AS main_category,
            ARRAY_AGG(DISTINCT horeca_type)
                FILTER (WHERE horeca_type IS NOT NULL) AS horeca_type,
            ARRAY_AGG(DISTINCT price_range)
                FILTER (WHERE price_range IS NOT NULL) AS price_range,
            FLOOR(MIN(rating)) AS min_rating,
            CEIL(MAX(rating)) AS max_rating
        FROM horeka.restaurants
        WHERE
            is_temporarily_closed = false
        AND is_permanently_closed = false
    """

    df = db.query(query)
    row = df.to_dicts()[0]

    return {
        "cuisine": sorted(row["main_category"] or []),
        "horeca_type": sorted(row["horeca_type"] or []),
        "price_range": sorted(row["price_range"] or []),
        "rating": {
            "min": row["min_rating"],   # slider start
            "max": row["max_rating"]    # slider end
        }
    }