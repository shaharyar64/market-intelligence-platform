from services.bank_brand_health.app.utils.database import db
from services.bank_brand_health.app.services.ai_score import _score, _filter_by_llm
import polars as pl


async def fetch_digital_overall_discoverability(llm: str | None = None):
    df = db.query(
        "SELECT brand AS bank, llm, ai_score "
        "FROM saudi_banks.digital_overall_discoverability"
    )
    df = _filter_by_llm(df, llm)
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True
    )

    return [
        {"bank": row["bank"], "llm": row["llm"], "score": _score(row["ai_score"])}
        for row in rows
    ]


async def fetch_digital_theme_discoverability(llm: str | None = None):
    df = db.query(
        "SELECT bank, theme, llm, ai_score "
        "FROM saudi_banks.digital_theme_discoverability"
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


async def fetch_digital_product_discoverability(llm: str | None = None):
    df = db.query(
        "SELECT bank, product, llm, ai_score "
        "FROM saudi_banks.digital_product_discoverability"
    )
    df = _filter_by_llm(df, llm)

    products = sorted(df.select(pl.col("product").unique()).to_series().to_list())
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True
    )

    result = {}
    for product in products:
        result[product] = [
            {
                "bank": row["bank"],
                "llm": row["llm"],
                "score": _score(row["ai_score"]),
            }
            for row in rows
            if row["product"] == product
        ]

    return result
