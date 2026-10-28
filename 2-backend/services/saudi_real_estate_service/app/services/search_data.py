from services.saudi_real_estate_service.app.utils.database import db

DEFAULT_START_DATE = "2025-01-01"


def date_range_clause(start_date: str | None, end_date: str | None) -> str:
    """Build a `date >= ... [AND date <= ...]` clause. Defaults start to 2025-01-01."""
    clauses = [f"date >= '{start_date or DEFAULT_START_DATE}'"]
    if end_date:
        clauses.append(f"date <= '{end_date}'")
    return " AND ".join(clauses)


def keyword_in_clause(banks: list[str]) -> str:
    """Build a `keyword IN (...)` value list from caller-provided bank names."""
    escaped_keywords = [b.replace("'", "''") for b in banks]
    return "(" + ", ".join(f"'{k}'" for k in escaped_keywords) + ")"


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


async def fetch_top5_banks(
    start_date: str | None = None,
    end_date: str | None = None,
    banks: list[str] | None = None,
):
    date_filter = date_range_clause(start_date, end_date)
    bank_filter = f"AND keyword IN {keyword_in_clause(banks)}" if banks else ""
    # If specific banks were requested, return all of them rather than only the top 5
    limit_clause = "" if banks else "LIMIT 5"

    query = f"""
        SELECT
            keyword AS bank,
            ROUND(AVG(value), 2) AS avg_value
        FROM google_trends
        WHERE project = 'realestate_dbh' AND country = 'SA'
          AND {date_filter}
          {bank_filter}
        GROUP BY keyword
        ORDER BY avg_value DESC
        {limit_clause};
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_bank_distribution(
    start_date: str | None = None,
    end_date: str | None = None,
    banks: list[str] | None = None,
):
    date_filter = date_range_clause(start_date, end_date)
    # Percentage is computed against the full set of banks; the bank filter only
    # narrows which rows are returned, so shares still add up meaningfully.
    bank_filter = f"WHERE bank IN {keyword_in_clause(banks)}" if banks else ""

    query = f"""
        WITH bank_totals AS (
            SELECT
                keyword AS bank,
                SUM(value) AS total_interest
            FROM google_trends
            WHERE project = 'realestate_dbh' AND country = 'SA'
              AND {date_filter}
            GROUP BY keyword
        ),
        distribution AS (
            SELECT
                bank,
                ROUND((total_interest * 100.0) / SUM(total_interest) OVER (), 2) AS percentage
            FROM bank_totals
        )
        SELECT bank, percentage
        FROM distribution
        {bank_filter}
        ORDER BY percentage DESC
    """
    df = db.query(query)
    return df.to_dicts()


async def fetch_bank_distribution_over_time(
    frequency: str,
    banks: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Share of Search over time, on the same 0-100 percentage scale as /distribution
    (percentage of total search volume across ALL banks in that period) — unlike
    /top5-over-time, which reports raw avg Google Trends value (~0-100 index, not a share)."""
    period_expr = FREQUENCY_PERIOD[frequency]
    date_filter = date_range_clause(start_date, end_date)

    if banks:
        keyword_filter = keyword_in_clause(banks)
        query = f"""
            WITH per_period AS (
                SELECT
                    keyword AS bank,
                    {period_expr} AS period,
                    SUM(value) AS period_total
                FROM google_trends
                WHERE project = 'realestate_dbh' AND country = 'SA'
                  AND {date_filter}
                GROUP BY bank, period
            ),
            with_share AS (
                SELECT
                    bank,
                    period,
                    ROUND((period_total * 100.0) / SUM(period_total) OVER (PARTITION BY period), 2) AS percentage
                FROM per_period
            )
            SELECT bank, period, percentage
            FROM with_share
            WHERE bank IN {keyword_filter}
            ORDER BY period, bank;
        """
    else:
        # Default: top 5 banks by total search volume (matches /distribution's own ranking)
        query = f"""
            WITH per_period AS (
                SELECT
                    keyword AS bank,
                    {period_expr} AS period,
                    SUM(value) AS period_total
                FROM google_trends
                WHERE project = 'realestate_dbh' AND country = 'SA'
                  AND {date_filter}
                GROUP BY bank, period
            ),
            with_share AS (
                SELECT
                    bank,
                    period,
                    ROUND((period_total * 100.0) / SUM(period_total) OVER (PARTITION BY period), 2) AS percentage
                FROM per_period
            ),
            top5 AS (
                SELECT bank
                FROM per_period
                GROUP BY bank
                ORDER BY SUM(period_total) DESC
                LIMIT 5
            )
            SELECT w.bank, w.period, w.percentage
            FROM with_share w
            JOIN top5 t ON w.bank = t.bank
            ORDER BY w.period, w.bank;
        """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top5_banks_over_time_grouped(
    frequency: str,
    banks: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    period_expr = FREQUENCY_PERIOD[frequency]
    date_filter = date_range_clause(start_date, end_date)

    if banks:
        # Filter to the caller-provided banks (already capped at 5)
        keyword_filter = keyword_in_clause(banks)

        query = f"""
            SELECT
                keyword AS bank,
                {period_expr} AS period,
                ROUND(AVG(value), 2) AS value
            FROM google_trends
            WHERE project = 'realestate_dbh' AND country = 'SA'
              AND {date_filter}
              AND keyword IN {keyword_filter}
            GROUP BY keyword, period
            ORDER BY period, keyword;
        """
    else:
        # Default: top 5 banks by avg value
        query = f"""
            WITH prepared AS (
                SELECT
                    keyword AS bank,
                    value,
                    {period_expr} AS period
                FROM google_trends
                WHERE project = 'realestate_dbh' AND country = 'SA'
                  AND {date_filter}
            ),
            top5 AS (
                SELECT
                    bank
                FROM prepared
                GROUP BY bank
                ORDER BY AVG(value) DESC
                LIMIT 5
            )
            SELECT
                p.bank,
                p.period,
                ROUND(AVG(value), 2) AS value
            FROM prepared p
            JOIN top5 t ON p.bank = t.bank
            GROUP BY p.bank, p.period
            ORDER BY p.period, p.bank;
        """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top_growing_banks(
    start_date: str | None = None,
    end_date: str | None = None,
    banks: list[str] | None = None,
    limit: int | None = None,
):
    date_filter = date_range_clause(start_date, end_date)

    # `growth` is the slope (REGR_SLOPE) of monthly Share of Search (0-100 scale)
    # against sequential month number, i.e. percentage POINTS of share change
    # per month (not a fraction-of-1, not % change relative to the prior value).
    # e.g. growth = 0.52 means share is rising by ~0.52 percentage points/month.
    # Share is always computed across ALL banks so proportions are correct;
    # an optional bank filter narrows which rows are returned, and `limit`
    # caps the row count (ordered by growth desc) when no specific banks are given.
    # No positivity filter: declining banks (negative growth) are included.
    bank_filter = f"WHERE g.bank IN {keyword_in_clause(banks)}" if banks else ""
    limit_clause = f"LIMIT {int(limit)}" if limit and not banks else ""

    query = f"""
        WITH monthly AS (
            SELECT
                keyword AS bank,
                {FREQUENCY_PERIOD["1m"]} AS period,
                AVG(value) AS avg_value
            FROM google_trends
            WHERE project = 'realestate_dbh' AND country = 'SA'
              AND {date_filter}
            GROUP BY bank, period
        ),
        with_share AS (
            SELECT
                bank,
                period,
                DENSE_RANK() OVER (ORDER BY period) AS period_num,
                avg_value / NULLIF(SUM(avg_value) OVER (PARTITION BY period), 0) * 100 AS share_pct
            FROM monthly
        ),
        current_share AS (
            SELECT bank, ROUND(share_pct::numeric, 2) AS current_share_of_search
            FROM with_share
            WHERE period_num = (SELECT MAX(period_num) FROM with_share)
        ),
        growth AS (
            SELECT
                bank,
                ROUND(REGR_SLOPE(share_pct, period_num)::numeric, 4) AS growth
            FROM with_share
            GROUP BY bank
        )
        SELECT
            g.bank,
            g.growth,
            c.current_share_of_search
        FROM growth g
        JOIN current_share c ON g.bank = c.bank
        {bank_filter}
        ORDER BY g.growth DESC
        {limit_clause};
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_top_growing_banks_over_time(
    frequency: str,
    banks: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    period_expr = FREQUENCY_PERIOD[frequency]
    date_filter = date_range_clause(start_date, end_date)

    if banks:
        # Filter to the caller-provided banks (already capped at 5)
        keyword_filter = keyword_in_clause(banks)

        query = f"""
            SELECT
                keyword AS bank,
                {period_expr} AS period,
                ROUND(AVG(value), 2) AS value
            FROM google_trends
            WHERE project = 'realestate_dbh' AND country = 'SA'
              AND {date_filter}
              AND keyword IN {keyword_filter}
            GROUP BY keyword, period
            ORDER BY period, keyword;
        """
    else:
        # Default: top 5 fastest-growing banks by REGR_SLOPE of monthly Share of Search.
        # Selection always uses a fixed monthly bucket (independent of the requested
        # display `frequency`) so the chosen banks match /top-growing regardless of
        # chart granularity. Only the displayed trend line is bucketed by `frequency`.
        query = f"""
            WITH monthly AS (
                SELECT
                    keyword AS bank,
                    {FREQUENCY_PERIOD["1m"]} AS period,
                    AVG(value) AS avg_value
                FROM google_trends
                WHERE project = 'realestate_dbh' AND country = 'SA'
                  AND {date_filter}
                GROUP BY bank, period
            ),
            with_share AS (
                SELECT
                    bank,
                    period,
                    DENSE_RANK() OVER (ORDER BY period) AS period_num,
                    avg_value / NULLIF(SUM(avg_value) OVER (PARTITION BY period), 0) * 100 AS share_pct
                FROM monthly
            ),
            growth AS (
                SELECT
                    bank,
                    REGR_SLOPE(share_pct, period_num) AS slope
                FROM with_share
                GROUP BY bank
                HAVING REGR_SLOPE(share_pct, period_num) > 0
                ORDER BY slope DESC
                LIMIT 5
            ),
            display AS (
                SELECT
                    keyword AS bank,
                    {period_expr} AS period,
                    AVG(value) AS avg_value
                FROM google_trends
                WHERE project = 'realestate_dbh' AND country = 'SA'
                  AND {date_filter}
                GROUP BY bank, period
            )
            SELECT
                d.bank,
                d.period,
                ROUND(d.avg_value, 2) AS value
            FROM display d
            JOIN growth g ON d.bank = g.bank
            ORDER BY d.period, d.bank;
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
    bank: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    snapshot_filter = region_snapshot_filter(start_date, end_date)

    if bank:
        # Return this bank's score across every province
        raw_keyword = bank.replace("'", "''")

        query = f"""
            SELECT
                keyword,
                geo_code,
                geo_name,
                country,
                ROUND(AVG(value), 2) AS score
            FROM google_trends_regions
            WHERE project = 'realestate_dbh' AND country = 'SA'
              AND keyword = '{raw_keyword}'
              {snapshot_filter}
            GROUP BY keyword, geo_code, geo_name, country;
        """
    else:
        # Default: top-scoring bank per province
        query = f"""
            WITH scored AS (
                SELECT
                    keyword,
                    geo_code,
                    geo_name,
                    country,
                    ROUND(AVG(value), 2) AS score
                FROM google_trends_regions
                WHERE project = 'realestate_dbh' AND country = 'SA'
                  {snapshot_filter}
                GROUP BY keyword, geo_code, geo_name, country
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY geo_code, geo_name, country ORDER BY score DESC) AS rn
                FROM scored
            )
            SELECT keyword, geo_code, geo_name, country, score
            FROM ranked
            WHERE rn = 1;
        """

    df = db.query(query)
    return df.to_dicts()


async def fetch_search_data_banks():
    """Developer keywords actually present in google_trends/google_trends_regions —
    this vocabulary doesn't match /filters/banks (social_data's shorter names) or
    other modules' spellings 1:1, so `bank` params on this router's endpoints must
    use these exact strings, not the shared developer filter list."""
    query = """
        SELECT DISTINCT keyword
        FROM google_trends
        WHERE project = 'realestate_dbh' AND country = 'SA'
        ORDER BY keyword;
    """
    df = db.query(query)
    return df.to_series().to_list()
