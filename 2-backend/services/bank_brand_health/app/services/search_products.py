import polars as pl
from services.bank_brand_health.app.utils.database import db
from services.bank_brand_health.app.utils.classifier import classify_keyword
from collections import defaultdict


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

DEFAULT_START_DATE = "2025-01-01"


def date_range_clause(start_date: str | None, end_date: str | None) -> str:
    """Build a `date >= ... [AND date <= ...]` clause. Defaults start to 2025-01-01."""
    clauses = [f"date >= '{start_date or DEFAULT_START_DATE}'"]
    if end_date:
        clauses.append(f"date <= '{end_date}'")
    return " AND ".join(clauses)


def category_in_clause(products: list[str]) -> str:
    """Build a `category IN (...)` value list from caller-provided product names."""
    escaped = [p.replace("'", "''") for p in products]
    return "(" + ", ".join(f"'{p}'" for p in escaped) + ")"


async def fetch_top5_products(
    start_date: str | None = None,
    end_date: str | None = None,
    products: list[str] | None = None,
):
    date_filter = date_range_clause(start_date, end_date)
    product_filter = f"AND category IN {category_in_clause(products)}" if products else ""
    # If specific products were requested, return all of them rather than only the top 5
    limit_clause = "" if products else "LIMIT 5"

    # Ranked by total search volume (SUM), matching /distribution's methodology.
    # AVG would let categories with very few sample rows (e.g. niche keywords)
    # outrank categories with much higher real-world search volume.
    query = f"""
        SELECT
            category AS products,
            ROUND(SUM(value), 2) AS avg_value
        FROM saudi_banks.search_products
        WHERE {date_filter}
          AND category IS NOT NULL
          {product_filter}
        GROUP BY category
        ORDER BY avg_value DESC
        {limit_clause}
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_product_distribution(
    start_date: str | None = None,
    end_date: str | None = None,
    products: list[str] | None = None,
):
    date_filter = date_range_clause(start_date, end_date)
    # Percentage is computed against the full set of products; the product filter only
    # narrows which rows are returned, so shares still add up meaningfully.
    product_filter = f"WHERE product IN {category_in_clause(products)}" if products else ""

    query = f"""
        WITH totals AS (
            SELECT
                category,
                SUM(value) AS total_interest
            FROM saudi_banks.search_products
            WHERE {date_filter}
              AND category IS NOT NULL
            GROUP BY category
        ),
        distribution AS (
            SELECT
                category AS product,
                ROUND((total_interest * 100.0) / SUM(total_interest) OVER (), 2) AS percentage
            FROM totals
        )
        SELECT product, percentage
        FROM distribution
        {product_filter}
        ORDER BY percentage DESC;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_product_distribution_over_time(
    frequency: str,
    products: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Share of Search over time, on the same 0-100 percentage scale as /distribution
    (percentage of total search volume across ALL products in that period) — unlike
    /top5-over-time, which reports raw summed Google Trends value, not a share."""
    period_expr = FREQUENCY_PERIOD[frequency]
    date_filter = date_range_clause(start_date, end_date)

    if products:
        category_filter = category_in_clause(products)
        query = f"""
            WITH per_period AS (
                SELECT
                    category AS product,
                    {period_expr} AS period,
                    SUM(value) AS period_total
                FROM saudi_banks.search_products
                WHERE {date_filter}
                  AND category IS NOT NULL
                GROUP BY product, period
            ),
            with_share AS (
                SELECT
                    product,
                    period,
                    ROUND((period_total * 100.0) / SUM(period_total) OVER (PARTITION BY period), 2) AS percentage
                FROM per_period
            )
            SELECT product, period, percentage
            FROM with_share
            WHERE product IN {category_filter}
            ORDER BY period, product;
        """
    else:
        # Default: top 5 products by total search volume (matches /distribution's own ranking)
        query = f"""
            WITH per_period AS (
                SELECT
                    category AS product,
                    {period_expr} AS period,
                    SUM(value) AS period_total
                FROM saudi_banks.search_products
                WHERE {date_filter}
                  AND category IS NOT NULL
                GROUP BY product, period
            ),
            with_share AS (
                SELECT
                    product,
                    period,
                    ROUND((period_total * 100.0) / SUM(period_total) OVER (PARTITION BY period), 2) AS percentage
                FROM per_period
            ),
            top5 AS (
                SELECT product
                FROM per_period
                GROUP BY product
                ORDER BY SUM(period_total) DESC
                LIMIT 5
            )
            SELECT w.product, w.period, w.percentage
            FROM with_share w
            JOIN top5 t ON w.product = t.product
            ORDER BY w.period, w.product;
        """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top5_over_time_grouped(
    frequency: str,
    products: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    period_expr = FREQUENCY_PERIOD[frequency]
    date_filter = date_range_clause(start_date, end_date)

    if products:
        # Filter to the caller-provided products (already capped at 5)
        category_filter = category_in_clause(products)

        query = f"""
            SELECT
                category AS product,
                {period_expr} AS period,
                ROUND(SUM(value), 2) AS value
            FROM saudi_banks.search_products
            WHERE {date_filter}
              AND category IN {category_filter}
            GROUP BY category, period
            ORDER BY period, category;
        """
    else:
        # Default: top 5 products by total search volume (matches /distribution)
        query = f"""
            WITH prepared AS (
                SELECT
                    category,
                    value,
                    date,
                    {period_expr} AS period
                FROM saudi_banks.search_products
                WHERE {date_filter}
                  AND category IS NOT NULL
            ),
            top5 AS (
                SELECT
                    category
                FROM prepared
                GROUP BY category
                ORDER BY SUM(value) DESC
                LIMIT 5
            )
            SELECT
                p.category AS product,
                p.period,
                ROUND(SUM(value), 2) AS value
            FROM prepared p
            JOIN top5 t ON p.category = t.category
            GROUP BY p.category, p.period
            ORDER BY p.period, p.category;
        """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top_growing_products(
    start_date: str | None = None,
    end_date: str | None = None,
    products: list[str] | None = None,
    limit: int | None = None,
):
    date_filter = date_range_clause(start_date, end_date)

    # `growth` is the slope (REGR_SLOPE) of monthly Share of Search (0-100 scale)
    # against sequential month number, i.e. percentage POINTS of share change
    # per month (not a fraction-of-1, not % change relative to the prior value).
    # e.g. growth = 0.52 means share is rising by ~0.52 percentage points/month.
    # Share is computed across ALL products so proportions are correct; an
    # optional product filter narrows which rows are returned, and `limit`
    # caps the row count (ordered by growth desc) when no products are given.
    # No positivity filter: declining products (negative growth) are included.
    product_filter = f"WHERE g.product IN {category_in_clause(products)}" if products else ""
    limit_clause = f"LIMIT {int(limit)}" if limit and not products else ""

    query = f"""
        WITH monthly AS (
            SELECT
                category AS product,
                {FREQUENCY_PERIOD["1m"]} AS period,
                SUM(value) AS total_value
            FROM saudi_banks.search_products
            WHERE {date_filter}
              AND category IS NOT NULL
            GROUP BY product, period
        ),
        with_share AS (
            SELECT
                product,
                period,
                DENSE_RANK() OVER (ORDER BY period) AS period_num,
                total_value / NULLIF(SUM(total_value) OVER (PARTITION BY period), 0) * 100 AS share_pct
            FROM monthly
        ),
        current_share AS (
            SELECT product, ROUND(share_pct::numeric, 2) AS current_share_of_search
            FROM with_share
            WHERE period_num = (SELECT MAX(period_num) FROM with_share)
        ),
        growth AS (
            SELECT
                product,
                ROUND(REGR_SLOPE(share_pct, period_num)::numeric, 4) AS growth
            FROM with_share
            GROUP BY product
        )
        SELECT
            g.product,
            g.growth,
            c.current_share_of_search
        FROM growth g
        JOIN current_share c ON g.product = c.product
        {product_filter}
        ORDER BY g.growth DESC
        {limit_clause};
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top_growing_products_over_time(
    frequency: str,
    products: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    period_expr = FREQUENCY_PERIOD[frequency]
    date_filter = date_range_clause(start_date, end_date)

    if products:
        # Filter to the caller-provided products (already capped at 5)
        category_filter = category_in_clause(products)

        query = f"""
            SELECT
                category AS product,
                {period_expr} AS period,
                ROUND(SUM(value), 2) AS value
            FROM saudi_banks.search_products
            WHERE {date_filter}
              AND category IN {category_filter}
            GROUP BY category, period
            ORDER BY period, category;
        """
    else:
        # Default: top 5 fastest-growing products by REGR_SLOPE of monthly Share of Search.
        # Selection always uses a fixed monthly bucket (independent of the requested
        # display `frequency`) so the chosen products match /top-growing regardless of
        # chart granularity. Only the displayed trend line is bucketed by `frequency`.
        query = f"""
            WITH monthly AS (
                SELECT
                    category,
                    {FREQUENCY_PERIOD["1m"]} AS period,
                    SUM(value) AS total_value
                FROM saudi_banks.search_products
                WHERE {date_filter}
                  AND category IS NOT NULL
                GROUP BY category, period
            ),
            with_share AS (
                SELECT
                    category,
                    period,
                    DENSE_RANK() OVER (ORDER BY period) AS period_num,
                    total_value / NULLIF(SUM(total_value) OVER (PARTITION BY period), 0) * 100 AS share_pct
                FROM monthly
            ),
            growth AS (
                SELECT
                    category,
                    REGR_SLOPE(share_pct, period_num) AS slope
                FROM with_share
                GROUP BY category
                HAVING REGR_SLOPE(share_pct, period_num) > 0
                ORDER BY slope DESC
                LIMIT 5
            ),
            display AS (
                SELECT
                    category,
                    {period_expr} AS period,
                    SUM(value) AS total_value
                FROM saudi_banks.search_products
                WHERE {date_filter}
                  AND category IS NOT NULL
                GROUP BY category, period
            )
            SELECT
                d.category AS product,
                d.period,
                ROUND(d.total_value, 2) AS value
            FROM display d
            JOIN growth g ON d.category = g.category
            ORDER BY d.period, d.category;
        """

    df = db.query(query)
    return df.to_dicts()


def region_snapshot_filter(start_date: str | None, end_date: str | None) -> str:
    """Filter geographic snapshots (google_trends_regions) by their refresh date.

    This table stores periodic full re-scrapes (keyed by `last_updated`), not a
    daily time series, so a date range selects which refresh batch(es) to use
    rather than re-aggregating per-day interest.
    """
    clauses = []
    if start_date:
        clauses.append(f"last_updated >= '{start_date}'")
    if end_date:
        clauses.append(f"last_updated < ('{end_date}'::date + INTERVAL '1 day')")
    return (" AND " + " AND ".join(clauses)) if clauses else ""


async def fetch_maps(
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    snapshot_filter = region_snapshot_filter(start_date, end_date)

    # 1️⃣ SQL: aggregate at keyword + geo level
    query = f"""
        SELECT
            keyword,
            geo_code,
            geo_name,
            country,
            AVG(value) AS score
        FROM google_trends_regions
        WHERE project = 'Saudi Banks Products'
          {snapshot_filter}
        GROUP BY keyword, geo_code, geo_name, country;
    """

    # get polars DataFrame
    df = db.query(query)

    # 2️⃣ Add category column
    df = df.with_columns(
        pl.col("keyword")
        .map_elements(classify_keyword, return_dtype=pl.Utf8)
        .alias("category")
    )

    # 2.5️⃣ Filter to the requested product, if any
    if product:
        df = df.filter(pl.col("category") == product)

    # 3️⃣ SECOND aggregation: category
    df = (
        df
        .group_by(["category", "geo_code", "geo_name", "country"])
        .agg(
            pl.col("score").mean().round(2).alias("score")
        )
    )

    # 4️⃣ If no product was requested, keep only the top-scoring category per province
    if not product:
        df = (
            df
            .sort("score", descending=True)
            .group_by(["geo_code", "geo_name", "country"], maintain_order=True)
            .first()
        )

    # 5️⃣ Convert to dict
    return df.to_dicts()
