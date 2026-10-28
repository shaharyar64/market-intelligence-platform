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


async def  fetch_restaurants(page: int, page_size: int, filters: dict = None):
    offset = (page - 1) * page_size
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT *
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        r.name,
        r.horeca_type,
        r.main_category,
        a.city,
        r.price_range AS price_level,
        r.rating,
        r.total_reviews,
        r.place_id
    FROM filtered_restaurants r
    JOIN horeka.addresses a ON r.place_id = a.place_id
    ORDER BY r.rating DESC NULLS LAST
    LIMIT {page_size}
    OFFSET {offset}
    """

    df = db.query(query)

    df = df.with_columns(
        (
            pl.lit("https://www.google.com/maps/place/?q=place_id:")
            + pl.col("place_id")
        ).alias("google_maps_url")
    )

    return {
        "page": page,
        "page_size": page_size,
        "data": df.to_dicts(),
    }



async def fetch_menu(page: int, page_size: int, filters: dict = None):
    offset = (page - 1) * page_size
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        m.item_name,
        m.price,
        m.place_id
    FROM horeka.menu m
    JOIN filtered_restaurants r
        ON m.place_id = r.place_id
    LIMIT {page_size}
    OFFSET {offset}
    """

    df = db.query(query)

    return {
        "page": page,
        "page_size": page_size,
        "data": df.to_dicts(),
    }



async def fetch_review_topics(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    )
    SELECT
        rv.topic_1 AS name,
        COUNT(*) AS value
    FROM horeka.reviews rv
    JOIN filtered_restaurants r
        ON rv.place_id = r.place_id
    WHERE rv.topic_1 IS NOT NULL
    GROUP BY rv.topic_1
    ORDER BY value DESC
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top_rated_restaurants(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT *
        FROM horeka.restaurants
        {where_clause}
    )

    SELECT * FROM (
        SELECT
            'high' AS type,
            r.name,
            r.rating,
            r.total_reviews,
            r.place_id
        FROM filtered_restaurants r
        WHERE r.rating IS NOT NULL
        AND r.rating >= 1
        AND r.total_reviews > 0
        ORDER BY r.rating DESC, r.total_reviews DESC
        LIMIT 10
    ) high_rated

    UNION ALL

    SELECT * FROM (
        SELECT
            'low' AS type,
            r.name,
            r.rating,
            r.total_reviews,
            r.place_id
        FROM filtered_restaurants r
        WHERE r.rating IS NOT NULL
        AND r.rating >= 1
        AND r.total_reviews > 0
        ORDER BY r.rating ASC, r.total_reviews DESC
        LIMIT 10
    ) low_rated
    """

    df = db.query(query)

    df = df.with_columns(
        (
            pl.lit("https://www.google.com/maps/place/?q=place_id:")
            + pl.col("place_id")
        ).alias("google_maps_url")
    )

    high = df.filter(pl.col("type") == "high").drop("type").to_dicts()
    low = df.filter(pl.col("type") == "low").drop("type").to_dicts()

    return {
        "top_high_rated": high,
        "top_low_rated": low,
    }


async def fetch_review_kpis(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    )

    SELECT
        COUNT(*) AS total_reviews,

        COUNT(*) FILTER (WHERE rv.rating >= 4) AS positive_reviews,

        COUNT(*) FILTER (WHERE rv.rating <= 2) AS negative_reviews,

        ROUND(AVG(rv.rating)::numeric, 2) AS avg_rating

    FROM horeka.reviews rv
    JOIN filtered_restaurants r
        ON rv.place_id = r.place_id
    WHERE rv.rating IS NOT NULL
    """

    df = db.query(query)
    return df.to_dicts()[0]


async def fetch_review_sentiment_distribution(filters: dict = None):
    where_clause = build_filters_where_clause(filters)

    query = f"""
    WITH filtered_restaurants AS (
        SELECT place_id
        FROM horeka.restaurants
        {where_clause}
    ),

    sentiment_counts AS (
        SELECT
            COUNT(*) AS total_reviews,

            COUNT(*) FILTER (WHERE rating = 5) AS very_positive,
            COUNT(*) FILTER (WHERE rating = 4) AS positive,
            COUNT(*) FILTER (WHERE rating = 3) AS neutral,
            COUNT(*) FILTER (WHERE rating = 2) AS negative,
            COUNT(*) FILTER (WHERE rating = 1) AS very_negative

        FROM horeka.reviews rv
        JOIN filtered_restaurants r
            ON rv.place_id = r.place_id
        WHERE rv.rating IS NOT NULL
    )

    SELECT
        total_reviews,

        ROUND(100.0 * very_positive / NULLIF(total_reviews,0),2) AS very_positive,
        ROUND(100.0 * positive / NULLIF(total_reviews,0),2) AS positive,
        ROUND(100.0 * neutral / NULLIF(total_reviews,0),2) AS neutral,
        ROUND(100.0 * negative / NULLIF(total_reviews,0),2) AS negative,
        ROUND(100.0 * very_negative / NULLIF(total_reviews,0),2) AS very_negative

    FROM sentiment_counts
    """

    df = db.query(query)
    return df.to_dicts()[0]



async def fetch_restaurant_names():
    
    query = """
    SELECT
        name,
        place_id
    FROM horeka.restaurants
    WHERE
        is_temporarily_closed = false
        AND is_permanently_closed = false
        AND name IS NOT NULL
    ORDER BY name
    """

    df = db.query(query)

    return df.to_dicts()


async def fetch_restaurant_details(place_id: str, filters: dict = None):

    where_clause = build_filters_where_clause(filters)

    if where_clause:
        where_clause += f" AND r.place_id = '{place_id}'"
    else:
        where_clause = f"WHERE r.place_id = '{place_id}'"

    # =====================================
    # QUERY 1 → RESTAURANT + REVIEW KPIs
    # =====================================

    restaurant_query = f"""
    WITH restaurant AS (
        SELECT
            r.place_id,
            r.name,
            r.horeca_type,
            r.main_category,
            r.price_range,
            r.rating,
            r.total_reviews,
            r.latitude,
            r.longitude,
            a.city
        FROM horeka.restaurants r
        JOIN horeka.addresses a
            ON r.place_id = a.place_id
        {where_clause}
    ),
    review_kpis AS (
        SELECT
            COUNT(*) AS total_reviews,
            COUNT(*) FILTER (WHERE rating >= 4) AS positive_reviews,
            COUNT(*) FILTER (WHERE rating <= 2) AS negative_reviews,
            ROUND(AVG(rating)::numeric,2) AS avg_rating
        FROM horeka.reviews
        WHERE place_id = '{place_id}'
        AND rating IS NOT NULL
    )
    SELECT
        r.*,
        k.total_reviews AS review_total,
        k.positive_reviews,
        k.negative_reviews,
        k.avg_rating
    FROM restaurant r
    CROSS JOIN review_kpis k
    """

    restaurant_df = db.query(restaurant_query)

    if restaurant_df.height == 0:
        return None

    restaurant = restaurant_df.to_dicts()[0]

    restaurant["google_maps_url"] = (
        "https://www.google.com/maps/place/?q=place_id:" + place_id
    )

    # =====================================
    # QUERY 2 → MENU + REVIEW TOPICS
    # =====================================

    menu_topics_query = f"""
    (
    SELECT
        'menu' AS type,
        item_name AS name,
        "price_SAR" AS price,
        image,
        NULL AS value
    FROM horeka.menu
    WHERE place_id = '{place_id}'
    LIMIT 100
    )

    UNION ALL

    SELECT
        'topic',
        topic_1,
        NULL,
        NULL,
        COUNT(*)::text
    FROM horeka.reviews
    WHERE place_id = '{place_id}'
    AND topic_1 IS NOT NULL
    GROUP BY topic_1
    """

    menu_topics_df = db.query(menu_topics_query)

    menu = []
    topics = []

    for row in menu_topics_df.to_dicts():

        if row["type"] == "menu":
            menu.append({
                "item_name": row["name"],
                "price_SAR": row["price"],
                "image": row["image"]
            })

        else:
            topics.append({
                "name": row["name"],
                "value": int(row["value"])
            })

    # =====================================
    # QUERY 3 → RATING DISTRIBUTION + POPULAR TIMES
    # =====================================

    analytics_query = f"""
    SELECT
        'rating' AS type,
        rating,
        count,
        percentage,
        NULL AS day,
        NULL AS hour,
        NULL AS popularity
    FROM (
        WITH rating_data AS (
            SELECT rating_1, rating_2, rating_3, rating_4, rating_5
            FROM horeka.rating_distribution
            WHERE place_id = '{place_id}'
        ),
        unpivot AS (
            SELECT 1 AS rating, rating_1 AS count FROM rating_data
            UNION ALL SELECT 2, rating_2 FROM rating_data
            UNION ALL SELECT 3, rating_3 FROM rating_data
            UNION ALL SELECT 4, rating_4 FROM rating_data
            UNION ALL SELECT 5, rating_5 FROM rating_data
        ),
        total AS (SELECT SUM(count) AS total FROM unpivot)
        SELECT
            rating,
            count,
            ROUND(count::numeric / NULLIF(total.total,0) * 100,2) AS percentage
        FROM unpivot, total
    ) r

    UNION ALL

    SELECT
        'popular',
        NULL,
        NULL,
        NULL,
        day,
        hour_of_day,
        popularity_percentage
    FROM horeka.popular_times
    WHERE place_id = '{place_id}'
    """

    analytics_df = db.query(analytics_query)

    rating_distribution = []
    popular_times = []

    for row in analytics_df.to_dicts():

        if row["type"] == "rating":
            rating_distribution.append({
                "rating": row["rating"],
                "count": row["count"],
                "percentage": row["percentage"]
            })

        else:
            popular_times.append({
                "y": row["day"],
                "x": row["hour"],
                "value": row["popularity"]
            })

    # =====================================
    # FINAL RESPONSE
    # =====================================

    return {
        "restaurant": {
            "place_id": restaurant["place_id"],
            "name": restaurant["name"],
            "horeca_type": restaurant["horeca_type"],
            "main_category": restaurant["main_category"],
            "price_range": restaurant["price_range"],
            "rating": restaurant["rating"],
            "total_reviews": restaurant["total_reviews"],
            "city": restaurant["city"],
            "latitude": restaurant["latitude"],
            "longitude": restaurant["longitude"],
            "google_maps_url": restaurant["google_maps_url"]
        },

        "menu": menu,

        "review_kpis": {
            "total_reviews": restaurant["review_total"],
            "positive_reviews": restaurant["positive_reviews"],
            "negative_reviews": restaurant["negative_reviews"],
            "avg_rating": restaurant["avg_rating"],
        },

        "review_topics": topics,

        "rating_distribution": rating_distribution,

        "popular_times": popular_times,
    }

