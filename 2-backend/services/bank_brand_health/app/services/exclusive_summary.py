from services.bank_brand_health.app.utils.database import db


BRAND_IQ_TABLES = {
    "normal": {
        "snapshot": "saudi_banks.brand_iq_snapshot",
        "trend": "saudi_banks.brand_iq_trend",
    },
    "digital": {
        "snapshot": "saudi_banks.digital_brand_iq_snapshot",
        "trend": "saudi_banks.digital_brand_iq_trend",
    },
}

# saudi_banks.brand_iq_snapshot / brand_iq_trend are real, pre-computed BrandIQ
# tables (replacing the earlier DBHE_Improved-based proxy score, which only
# covered social engagement and just 12 of the 15 tracked banks). Mirrors the
# same table shape already used in services/real_estate_service.
# Both tables are pre-aggregated at monthly granularity only, so `freq` is
# accepted for URL/backward compatibility but not used to re-bucket the data.


def escape_sql(value: str) -> str:
    return value.replace("'", "''")


def _brand_iq_table(segment: str, kind: str) -> str:
    try:
        return BRAND_IQ_TABLES[segment][kind]
    except KeyError as error:
        raise ValueError(f"Unsupported BrandIQ segment or table kind: {segment}/{kind}") from error


# The 'normal' (traditional banks) segment also folds in the digital-only
# banks, so it reflects the whole tracked market rather than just the legacy
# 11 banks. 'digital' stays scoped to the digital-only cohort.
_COMBINED_SNAPSHOT_CTE = """
    WITH combined AS (
        SELECT bank, brand_iq_index, ai_score, share_of_search_pct, rating,
               review_volume, social_sov_pct, engagement, project, calculated_at
        FROM saudi_banks.brand_iq_snapshot
        UNION ALL
        SELECT bank, brand_iq_index, ai_score, share_of_search_pct, rating,
               review_volume, social_sov_pct, engagement, project, calculated_at
        FROM saudi_banks.digital_brand_iq_snapshot
    )
"""

_COMBINED_TREND_CTE = """
    WITH combined AS (
        SELECT period, bank, brand_iq_index, project, calculated_at
        FROM saudi_banks.brand_iq_trend WHERE bank != 'Average'
        UNION ALL
        SELECT period, bank, brand_iq_index, project, calculated_at
        FROM saudi_banks.digital_brand_iq_trend WHERE bank != 'Average'
    ),
    overall_average AS (
        SELECT period, AVG(brand_iq_index) AS brand_iq_index
        FROM combined
        GROUP BY period
    )
"""


async def fetch_brand_iq_snapshot(segment: str):
    """Return the detailed current BrandIQ rows for one peer group."""
    if segment == "normal":
        query = _COMBINED_SNAPSHOT_CTE + """
            SELECT
                RANK() OVER (ORDER BY brand_iq_index DESC) AS rank,
                bank,
                brand_iq_index AS avg_score,
                ai_score,
                share_of_search_pct,
                rating,
                review_volume,
                social_sov_pct,
                engagement,
                project,
                calculated_at
            FROM combined
            ORDER BY rank;
        """
    else:
        table = _brand_iq_table(segment, "snapshot")
        query = f"""
            SELECT
                rank,
                bank,
                brand_iq_index AS avg_score,
                ai_score,
                share_of_search_pct,
                rating,
                review_volume,
                social_sov_pct,
                engagement,
                project,
                calculated_at
            FROM {table}
            ORDER BY rank;
        """
    return db.query(query).to_dicts()


async def fetch_brand_iq_trend(segment: str, banks: list[str] | None = None):
    """Return one peer group's monthly BrandIQ rows and its Average series."""
    if segment == "normal":
        if banks:
            escaped = [escape_sql(bank) for bank in banks]
            bank_filter = "(" + ", ".join(f"'{bank}'" for bank in escaped) + ")"
            bank_where = f"WHERE bank IN {bank_filter}"
        else:
            bank_where = ""
        query = _COMBINED_TREND_CTE + f"""
            SELECT period, bank, brand_iq_index AS avg_score, project, calculated_at
            FROM combined
            {bank_where}
            UNION ALL
            SELECT period, 'Average' AS bank, brand_iq_index AS avg_score, NULL AS project, NULL AS calculated_at
            FROM overall_average
            ORDER BY period, bank;
        """
        return db.query(query).to_dicts()

    table = _brand_iq_table(segment, "trend")
    if banks:
        escaped = [escape_sql(bank) for bank in banks]
        bank_filter = "(" + ", ".join(f"'{bank}'" for bank in escaped) + ")"
        where = f"bank IN {bank_filter} OR bank = 'Average'"
    else:
        where = "TRUE"
    query = f"""
        SELECT period, bank, brand_iq_index AS avg_score, project, calculated_at
        FROM {table}
        WHERE {where}
        ORDER BY period, bank;
    """
    return db.query(query).to_dicts()


async def fetch_top_digital_health():
    """BrandIQ snapshot across all banks (traditional + digital), re-ranked together."""
    query = _COMBINED_SNAPSHOT_CTE + """
        SELECT
            bank,
            brand_iq_index AS avg_score,
            RANK() OVER (ORDER BY brand_iq_index DESC) AS rank,
            ai_score,
            share_of_search_pct,
            rating,
            review_volume,
            social_sov_pct,
            engagement
        FROM combined
        ORDER BY rank;
    """
    return db.query(query).to_dicts()


async def fetch_digital_equity_trend(freq: str):
    """Monthly average BrandIQ index across all banks (traditional + digital)."""
    query = _COMBINED_TREND_CTE + """
        SELECT period, brand_iq_index AS avg_score
        FROM overall_average
        ORDER BY period;
    """
    return db.query(query).to_dicts()


async def fetch_top3_banks_trend(freq: str, banks: list[str] | None = None):
    if banks:
        escaped = [escape_sql(b) for b in banks]
        bank_filter = "(" + ", ".join(f"'{b}'" for b in escaped) + ")"
        query = _COMBINED_TREND_CTE + f"""
            SELECT period, bank, brand_iq_index AS avg_score FROM combined WHERE bank IN {bank_filter}
            UNION ALL
            SELECT period, 'Average' AS bank, brand_iq_index AS avg_score FROM overall_average
            ORDER BY period, bank;
        """
    else:
        # Default: top 5 banks by average BrandIQ index, plus the Average
        # series itself as a benchmark reference line.
        query = _COMBINED_TREND_CTE + """
            , top AS (
                SELECT bank
                FROM combined
                GROUP BY bank
                ORDER BY AVG(brand_iq_index) DESC
                LIMIT 5
            )
            SELECT period, bank, brand_iq_index AS avg_score FROM combined WHERE bank IN (SELECT bank FROM top)
            UNION ALL
            SELECT period, 'Average' AS bank, brand_iq_index AS avg_score FROM overall_average
            ORDER BY period, bank;
        """
    return db.query(query).to_dicts()
