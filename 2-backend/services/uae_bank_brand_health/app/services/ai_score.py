from services.uae_bank_brand_health.app.utils.database import db
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


async def fetch_overall_discoverability(llm: str | None = None):
    df = db.query(
        "SELECT brand AS bank, llm, ai_score "
        "FROM uae_banks_dbh.overall_discoverability"
    )
    df = _filter_by_llm(df, llm)
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["ai_score"]), reverse=True
    )

    return [
        {"bank": row["bank"], "llm": row["llm"], "score": _score(row["ai_score"])}
        for row in rows
    ]


async def fetch_theme_discoverability(llm: str | None = None):
    df = db.query(
        "SELECT brand AS bank, theme, llm, ai_score "
        "FROM uae_banks_dbh.theme_discoverability"
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


async def fetch_product_discoverability(llm: str | None = None):
    df = db.query(
        "SELECT brand AS bank, theme AS product, llm, ai_score "
        "FROM uae_banks_dbh.product_discoverability"
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


async def fetch_audience_affinity(
    llm: str | None = "Overall", bank: str | None = None
):
    df = db.query(
        "SELECT brand AS bank, customer_segment, llm, affinity_score, rationale "
        "FROM uae_banks_dbh.audience_affinity"
    )
    df = _filter_by_llm(df, llm)
    df = _filter_by_bank(df, bank)

    banks = sorted(df.select(pl.col("bank").unique()).to_series().to_list())
    rows = sorted(
        df.to_dicts(), key=lambda row: _score(row["affinity_score"]), reverse=True
    )

    result = {}
    for bank in banks:
        result[bank] = [
            {
                "customer_segment": row["customer_segment"],
                "llm": row["llm"],
                "score": _score(row["affinity_score"]),
                "rationale": row["rationale"],
            }
            for row in rows
            if row["bank"] == bank
        ]

    return result


def _normalize_citation_url(url: str | None) -> str:
    """Strip query/fragment and trailing slash so the same page under
    different tracking params or casing is treated as one source."""
    if not url:
        return ""
    return url.split("#")[0].split("?")[0].strip().rstrip("/").lower()


def _citation_overlap(df: pl.DataFrame) -> dict:
    """Cross-assistant agreement stats. Only meaningful over the FULL,
    unfiltered dataset: with a single assistant selected, 'assistant_count'
    would collapse to 1 and every source would trivially count as 'cited by
    all assistants', which measures nothing. So this always runs on all
    citations regardless of the caller's assistant filter."""
    assistants = sorted(df.select(pl.col("llm").unique()).to_series().to_list())
    assistant_count = len(assistants)

    per_url = (
        df.with_columns(
            pl.col("url")
            .map_elements(_normalize_citation_url, return_dtype=pl.Utf8)
            .alias("normalized_url")
        )
        .group_by("normalized_url")
        .agg(pl.col("llm").n_unique().alias("assistants_citing"))
    )

    overlap_counts = per_url.group_by("assistants_citing").agg(
        pl.len().alias("url_count")
    )
    overlap_distribution = {
        str(row["assistants_citing"]): row["url_count"]
        for row in overlap_counts.to_dicts()
    }

    return {
        "assistant_count": assistant_count,
        "assistants": assistants,
        "cited_by_all_assistants": overlap_distribution.get(str(assistant_count), 0),
        "max_overlap": max((int(k) for k in overlap_distribution), default=0),
        "overlap_distribution": overlap_distribution,
    }


def _citation_volume(df: pl.DataFrame) -> dict:
    """Volume stats scoped to whatever citations were passed in — these are
    well-defined for a single assistant too, so they follow the filter."""
    normalized_urls = df.select(
        pl.col("url")
        .map_elements(_normalize_citation_url, return_dtype=pl.Utf8)
        .alias("normalized_url")
    )
    return {
        "total_citations": df.height,
        "unique_urls": normalized_urls.select(pl.col("normalized_url").n_unique()).item(),
    }


async def fetch_citations(llm: str | None = None, bank: str | None = None):
    df = _with_citation_fields(db.query("SELECT *, brand AS bank FROM uae_banks_dbh.citations"))

    # Bank scopes everything, overlap included; assistant scopes only the volume.
    df = _filter_by_bank(df, bank)
    filtered = _filter_citations_by_llm(df, llm)
    kpi = {**_citation_volume(filtered), **_citation_overlap(df)}

    return {"citations": filtered.to_dicts(), "kpi": kpi}


ALL_BANKS = "All Banks"  # market-level rows, not attributable to one bank

# Source domain and category come pre-classified from the data team
# (citations.source_domain / source_category). "Brand-owned" is the bank's own site.


def _with_citation_fields(df: pl.DataFrame) -> pl.DataFrame:
    """Add domain, norm_url and category from the data team's columns."""
    return df.with_columns(
        pl.col("source_domain").alias("domain"),
        pl.col("source_category").alias("category"),
        pl.col("url")
        .map_elements(_normalize_citation_url, return_dtype=pl.Utf8)
        .alias("norm_url"),
    )


def _rows(df: pl.DataFrame) -> list[dict]:
    return df.to_dicts()


def _recency_bucket() -> pl.Expr:
    """Publication-year bucket. A missing date, or the 1970 epoch placeholder, is Undated."""
    year = pl.col("date").dt.year()
    return (
        pl.when(pl.col("date").is_null() | (year <= 1970)).then(pl.lit("Undated"))
        .when(year >= 2026).then(pl.lit("2026"))
        .when(year == 2025).then(pl.lit("2025"))
        .when(year >= 2023).then(pl.lit("2023–2024"))
        .when(year >= 2020).then(pl.lit("2020–2022"))
        .otherwise(pl.lit("Before 2020"))
        .alias("bucket")
    )


async def fetch_citation_analysis(llm: str | None = None, bank: str | None = None):
    # Bank scopes the whole response, like /citations.
    all_df = _filter_by_bank(
        _with_citation_fields(db.query("SELECT *, brand AS bank FROM uae_banks_dbh.citations")), bank
    )
    df = _filter_citations_by_llm(all_df, llm)
    banks = df.filter(pl.col("bank") != ALL_BANKS)
    bank_total = banks.height or 1

    by_bank = banks.group_by("bank").agg(
        pl.len().alias("citations"),
        pl.col("norm_url").n_unique().alias("unique_urls"),
        pl.col("domain").n_unique().alias("unique_domains"),
    ).with_columns(
        (pl.col("citations") * 100.0 / bank_total).round(2).alias("share_pct")
    ).sort("citations", descending=True)

    top_domains = (
        df.group_by("domain")
        .agg(
            pl.len().alias("citations"),
            pl.col("bank").n_unique().alias("banks"),
            pl.col("llm").unique().sort().alias("assistants"),
            pl.col("analysis_section").unique().sort().alias("sections"),
        )
        .sort("citations", descending=True)
        .head(15)
    )
    # Domains x banks heatmap for the 10 most-cited domains.
    domain_by_bank = banks.filter(
        pl.col("domain").is_in(top_domains["domain"].head(10))
    ).group_by("bank", "domain").agg(pl.len().alias("citations"))

    source_mix = (
        banks.with_columns(
            pl.when(pl.col("category") == "Brand-owned")
            .then(pl.lit("own_site"))
            .otherwise(pl.lit("third_party"))
            .alias("kind")
        )
        .group_by("bank", "kind")
        .agg(pl.len().alias("citations"))
    )

    # Categories are bank-attributed only (like source_mix): "Brand-owned" has
    # no meaning for market-level rows, so shares sum to 100 over bank_citations.
    by_category = banks.group_by("category").agg(
        pl.len().alias("citations")
    ).with_columns(
        (pl.col("citations") * 100.0 / bank_total).round(2).alias("share_pct")
    ).sort("citations", descending=True)

    # Every category in the data, most-cited first. Always over the unfiltered set
    # so the list (and any colours the UI assigns from it) stays stable across filters.
    categories = (
        all_df.group_by("category").len().sort("len", descending=True)["category"].to_list()
    )

    return {
        "categories": categories,
        "kpi": {
            "total_citations": df.height,
            "bank_citations": banks.height,
            "market_level_citations": df.height - banks.height,
            "unique_domains": df["domain"].n_unique(),
            "unique_urls": df["norm_url"].n_unique(),
            # Cross-assistant stat: always over the unfiltered set (see _citation_overlap).
            "cited_by_all_assistants": _citation_overlap(all_df)["cited_by_all_assistants"],
        },
        "by_bank": _rows(by_bank),
        "by_bank_assistant": _rows(
            banks.group_by("bank", "llm").agg(pl.len().alias("citations"))
        ),
        "by_bank_section": _rows(
            banks.group_by("bank", "analysis_section").agg(pl.len().alias("citations"))
        ),
        "top_domains": _rows(top_domains),
        "domain_by_bank": _rows(domain_by_bank),
        "source_mix": _rows(source_mix),
        "by_category": _rows(by_category),
        "by_category_assistant": _rows(
            banks.group_by("category", "llm").agg(pl.len().alias("citations"))
        ),
        "by_category_bank": _rows(
            banks.group_by("bank", "category").agg(pl.len().alias("citations"))
        ),
        # Publication dates (citations.date); rows without one are "Undated".
        "evidence_recency": _rows(
            df.group_by(_recency_bucket(), "llm", "bank").agg(pl.len().alias("citations"))
        ),
        # Over all rows (market-level included) so Overall Discoverability shows up.
        "source_by_section": _rows(
            df.group_by("category", "analysis_section").agg(pl.len().alias("citations"))
        ),
    }


async def fetch_brand_projection(
    llm: str | None = "Overall", bank: str | None = None
):
    projection_df = db.query(
        "SELECT brand AS bank, llm, personality FROM uae_banks_dbh.brand_projection"
    )
    points_df = db.query(
        'SELECT brand AS bank, llm, type, text FROM uae_banks_dbh.brand_projection_points'
    )
    projection_df = _filter_by_llm(projection_df, llm)
    projection_df = _filter_by_bank(projection_df, bank)
    points_df = _filter_by_llm(points_df, llm)
    points_df = _filter_by_bank(points_df, bank)

    result = {}
    projection_rows = projection_df.to_dicts()
    point_rows = points_df.to_dicts()
    banks = sorted({row["bank"] for row in projection_rows})

    for bank in banks:
        bank_projections = [row for row in projection_rows if row["bank"] == bank]
        bank_projections.sort(
            key=lambda row: (row["llm"].lower() != "overall", row["llm"])
        )
        bank_points = [row for row in point_rows if row["bank"] == bank]

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
        result[bank] = {
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

    Returned using the exact 'bank' values stored in those tables (not the
    short-code names from the canonical /filters/banks list) so the caller can
    pass a value straight back into the `bank` query param on
    /audience-affinity and /brand-projection without any name translation.
    """
    projection_banks = set(
        db.query("SELECT DISTINCT brand FROM uae_banks_dbh.brand_projection")
        .to_series()
        .to_list()
    )
    affinity_banks = set(
        db.query("SELECT DISTINCT brand FROM uae_banks_dbh.audience_affinity")
        .to_series()
        .to_list()
    )

    banks_with_data = {bank for bank in projection_banks & affinity_banks if bank}
    return sorted(banks_with_data)
