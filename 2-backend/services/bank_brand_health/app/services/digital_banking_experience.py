from services.bank_brand_health.app.utils.database import db
from services.bank_brand_health.app.services.ai_score import _score, _filter_by_llm
import polars as pl


async def fetch_digital_banking_experience(llm: str | None = None):
    df = db.query(
        "SELECT bank, theme, llm, ai_score "
        "FROM saudi_banks.digital_banking_experience"
    )
    df = _filter_by_llm(df, llm)

    themes = sorted(df.select(pl.col("theme").unique()).to_series().to_list())
    rows = sorted(df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True)

    result = {}
    for theme in themes:
        result[theme] = [
            {
                "bank": row["bank"],
                "llm": row["llm"],
                "score": _score(row["ai_score"]),
            }
            for row in rows
            if row["theme"] == theme
        ]

    return result
