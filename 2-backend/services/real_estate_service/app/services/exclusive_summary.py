from services.real_estate_service.app.utils.database import db
from typing import Optional

# realestate_dbh.brand_iq_snapshot / brand_iq_trend are real, pre-computed BrandIQ
# tables (replacing the earlier percentile-rank proxy score computed from
# social_data/social_data_posts — no longer needed now that a real score exists).
# Both tables are pre-aggregated at monthly granularity only, so `freq` is accepted
# for URL/backward compatibility but not used to re-bucket the data.


def escape_sql(value: str) -> str:
    return value.replace("'", "''")


async def fetch_top_digital_health():
    """BrandIQ snapshot, one row per developer, pre-ranked."""
    query = """
        SELECT
            developer AS bank,
            brand_iq_index AS avg_score,
            rank,
            ai_score,
            share_of_search_pct,
            rating,
            review_volume,
            social_sov_pct,
            engagement
        FROM realestate_dbh.brand_iq_snapshot
        ORDER BY rank;
    """
    return db.query(query).to_dicts()


async def fetch_digital_equity_trend(freq: str):
    """Pre-computed monthly average BrandIQ index across all developers."""
    query = """
        SELECT period, brand_iq_index AS avg_score
        FROM realestate_dbh.brand_iq_trend
        WHERE developer = 'Average'
        ORDER BY period;
    """
    return db.query(query).to_dicts()


async def fetch_top3_banks_trend(freq: str, banks: Optional[list[str]] = None):
    if banks:
        escaped = [escape_sql(b) for b in banks]
        bank_filter = "(" + ", ".join(f"'{b}'" for b in escaped) + ")"
        query = f"""
            SELECT period, developer AS bank, brand_iq_index AS avg_score
            FROM realestate_dbh.brand_iq_trend
            WHERE developer IN {bank_filter}
            ORDER BY period, bank;
        """
    else:
        # Default: top 5 developers by average BrandIQ index, plus the Average
        # series itself as a benchmark reference line.
        query = """
            WITH top AS (
                SELECT developer
                FROM realestate_dbh.brand_iq_trend
                WHERE developer != 'Average'
                GROUP BY developer
                ORDER BY AVG(brand_iq_index) DESC
                LIMIT 5
            )
            SELECT period, developer AS bank, brand_iq_index AS avg_score
            FROM realestate_dbh.brand_iq_trend
            WHERE developer IN (SELECT developer FROM top) OR developer = 'Average'
            ORDER BY period, bank;
        """
    return db.query(query).to_dicts()
