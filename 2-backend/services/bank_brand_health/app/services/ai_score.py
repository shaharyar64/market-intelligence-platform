from services.bank_brand_health.app.utils.database import db
import polars as pl
from functools import lru_cache
from urllib.parse import urlparse


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
        "SELECT brand AS bank, llm, ai_score FROM saudi_banks.overall_discoverability "
        "UNION ALL "
        "SELECT brand AS bank, llm, ai_score FROM saudi_banks.digital_overall_discoverability"
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
        "SELECT bank, theme, llm, ai_score FROM saudi_banks.theme_discoverability "
        "UNION ALL "
        "SELECT bank, theme, llm, ai_score FROM saudi_banks.digital_theme_discoverability"
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
        "SELECT bank, product, llm, ai_score FROM saudi_banks.product_discoverability "
        "UNION ALL "
        "SELECT bank, product, llm, ai_score FROM saudi_banks.digital_product_discoverability"
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
        "SELECT bank, customer_segment, llm, affinity_score, rationale "
        "FROM saudi_banks.audience_affinity"
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
    df = _with_citation_fields(db.query("SELECT * FROM saudi_banks.citations"))

    # Bank scopes everything, overlap included; assistant scopes only the volume.
    df = _filter_by_bank(df, bank)
    filtered = _filter_citations_by_llm(df, llm)
    kpi = {**_citation_volume(filtered), **_citation_overlap(df)}

    return {"citations": filtered.to_dicts(), "kpi": kpi}


ALL_BANKS = "All Banks"  # market-level rows, not attributable to one bank

# Official sites per bank, taken from the domains actually cited. Banks with no
# entry (EZ Bank, Saudi Digital Bank) never had their own site cited.
OFFICIAL_DOMAINS = {
    "Alinma Bank": ["alinma.com"],
    "Riyad Bank": ["riyadbank.com"],
    "Al Rajhi Bank": ["alrajhibank.com.sa"],
    "Saudi Awwal Bank": ["sab.com"],
    "Saudi National Bank": ["alahli.com"],
    "Saudi Investment Bank": ["saib.com.sa"],
    "Arab National Bank": ["anb.com.sa"],
    "D360 Bank": ["d360.com"],
    "Banque Saudi Fransi": ["bsf.sa"],
    "Bank AlBilad": ["bankalbilad.com.sa"],
    "Bank AlJazira": ["aljazirabank.com.sa", "bankaljazira.com"],
    "Vision Bank": ["visionbank.bank", "visionbank.com", "visionbank.com.sa"],
    "STC Bank": ["stcbank.com.sa"],
}


def _citation_domain(title: str, url: str) -> str:
    """Real source domain. Gemini URLs are vertexaisearch redirects, but its
    `title` holds the actual domain."""
    host = title if "vertexaisearch.cloud.google.com" in url else urlparse(url).netloc
    return host.strip().lower().removeprefix("www.")


def _is_domain(domain: str, official: str) -> bool:
    return domain == official or domain.endswith("." + official)


def _source_kind(bank: str, domain: str) -> str:
    if any(_is_domain(domain, d) for d in OFFICIAL_DOMAINS.get(bank, [])):
        return "own_site"
    if any(_is_domain(domain, d) for ds in OFFICIAL_DOMAINS.values() for d in ds):
        return "other_bank_site"
    return "third_party"


# Domain -> category for third-party sources; anything unlisted is "Other".
# ponytail: static map, extend as new domains show up (or swap for an LLM batch
# cached per domain if the long tail matters).
GOVERNMENT = ["sama.gov.sa", "cma.org.sa", "saudiexchange.sa", "zatca.gov.sa"]
SOCIAL = [
    "reddit.com", "linkedin.com", "youtube.com", "facebook.com", "x.com",
    "twitter.com", "instagram.com", "tiktok.com", "quora.com", "medium.com",
    "vocal.media", "apps.apple.com", "play.google.com",
]
NEWS = [
    "arabnews.com", "argaam.com", "argaamplus.s3.amazonaws.com", "forbes.com",
    "forbesmiddleeast.com", "zawya.com", "gulfnews.com", "saudigazette.com.sa",
    "bloomberg.com", "reuters.com", "ft.com", "cnbc.com", "alarabiya.net",
    "agbi.com", "arabianbusiness.com", "businesswire.com", "prnewswire.com",
    "fintechnews.ae", "fintechfutures.com", "gfmag.com", "finance.yahoo.com",
    "thedigitalbanker.com", "retailbankerinternational.com", "worldfinance.com",
    "ffnews.com", "economymiddleeast.com", "intellinews.com", "thebanker.com",
    "euromoney.com", "fintechmagazine.com", "businesschief.eu", "waya.media",
    "sharikatmubasher.com", "qatar-tribune.com", "banksdaily.com", "spa.gov.sa",
]
REFERENCE = [
    "wikipedia.org", "grokipedia.com", "saudipedia.com", "yallacompare.com",
    "globaldata.com", "cbinsights.com", "statista.com", "crunchbase.com",
    "glassdoor.com", "zoominfo.com", "pitchbook.com", "tracxn.com", "dnb.com",
    "fitchratings.com", "spglobal.com", "marketscreener.com", "simplywall.st",
    "mordorintelligence.com", "researchandmarkets.com", "expertmarketresearch.com",
    "kenresearch.com", "imarcgroup.com", "verifiedmarketresearch.com",
    "marketresearch.com", "brandfinance.com", "brandirectory.com", "theorg.com",
    "yelp.com", "relbanks.com", "leadiq.com", "weforum.org", "pestel-analysis.com",
    "portersfiveforce.com", "matrixbcg.com", "umbrex.com", "swfinstitute.org",
]


@lru_cache(maxsize=None)
def _source_category(bank: str, domain: str) -> str:
    kind = _source_kind(bank, domain)
    if kind == "own_site":
        return "Brand-owned"
    if kind == "other_bank_site":
        return "Other bank"
    if any(_is_domain(domain, d) for d in NEWS):  # before .gov.sa: spa.gov.sa is news
        return "News & business"
    if domain.endswith((".gov.sa", ".gov")) or any(_is_domain(domain, d) for d in GOVERNMENT):
        return "Government & regulatory"
    for category, domains in (
        ("Social / community", SOCIAL),
        ("Comparison & reference", REFERENCE),
    ):
        if any(_is_domain(domain, d) for d in domains):
            return category
    return "Other"


def _with_citation_fields(df: pl.DataFrame) -> pl.DataFrame:
    """Add domain, norm_url and category."""
    return df.with_columns(
        pl.struct("title", "url")
        .map_elements(
            lambda r: _citation_domain(r["title"], r["url"]), return_dtype=pl.Utf8
        )
        .alias("domain"),
        pl.col("url")
        .map_elements(_normalize_citation_url, return_dtype=pl.Utf8)
        .alias("norm_url"),
    ).with_columns(
        pl.struct("bank", "domain")
        .map_elements(
            lambda r: _source_category(r["bank"], r["domain"]), return_dtype=pl.Utf8
        )
        .alias("category")
    )


def _rows(df: pl.DataFrame) -> list[dict]:
    return df.to_dicts()


async def fetch_citation_analysis(llm: str | None = None):
    all_df = _with_citation_fields(db.query("SELECT * FROM saudi_banks.citations"))
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
            pl.struct("bank", "domain")
            .map_elements(
                lambda r: _source_kind(r["bank"], r["domain"]), return_dtype=pl.Utf8
            )
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

    return {
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
    }


async def fetch_brand_projection(
    llm: str | None = "Overall", bank: str | None = None
):
    projection_df = db.query(
        "SELECT bank, llm, personality FROM saudi_banks.brand_projection"
    )
    points_df = db.query(
        'SELECT bank, llm, type, text FROM saudi_banks.brand_projection_points'
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
        db.query("SELECT DISTINCT bank FROM saudi_banks.brand_projection")
        .to_series()
        .to_list()
    )
    affinity_banks = set(
        db.query("SELECT DISTINCT bank FROM saudi_banks.audience_affinity")
        .to_series()
        .to_list()
    )

    banks_with_data = {bank for bank in projection_banks & affinity_banks if bank}
    return sorted(banks_with_data)
