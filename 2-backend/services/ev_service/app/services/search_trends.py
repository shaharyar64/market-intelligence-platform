from shared.database import db
from typing import Optional


FREQUENCY_PERIOD = {
    "1m": "TO_CHAR(date_trunc('month', date), 'YYYY-MM')",
    "3m": "TO_CHAR(date_trunc('quarter', date), 'YYYY-MM')",
    "6m": """CASE 
                WHEN EXTRACT(MONTH FROM date) <= 6 
                THEN CONCAT(EXTRACT(YEAR FROM date), '-H1')
                ELSE CONCAT(EXTRACT(YEAR FROM date), '-H2')
            END""",
    "1y": "TO_CHAR(date_trunc('year', date), 'YYYY')"
}

def country_where(country: Optional[str]):
    return "" if not country or country == "Overall" else f"WHERE country = '{country}'"



async def fetch_top5_products(country: Optional[str] = "Overall"):
    where_clause = country_where(country)

    query = f"""
        SELECT 
            category AS products,
            ROUND(AVG(value), 2) AS avg_value
        FROM ev.search_trends
        {where_clause}
        GROUP BY category
        ORDER BY avg_value DESC
        LIMIT 5
    """
    df = db.query(query)
    return df.to_dicts()



async def fetch_product_distribution(country: Optional[str] = "Overall"):
    where_clause = country_where(country)

    query = f"""
        WITH counts AS (
            SELECT 
                category,
                COUNT(*) AS cnt
            FROM ev.search_trends
            {where_clause}
            GROUP BY category
        )
        SELECT 
            category AS product,
            ROUND((cnt * 100.0) / SUM(cnt) OVER (), 2) AS percentage
        FROM counts
        ORDER BY percentage DESC;
    """

    df = db.query(query)
    return df.to_dicts()



async def fetch_top5_over_time_grouped(
    frequency: str,
    country: Optional[str] = "Overall"
):
    period_expr = FREQUENCY_PERIOD[frequency]
    where_clause = country_where(country)

    query = f"""
        WITH prepared AS (
            SELECT
                category,
                value,
                date,
                {period_expr} AS period
            FROM ev.search_trends
            {where_clause}
        ),
        top5 AS (
            SELECT 
                category
            FROM prepared
            GROUP BY category
            ORDER BY AVG(value) DESC
            LIMIT 5
        )
        SELECT
            p.category AS product,
            p.period,
            ROUND(AVG(value), 2) AS value
        FROM prepared p
        JOIN top5 t ON p.category = t.category
        GROUP BY p.category, p.period
        ORDER BY p.period, p.category;
    """

    df = db.query(query)
    return df.to_dicts()



async def fetch_top_growing_products(country: Optional[str] = "Overall"):
    where_clause = country_where(country)

    query = f"""
        WITH product_growth AS (
            SELECT
                category AS product,
                FIRST_VALUE(value) OVER (
                    PARTITION BY category 
                    ORDER BY date
                ) AS first_value,
                LAST_VALUE(value) OVER (
                    PARTITION BY category 
                    ORDER BY date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS last_value
            FROM ev.search_trends
            {where_clause}
        ),
        growth AS (
            SELECT DISTINCT
                product,
                first_value,
                last_value,
                (last_value - first_value) AS growth
            FROM product_growth
        )
        SELECT 
            product,
            growth
        FROM growth
        ORDER BY growth DESC
        LIMIT 5;
    """

    df = db.query(query)
    return df.to_dicts()



async def fetch_top_growing_products_over_time(
    frequency: str,
    country: Optional[str] = "Overall"
):
    period_expr = FREQUENCY_PERIOD[frequency]
    where_clause = country_where(country)

    query = f"""
        WITH prepared AS (
            SELECT
                category,
                {period_expr} AS period,
                AVG(value) AS avg_value
            FROM ev.search_trends
            {where_clause}
            GROUP BY category, period
        ),
        first_last AS (
            SELECT
                category,
                FIRST_VALUE(avg_value) OVER (PARTITION BY category ORDER BY period) AS first_value,
                LAST_VALUE(avg_value) OVER (
                    PARTITION BY category ORDER BY period 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS last_value
            FROM prepared
        ),
        growth AS (
            SELECT DISTINCT
                category,
                (last_value - first_value) AS growth
            FROM first_last
            ORDER BY growth DESC
            LIMIT 5
        )
        SELECT
            p.category AS product,
            p.period,
            ROUND(p.avg_value, 2) AS value
        FROM prepared p
        JOIN growth g ON p.category = g.category
        ORDER BY p.period, p.category;
    """

    df = db.query(query)
    return df.to_dicts()
