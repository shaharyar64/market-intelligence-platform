from services.uae_bank_brand_health.app.utils.database import db


BRAND_IQ_TABLES = {
    "normal": {
        "snapshot": "uae_banks_dbh.brand_iq_snapshot",
        "trend": "uae_banks_dbh.brand_iq_trend",
    },
    "digital": {
        "snapshot": "uae_banks_dbh.digital_brand_iq_snapshot",
        "trend": "uae_banks_dbh.digital_brand_iq_trend",
    },
}

# uae_banks_dbh.brand_iq_snapshot / brand_iq_trend are real, pre-computed BrandIQ
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


async def fetch_brand_iq_snapshot(segment: str):
    """Return the detailed current BrandIQ rows for one peer group."""
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
    """BrandIQ snapshot, one row per bank, pre-ranked."""
    query = """
        SELECT
            bank,
            brand_iq_index AS avg_score,
            rank,
            ai_score,
            share_of_search_pct,
            rating,
            review_volume,
            social_sov_pct,
            engagement
        FROM uae_banks_dbh.brand_iq_snapshot
        ORDER BY rank;
    """
    return db.query(query).to_dicts()


async def fetch_digital_equity_trend(freq: str):
    """Pre-computed monthly average BrandIQ index across all banks."""
    query = """
        SELECT period, brand_iq_index AS avg_score
        FROM uae_banks_dbh.brand_iq_trend
        WHERE bank = 'Average'
        ORDER BY period;
    """
    return db.query(query).to_dicts()


async def fetch_top3_banks_trend(freq: str, banks: list[str] | None = None):
    if banks:
        escaped = [escape_sql(b) for b in banks]
        bank_filter = "(" + ", ".join(f"'{b}'" for b in escaped) + ")"
        query = f"""
            SELECT period, bank, brand_iq_index AS avg_score
            FROM uae_banks_dbh.brand_iq_trend
            WHERE bank IN {bank_filter}
            ORDER BY period, bank;
        """
    else:
        # Default: top 5 banks by average BrandIQ index, plus the Average
        # series itself as a benchmark reference line.
        query = """
            WITH top AS (
                SELECT bank
                FROM uae_banks_dbh.brand_iq_trend
                WHERE bank != 'Average'
                GROUP BY bank
                ORDER BY AVG(brand_iq_index) DESC
                LIMIT 5
            )
            SELECT period, bank, brand_iq_index AS avg_score
            FROM uae_banks_dbh.brand_iq_trend
            WHERE bank IN (SELECT bank FROM top) OR bank = 'Average'
            ORDER BY period, bank;
        """
    return db.query(query).to_dicts()
