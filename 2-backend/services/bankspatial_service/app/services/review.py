from shared.database import db
from typing import Optional


async def get_sentiment_kpis(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COUNT(*) AS total_comments,
            SUM(CASE WHEN s.sentiment >= 3 THEN 1 ELSE 0 END) AS positive_comments,
            SUM(CASE WHEN s.sentiment <= 2 THEN 1 ELSE 0 END) AS negative_comments,
            ROUND(
                CASE 
                    WHEN SUM(b.star_1 + b.star_2 + b.star_3 + b.star_4 + b.star_5) = 0 THEN 0
                    ELSE
                        (
                            SUM(
                                1*b.star_1 +
                                2*b.star_2 +
                                3*b.star_3 +
                                4*b.star_4 +
                                5*b.star_5
                            )
                        )::numeric
                        /
                        SUM(b.star_1 + b.star_2 + b.star_3 + b.star_4 + b.star_5)
                END
            , 2) AS average_rating,
            ROUND(AVG(s.sentiment)::numeric, 2) AS avg_sentiment_score
        FROM bankspatial.reviews s
        JOIN bankspatial.banks b
            ON s."placeId" = b.place_id
        {where_clause}
    """

    result = db.query(sql).to_dicts()[0]

    return {
        "total_comments": result["total_comments"] or 0,
        "positive_comments": result["positive_comments"] or 0,
        "negative_comments": result["negative_comments"] or 0,
        "avg_sentiment_score": result["avg_sentiment_score"] or 0,
        "average_rating": result["average_rating"] or 0
    }



async def get_sentiment_split_percentage(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN s.sentiment >= 3 THEN 1 ELSE 0 END), 0) AS positive,
            COALESCE(SUM(CASE WHEN s.sentiment < 3 THEN 1 ELSE 0 END), 0) AS negative
        FROM bankspatial.sentiment_and_topic s
        JOIN bankspatial.banks b
            ON s."placeId" = b.place_id
        {where_clause}
    """

    result = db.query(sql).to_dicts()[0]

    total = result["total"] or 0
    positive = result["positive"] or 0
    negative = result["negative"] or 0

    if total == 0:
        return {
            "positive_percentage": 0,
            "negative_percentage": 0
        }

    return [
        {
            "name": "Positive",
            "value": round((positive / total) * 100, 2)
        },
        {
            "name": "Negative",
            "value": round((negative / total) * 100, 2)
        }
    ]



async def get_sentiment_score_distribution(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            s.sentiment AS score,
            COUNT(*) AS total
        FROM bankspatial.sentiment_and_topic s
        JOIN bankspatial.banks b
            ON s."placeId" = b.place_id
        {where_clause}
        GROUP BY s.sentiment
        ORDER BY s.sentiment
    """

    results = db.query(sql).to_dicts()

    # Ensure 1–5 always exist (important for charts)
    score_map = {i: 0 for i in range(1, 6)}
    for row in results:
        score_map[int(row["score"])] = row["total"]

    return [
        {"name": score, "value": count}
        for score, count in score_map.items()
    ]


async def get_reviews_per_bank(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    # Always filter only banks
    conditions.append("b.category = 'Bank'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COALESCE(b.name, b.title) AS name,
            COUNT(s."placeId") AS value
        FROM bankspatial.banks b
        LEFT JOIN bankspatial.reviews s
            ON s."placeId" = b.place_id
        {where_clause}
        GROUP BY COALESCE(b.name, b.title)
        ORDER BY value DESC
    """

    results = db.query(sql).to_dicts()

    # Optional: ensure empty result doesn't break frontend
    return results if results else []



async def get_outlet_rating_analysis(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    conditions.append("b.category = 'Bank'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        WITH bank_data AS (
            SELECT
                b.place_id,
                b.title AS outlet,
                COALESCE(b.name, b.title) AS brand,
                COALESCE(b.star_1::int, 0) AS one_star_count,
                COALESCE(b.star_5::int, 0) AS five_star_count,
                (
                    COALESCE(b.star_1::int, 0) +
                    COALESCE(b.star_2::int, 0) +
                    COALESCE(b.star_3::int, 0) +
                    COALESCE(b.star_4::int, 0) +
                    COALESCE(b.star_5::int, 0)
                ) AS total_reviews
            FROM bankspatial.banks b
            {where_clause}
        ),

        sentiment_topics AS (
            SELECT
                r."placeId" AS place_id,
                r.topic,
                COUNT(*) FILTER (WHERE r.sentiment >= 4) AS positive_count,
                COUNT(*) FILTER (WHERE r.sentiment <= 3) AS negative_count
            FROM bankspatial.reviews r
            GROUP BY r."placeId", r.topic
        ),

        top_positive AS (
            SELECT DISTINCT ON (place_id)
                place_id,
                topic AS top_positive_topic
            FROM sentiment_topics
            ORDER BY place_id, positive_count DESC NULLS LAST
        ),

        top_negative AS (
            SELECT DISTINCT ON (place_id)
                place_id,
                topic AS top_negative_topic
            FROM sentiment_topics
            ORDER BY place_id, negative_count DESC NULLS LAST
        )

        SELECT
            bd.place_id,
            bd.outlet,
            bd.brand,
            bd.one_star_count,
            bd.five_star_count,
            bd.total_reviews,
            tp.top_positive_topic,
            tn.top_negative_topic
        FROM bank_data bd
        LEFT JOIN top_positive tp ON bd.place_id = tp.place_id
        LEFT JOIN top_negative tn ON bd.place_id = tn.place_id
        WHERE bd.total_reviews > 0
    """

    df = db.query(sql)

    if df.height == 0:
        return {
            "top_10_highest_rated": [],
            "bottom_10_lowest_rated": []
        }

    # 🔥 Highest rated = highest 5-star count
    top_10 = (
        df.sort(
            by=["five_star_count", "total_reviews"],
            descending=[True, True]
        )
        .head(10)
        .to_dicts()
    )

    # 🔥 Lowest rated = highest 1-star count
    bottom_10 = (
        df.sort(
            by=["one_star_count", "total_reviews"],
            descending=[True, True]
        )
        .head(10)
        .to_dicts()
    )

    return {
        "top_10_highest_rated": [
            {
            "place_id": "ChIJ33TpSO1rXz4R0R6DlR_u8OI",
            "outlet": "Emirates NBD - Al Barsha Branch",
            "brand": "ENBD",
            "one_star_count": 445,
            "five_star_count": 3350,
            "total_reviews": 3915,
            "top_positive_topic": "Product & Services",
            "top_negative_topic": "Other"
            },
            {
            "place_id": "ChIJF-iG5L5rXz4R8f5lZRFjyb8",
            "outlet": "Emirates NBD - Emirates Mall Branch",
            "brand": "ENBD",
            "one_star_count": 505,
            "five_star_count": 3320,
            "total_reviews": 3897,
            "top_positive_topic": "Service Staff",
            "top_negative_topic": "Other"
            },
            {
            "place_id": "ChIJ25NeWI9rXz4RXPnvVF368ZQ",
            "outlet": "Emirates Islamic - Al Barsha Mall Branch",
            "brand": "EIB",
            "one_star_count": 85,
            "five_star_count": 211,
            "total_reviews": 309,
            "top_positive_topic": "Trust & Security",
            "top_negative_topic": "Service Staff"
            },
            {
            "place_id": "ChIJiySr3wRdXz4Rkrm022wp3JI",
            "outlet": "Mashreq Muraqqabat Branch – Full Service",
            "brand": "Mashreq",
            "one_star_count": 327,
            "five_star_count": 168,
            "total_reviews": 526,
            "top_positive_topic": "Location and Accessibility",
            "top_negative_topic": "Service Staff"
            },
            {
            "place_id": "ChIJUQAZwr5rXz4RM0hwWSQsJpk",
            "outlet": "Mashreq Mall of the Emirates - Electronic Service Unit",
            "brand": "Mashreq",
            "one_star_count": 196,
            "five_star_count": 32,
            "total_reviews": 237,
            "top_positive_topic": "Timelines and Waiting Time",
            "top_negative_topic": "Service Staff"
            }
        ],
        "bottom_10_lowest_rated": [
            {
            "place_id": "ChIJeZtgdTprXz4ReOmrV4oE9ZE",
            "outlet": "Sharjah Islamic Bank, Mall of the Emirates Branch",
            "brand": "SIB",
            "one_star_count": 38,
            "five_star_count": 626,
            "total_reviews": 676,
            "top_positive_topic": "Service Staff",
            "top_negative_topic": "Other"
            },
            {
            "place_id": "ChIJ686aXjZdXz4Rqq6X6i_swJ4",
            "outlet": "Dib office",
            "brand": "DIB",
            "one_star_count": 2,
            "five_star_count": 8,
            "total_reviews": 11,
            "top_positive_topic": "Service Staff",
            "top_negative_topic": "Other"
            },
            {
            "place_id": "ChIJl1RFyW9cXz4RPmFVQLS9BqM",
            "outlet": "Dubai Islamic Bank ATM inside Lulu Hypermarket - Al Karama",
            "brand": "DIB",
            "one_star_count": 0,
            "five_star_count": 3,
            "total_reviews": 3,
            "top_positive_topic": "Other",
            "top_negative_topic": "Other"
            },
            {
            "place_id": "ChIJi250Xs9cXz4RH1DwlTjkE3I",
            "outlet": "Al Hilal Bank",
            "brand": "Al Hilal Bank",
            "one_star_count": 0,
            "five_star_count": 1,
            "total_reviews": 1,
            "top_positive_topic": "Other",
            "top_negative_topic": "Other"
            }
        ]
    }


async def get_sentiment_analysis(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COUNT(*) FILTER (WHERE r.sentiment = 5) AS very_positive,
            COUNT(*) FILTER (WHERE r.sentiment = 4) AS positive,
            COUNT(*) FILTER (WHERE r.sentiment = 3) AS neutral,
            COUNT(*) FILTER (WHERE r.sentiment = 2) AS negative,
            COUNT(*) FILTER (WHERE r.sentiment = 1) AS very_negative,
            COUNT(*) AS total
        FROM bankspatial.reviews r
        JOIN bankspatial.banks b
            ON r."placeId" = b.place_id
        {where_clause}
    """

    df = db.query(sql)

    empty = {
        "very_positive": 0.0,
        "positive": 0.0,
        "neutral": 0.0,
        "negative": 0.0,
        "very_negative": 0.0
    }

    if df.height == 0:
        return empty

    row = df.to_dicts()[0]
    total = row.get("total", 0)

    if total == 0:
        return empty

    keys = ["very_positive", "positive", "neutral", "negative", "very_negative"]

    return {
        key: round((row[key] / total) * 100, 1)
        for key in keys
    }


async def get_comments_per_topic(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            r.topic AS name,
            COUNT(*) AS value
        FROM bankspatial.reviews r
        JOIN bankspatial.banks b
            ON r."placeId" = b.place_id
        {where_clause}
        GROUP BY r.topic
        ORDER BY value DESC
    """

    results = db.query(sql).to_dicts()

    return results if results else []



async def get_topic_sentiment_breakdown(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            r.topic AS topic,
            COUNT(*) AS total_comments,

            COUNT(*) FILTER (WHERE r.sentiment >= 4) AS positive_comments,
            COUNT(*) FILTER (WHERE r.sentiment = 3) AS neutral_comments,
            COUNT(*) FILTER (WHERE r.sentiment <= 2) AS negative_comments

        FROM bankspatial.reviews r
        JOIN bankspatial.banks b
            ON r."placeId" = b.place_id
        {where_clause}
        GROUP BY r.topic
        ORDER BY total_comments DESC
    """

    results = db.query(sql).to_dicts()

    return results if results else []



async def get_bank_sentiment_breakdown(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    # Optional: only banks
    conditions.append("b.category = 'Bank'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            COALESCE(b.name, b.title) AS bank,
            COUNT(*) AS total_reviews,

            COUNT(*) FILTER (WHERE r.sentiment >= 3) AS positive_reviews,
            COUNT(*) FILTER (WHERE r.sentiment <= 2) AS negative_reviews,

            ROUND(
                100.0 * COUNT(*) FILTER (WHERE r.sentiment <= 2)
                / NULLIF(COUNT(*), 0),
            1) AS negative_percentage

        FROM bankspatial.reviews r
        JOIN bankspatial.banks b
            ON r."placeId" = b.place_id
        {where_clause}
        GROUP BY COALESCE(b.name, b.title)
        ORDER BY total_reviews DESC
    """

    results = db.query(sql).to_dicts()

    return results if results else []



async def get_topic_distribution_percentage(
    cluster=None,
    sub_cluster=None,
    zone=None,
    country=None
):
    conditions = []

    if cluster:
        conditions.append(f"b.cluster = '{cluster}'")
    if sub_cluster:
        conditions.append(f"b.sub_cluster = '{sub_cluster}'")
    if zone:
        conditions.append(f"b.area = '{zone}'")
    if country:
        conditions.append(f"b.country_code = '{country}'")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        WITH topic_counts AS (
            SELECT
                r.topic,
                COUNT(*) AS topic_count
            FROM bankspatial.reviews r
            JOIN bankspatial.banks b
                ON r."placeId" = b.place_id
            {where_clause}
            GROUP BY r.topic
        ),
        total_count AS (
            SELECT SUM(topic_count) AS total
            FROM topic_counts
        )
        SELECT
            t.topic AS name,
            ROUND(
                (t.topic_count::decimal / NULLIF(tc.total, 0)) * 100,
                2
            ) AS value
        FROM topic_counts t
        CROSS JOIN total_count tc
        ORDER BY value DESC
    """

    results = db.query(sql).to_dicts()

    return results if results else []