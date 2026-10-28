from services.real_estate_service.app.utils.database import db
import polars as pl


def _score(value) -> float:
    """Normalize numeric and numeric-text database scores for the API."""
    return round(float(value), 2)


def _filter_by_llm(df: pl.DataFrame, llm: str | None) -> pl.DataFrame:
    """Apply the optional UI LLM filter without interpolating it into SQL."""
    if not llm or llm.strip().lower() == "all assistants":
        selected_llm = "overall"
    elif llm.strip().lower() == "all":
        return df
    else:
        selected_llm = llm.strip().lower()

    return df.filter(pl.col("llm").str.to_lowercase() == selected_llm)


def _filter_by_location(df: pl.DataFrame, location: str | None) -> pl.DataFrame:
    """Apply the optional UI region/geo filter. Defaults to the UAE-wide aggregate
    (mirrors _filter_by_llm's "Overall" default); "all" bypasses filtering entirely."""
    if not location or location.strip().lower() == "uae":
        selected_location = "uae"
    elif location.strip().lower() == "all":
        return df
    else:
        selected_location = location.strip().lower()

    return df.filter(pl.col("location").str.to_lowercase() == selected_location)


def _filter_by_bank(df: pl.DataFrame, bank: str | None) -> pl.DataFrame:
    """Apply an optional case-insensitive exact bank filter."""
    if not bank or bank.strip().lower() in {"all", "all banks"}:
        return df

    selected_bank = bank.strip().lower()
    return df.filter(pl.col("bank").str.to_lowercase() == selected_bank)


def _filter_citations_by_llm(df: pl.DataFrame, llm: str | None) -> pl.DataFrame:
    """Filter citations while treating All Assistants as an unfiltered view."""
    if not llm or llm.strip().lower() in {"all", "all assistants"}:
        return df

    selected_llm = llm.strip().lower()
    return df.filter(pl.col("llm").str.to_lowercase() == selected_llm)


def _filter_citations_by_location(df: pl.DataFrame, location: str | None) -> pl.DataFrame:
    """Citations' own unscoped bucket is the literal "All Locations" row (9.5k of
    10.1k rows), not "UAE" like the discoverability tables — that's the default."""
    if not location or location.strip().lower() == "all locations":
        selected_location = "all locations"
    elif location.strip().lower() == "all":
        return df
    else:
        selected_location = location.strip().lower()

    return df.filter(pl.col("location").str.to_lowercase() == selected_location)


async def fetch_overall_discoverability(llm: str | None = None, location: str | None = None):
    df = db.query(
        "SELECT location, brand AS bank, llm, ai_score "
        "FROM realestate_dbh.overall_discoverability"
    )
    df = _filter_by_llm(df, llm)
    df = _filter_by_location(df, location)
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True
    )

    return [
        {
            "bank": row["bank"],
            "llm": row["llm"],
            "score": _score(row["ai_score"]),
            "location": row["location"],
        }
        for row in rows
    ]


async def fetch_theme_discoverability(llm: str | None = None, location: str | None = None):
    df = db.query(
        "SELECT location, bank, theme, llm, ai_score "
        "FROM realestate_dbh.theme_discoverability"
    )
    df = _filter_by_llm(df, llm)
    df = _filter_by_location(df, location)

    themes = sorted(df.select(pl.col("theme").unique()).to_series().to_list())
    rows = sorted(df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True)

    result = {}
    for theme in themes:
        result[theme] = [
            {
                "bank": row["bank"],
                "llm": row["llm"],
                "score": _score(row["ai_score"]),
                "location": row["location"],
            }
            for row in rows
            if row["theme"] == theme
        ]

    return result


async def fetch_product_discoverability(llm: str | None = None, location: str | None = None):
    # realestate_dbh calls this "property type" rather than "product" — same shape,
    # aliased back to `product` so the /ai-score/products contract is unchanged.
    df = db.query(
        "SELECT location, bank, property_type AS product, llm, ai_score "
        "FROM realestate_dbh.property_type_discoverability"
    )
    df = _filter_by_llm(df, llm)
    df = _filter_by_location(df, location)

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
                "location": row["location"],
            }
            for row in rows
            if row["product"] == product
        ]

    return result


async def fetch_market_positioning_discoverability(llm: str | None = None, location: str | None = None):
    # No banking equivalent — real-estate-only table.
    df = db.query(
        "SELECT location, bank, market_position, llm, ai_score "
        "FROM realestate_dbh.market_positioning_discoverability"
    )
    df = _filter_by_llm(df, llm)
    df = _filter_by_location(df, location)

    positions = sorted(df.select(pl.col("market_position").unique()).to_series().to_list())
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True
    )

    result = {}
    for position in positions:
        result[position] = [
            {
                "bank": row["bank"],
                "llm": row["llm"],
                "score": _score(row["ai_score"]),
                "location": row["location"],
            }
            for row in rows
            if row["market_position"] == position
        ]

    return result


async def fetch_audience_affinity(
    llm: str | None = "Overall", bank: str | None = None
):
    df = db.query(
        "SELECT bank, customer_segment, llm, affinity_score, rationale "
        "FROM realestate_dbh.audience_affinity"
    )
    df = _filter_by_llm(df, llm)
    df = _filter_by_bank(df, bank)

    banks = sorted(df.select(pl.col("bank").unique()).to_series().to_list())
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["affinity_score"]), reverse=True
    )

    result = {}
    for bank_name in banks:
        result[bank_name] = [
            {
                "customer_segment": row["customer_segment"],
                "llm": row["llm"],
                "score": _score(row["affinity_score"]),
                "rationale": row["rationale"],
            }
            for row in rows
            if row["bank"] == bank_name
        ]

    return result


async def fetch_citations(llm: str | None = None, location: str | None = None):
    df = db.query(
        "SELECT location, bank, llm, model, analysis_section, prompt, title, url "
        "FROM realestate_dbh.citations"
    )
    df = _filter_citations_by_llm(df, llm)
    df = _filter_citations_by_location(df, location)
    return df.to_dicts()


async def fetch_brand_projection(
    llm: str | None = "Overall", bank: str | None = None
):
    projection_df = db.query(
        "SELECT bank, llm, personality FROM realestate_dbh.brand_projection"
    )
    points_df = db.query(
        "SELECT bank, llm, type, text FROM realestate_dbh.brand_projection_points"
    )
    projection_df = _filter_by_llm(projection_df, llm)
    projection_df = _filter_by_bank(projection_df, bank)
    points_df = _filter_by_llm(points_df, llm)
    points_df = _filter_by_bank(points_df, bank)

    result = {}
    projection_rows = projection_df.to_dicts()
    point_rows = points_df.to_dicts()
    banks = sorted({row["bank"] for row in projection_rows})

    for bank_name in banks:
        bank_projections = [row for row in projection_rows if row["bank"] == bank_name]
        bank_projections.sort(
            key=lambda row: (row["llm"].lower() != "overall", row["llm"])
        )
        bank_points = [row for row in point_rows if row["bank"] == bank_name]

        projections = []
        for projection in bank_projections:
            llm_points = [
                {"type": point["type"], "text": point["text"]}
                for point in bank_points
                if point["llm"] == projection["llm"]
            ]
            projections.append(
                {
                    "llm": projection["llm"],
                    "personality": projection["personality"],
                    "points": llm_points,
                }
            )

        # Preserve the original top-level fields for existing UI consumers. The
        # Overall projection is preferred; complete per-LLM data is in projections.
        result[bank_name] = {
            "personality": bank_projections[0]["personality"],
            "strengths": [
                point["text"] for point in bank_points if point["type"] == "strength"
            ],
            "positioning_opportunities": [
                point["text"]
                for point in bank_points
                if point["type"]
                in {"positioning", "positioning_opportunity", "opportunity"}
            ],
            "projections": projections,
        }

    return result


async def fetch_ai_score_banks():
    """Banks that have Perception data (brand_projection AND audience_affinity).
    Unlike banking, real-estate's AI-perception names are kept as-is — no
    canonical-name remapping to the social-data/filters bank list."""
    projection_banks = set(
        db.query("SELECT DISTINCT bank FROM realestate_dbh.brand_projection")
        .to_series()
        .to_list()
    )
    affinity_banks = set(
        db.query("SELECT DISTINCT bank FROM realestate_dbh.audience_affinity")
        .to_series()
        .to_list()
    )

    banks_with_data = {bank for bank in projection_banks & affinity_banks if bank}
    return sorted(banks_with_data)
