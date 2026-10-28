import asyncio
from shared.database import db
from datetime import timedelta
from functools import lru_cache
import os
import re

# Was gateway Settings.DB_TABLE_NAME; read from env directly so this service
# doesn't import (and its image doesn't need) the gateway package.
DEFAULT_TABLE_REF = os.getenv("DB_TABLE_NAME", 'beer_pricing_analysis."plaformsV2"')

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_iso_date(value: str) -> str:
    """Validate a user-supplied `date` filter is a plain YYYY-MM-DD string
    before it's interpolated into raw SQL — queries in this module are built
    via f-strings rather than bound parameters, so this is the only guard."""
    text = str(value).strip()
    if not _ISO_DATE_RE.match(text):
        raise ValueError(f"Invalid date filter: {value!r}. Expected YYYY-MM-DD.")
    return text


# QUANTITY_BUCKET_LABELS = [
#     "<= 25CL (Small / Trial)",
#     "26-35CL (Standard Small - \"330ml range\")",
#     "36-45CL (Mid Size - \"440ml range\")",
#     "46-55CL (Large - \"500ml range\")",
#     "56-100CL (Extra Large / Sharing)",
#     "100CL+ (Bulk / Packs / Kegs)",
# ]

QUANTITY_BUCKET_LABELS = [
    "<= 25CL",
    "26-35CL",
    "36-45CL",
    "46-55CL",
    "56-100CL",
    "100CL+",
]


def _escape_sql_text(value: str) -> str:
    return value.replace("'", "''")


def _escape_like_text(value: str) -> str:
    return _escape_sql_text(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _sql_list(values: list[str]) -> str:
    return ", ".join(f"'{_escape_sql_text(v)}'" for v in values)


def _sql_list_lower_trim(values: list[str]) -> str:
    cleaned = [v.strip().lower() for v in values if str(v).strip()]
    return _sql_list(cleaned)


def _region_remap_sql(col: str = "region") -> str:
    """CASE expression that remaps override retailers to their canonical region."""
    cases = [
        f"WHEN LOWER(TRIM(platform)) = '{_escape_sql_text(p.lower())}' THEN '{_escape_sql_text(regions[0])}'"
        for p, regions in RETAILER_REGION_OVERRIDE.items()
        if regions
    ]
    if not cases:
        return f"TRIM({col})"
    return "CASE " + " ".join(cases) + f" ELSE TRIM({col}) END"


# Brand aliases that should collapse to a single canonical brand key for the
# hero-SKU tracker/trend/price-trend queries (source data has inconsistent
# cleaned_brand values across retailers for the same underlying brand).
_HERO_SKU_BRAND_ALIASES: dict[str, str] = {
    "stella artois": "stella",
}


def _hero_sku_brand_remap_sql(col: str = "cleaned_brand") -> str:
    """CASE expression that collapses known brand aliases to their canonical key."""
    cases = [
        f"WHEN LOWER(TRIM({col})) = '{_escape_sql_text(alias)}' THEN '{_escape_sql_text(canonical)}'"
        for alias, canonical in _HERO_SKU_BRAND_ALIASES.items()
    ]
    if not cases:
        return f"LOWER(TRIM({col}))"
    return "CASE " + " ".join(cases) + f" ELSE LOWER(TRIM({col})) END"


@lru_cache(maxsize=1)
def _default_table_columns() -> frozenset[str]:
    query = """
    SELECT DISTINCT column_name
    FROM information_schema.columns
    WHERE table_schema = 'beer_pricing_analysis'
      AND LOWER(table_name) = 'plaformsv2';
    """
    df = db.query(query)
    return frozenset(str(row.get("column_name")) for row in df.to_dicts() if row.get("column_name"))


def _default_table_has_column(column_name: str) -> bool:
    return column_name in _default_table_columns()


_BRAND_ALIAS_MAP: dict[str, list[str]] = {
    "stella": ["stella", "stella artois"],
    "stella artois": ["stella", "stella artois"],
}


def _expand_brand_aliases(values: list[str]) -> list[str]:
    expanded: set[str] = set()
    for value in values:
        key = str(value).strip().lower()
        if not key:
            continue
        expanded.update(_BRAND_ALIAS_MAP.get(key, [key]))
    return sorted(expanded)


def _expand_market_aliases(values: list[str]) -> list[str]:
    alias_map = {
        "uae": ["uae", "united arab emirates", "u.a.e", "ae", "united-arab-emirates"],
        "united arab emirates": ["uae", "united arab emirates", "u.a.e", "ae", "united-arab-emirates"],
        "bahrain": ["bahrain", "baharain", "bh"],
        "baharain": ["bahrain", "baharain", "bh"],
    }
    expanded: set[str] = set()
    for value in values:
        key = str(value).strip().lower()
        if not key:
            continue
        expanded.update(alias_map.get(key, [key]))
    return sorted(expanded)


def _normalize_quantity_filter_value(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace("≤", "<=")
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", "")
    )


def _quantity_to_cl_sql(column: str) -> str:
    return f"""
    CASE
        WHEN NULLIF(TRIM({column}::text), '') IS NULL THEN NULL
        WHEN UPPER(TRIM({column}::text)) ~ '^[0-9]+(\\.[0-9]+)?\\s*CL$'
            THEN CAST(REGEXP_REPLACE(UPPER(TRIM({column}::text)), '[^0-9\\.]', '', 'g') AS numeric)
        WHEN UPPER(TRIM({column}::text)) ~ '^[0-9]+(\\.[0-9]+)?\\s*ML$'
            THEN CAST(REGEXP_REPLACE(UPPER(TRIM({column}::text)), '[^0-9\\.]', '', 'g') AS numeric) / 10.0
        WHEN UPPER(TRIM({column}::text)) ~ '^[0-9]+(\\.[0-9]+)?\\s*L$'
            THEN CAST(REGEXP_REPLACE(UPPER(TRIM({column}::text)), '[^0-9\\.]', '', 'g') AS numeric) * 100.0
        ELSE NULL
    END
    """


def _build_quantity_filter_condition(
    values: list[str], column: str, partial_text: bool = False
) -> str | None:
    if not values:
        return None

    raw_values: list[str] = []
    bucket_conditions: list[str] = []
    quantity_cl_expr = _quantity_to_cl_sql(column)

    for value in values:
        key = _normalize_quantity_filter_value(value)
        if key.startswith("<=25cl"):
            bucket_conditions.append(f"({quantity_cl_expr}) <= 25")
        elif key.startswith("26-35cl"):
            bucket_conditions.append(f"({quantity_cl_expr}) BETWEEN 26 AND 35")
        elif key.startswith("36-45cl"):
            bucket_conditions.append(f"({quantity_cl_expr}) BETWEEN 36 AND 45")
        elif key.startswith("46-55cl"):
            bucket_conditions.append(f"({quantity_cl_expr}) BETWEEN 46 AND 55")
        elif key.startswith("56-100cl"):
            bucket_conditions.append(f"({quantity_cl_expr}) BETWEEN 56 AND 100")
        elif key.startswith("100cl+") or key == "100cl":
            bucket_conditions.append(f"({quantity_cl_expr}) > 100")
        else:
            raw_values.append(str(value))

    all_conditions: list[str] = []
    if raw_values:
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({column})) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in raw_values
                if str(v).strip()
            ]
            if like_conditions:
                all_conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            all_conditions.append(
                f"LOWER(TRIM({column})) IN ({_sql_list_lower_trim(raw_values)})"
            )
    all_conditions.extend(bucket_conditions)

    if not all_conditions:
        return None

    return "(" + " OR ".join(all_conditions) + ")"


def _quantity_bucket_label_from_value(value: str) -> str | None:
    match = re.match(
        r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(ml|cl|l)\s*$",
        str(value),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2).lower()

    if unit == "ml":
        cl_value = amount / 10.0
    elif unit == "l":
        cl_value = amount * 100.0
    else:
        cl_value = amount

    if cl_value <= 25:
        return QUANTITY_BUCKET_LABELS[0]
    if 26 <= cl_value <= 35:
        return QUANTITY_BUCKET_LABELS[1]
    if 36 <= cl_value <= 45:
        return QUANTITY_BUCKET_LABELS[2]
    if 46 <= cl_value <= 55:
        return QUANTITY_BUCKET_LABELS[3]
    if 56 <= cl_value <= 100:
        return QUANTITY_BUCKET_LABELS[4]
    if cl_value > 100:
        return QUANTITY_BUCKET_LABELS[5]
    return None


def _pivot_brand_rows_single_metric(
    rows: list[dict],
    metric_key: str,
    brand_field: str = "brand",
    date_field: str = "date",
) -> list[dict]:
    by_date: dict[str, dict] = {}
    for row in rows:
        date = row.get(date_field)
        brand = row.get(brand_field)
        if date is None or not brand:
            continue
        key = str(date)
        by_date.setdefault(key, {"date": date})
        by_date[key][brand] = row.get(metric_key)
    return [by_date[k] for k in sorted(by_date.keys())]


def _pivot_brand_rows_multi_metric(
    rows: list[dict],
    metric_keys: list[str],
    brand_field: str = "brand",
    date_field: str = "date",
) -> dict:
    output: dict[str, list[dict]] = {}
    for metric_key in metric_keys:
        output[metric_key] = _pivot_brand_rows_single_metric(
            rows,
            metric_key=metric_key,
            brand_field=brand_field,
            date_field=date_field,
        )
    return output


def _build_common_filter_conditions(
    filters: dict | None = None, table_alias: str = "", partial_text: bool = False
) -> list[str]:
    if not filters:
        return []

    prefix = f"{table_alias}." if table_alias else ""
    conditions: list[str] = []

    markets = filters.get("market") or []
    if markets:
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}country)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in markets
                if str(v).strip()
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            market_values = _expand_market_aliases(markets)
            conditions.append(
                f"LOWER(TRIM({prefix}country)) IN ({_sql_list(market_values)})"
            )

    retailers = filters.get("retailer") or []
    if retailers:
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}platform)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in retailers
                if str(v).strip()
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            conditions.append(
                f"LOWER(TRIM({prefix}platform)) IN ({_sql_list_lower_trim(retailers)})"
            )

    segments = filters.get("segment") or []
    if segments:
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}segment)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in segments
                if str(v).strip()
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            conditions.append(
                f"LOWER(TRIM({prefix}segment)) IN ({_sql_list_lower_trim(segments)})"
            )

    comps = filters.get("comp") or []
    if comps and _default_table_has_column("comp"):
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}comp)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in comps
                if str(v).strip()
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            conditions.append(
                f"LOWER(TRIM({prefix}comp)) IN ({_sql_list_lower_trim(comps)})"
            )

    types = filters.get("type") or []
    if types:
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}pack_format)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in types
                if str(v).strip()
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            conditions.append(
                f"LOWER(TRIM({prefix}pack_format)) IN ({_sql_list_lower_trim(types)})"
            )

    brands = filters.get("brand") or []
    if brands:
        brand_values = _expand_brand_aliases(brands)
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}cleaned_brand)) LIKE "
                    f"'%{_escape_like_text(v)}%' ESCAPE E'\\\\'"
                )
                for v in brand_values
                if v
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            conditions.append(
                f"LOWER(TRIM({prefix}cleaned_brand)) IN ({_sql_list(brand_values)})"
            )

    sub_types = filters.get("sub_type") or []
    if sub_types:
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}sub_type)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in sub_types
                if str(v).strip()
            ]
            if like_conditions:
                conditions.append("(" + " OR ".join(like_conditions) + ")")
        else:
            conditions.append(
                f"LOWER(TRIM({prefix}sub_type)) IN ({_sql_list_lower_trim(sub_types)})"
            )

    cities = filters.get("city") or []
    if cities:
        cities_lower = {c.strip().lower() for c in cities if c.strip()}
        # Platforms whose canonical region matches the filter → include regardless of DB region
        include_overrides = [
            p for p, regions in RETAILER_REGION_OVERRIDE.items()
            if any(r.strip().lower() in cities_lower for r in regions)
        ]
        # Platforms whose canonical region does NOT match → exclude even if DB region matches
        exclude_overrides = [
            p for p, regions in RETAILER_REGION_OVERRIDE.items()
            if not any(r.strip().lower() in cities_lower for r in regions)
        ]
        if partial_text:
            like_conditions = [
                (
                    f"LOWER(TRIM({prefix}region)) LIKE "
                    f"'%{_escape_like_text(str(v).strip().lower())}%' ESCAPE E'\\\\'"
                )
                for v in cities
                if str(v).strip()
            ]
            if like_conditions:
                region_part = "(" + " OR ".join(like_conditions) + ")"
                if include_overrides:
                    platform_part = f"LOWER(TRIM({prefix}platform)) IN ({_sql_list_lower_trim(include_overrides)})"
                    region_part = f"({region_part} OR {platform_part})"
                if exclude_overrides:
                    excl_part = f"LOWER(TRIM({prefix}platform)) NOT IN ({_sql_list_lower_trim(exclude_overrides)})"
                    conditions.append(f"({region_part} AND {excl_part})")
                else:
                    conditions.append(region_part)
        else:
            region_cond = f"LOWER(TRIM({prefix}region)) IN ({_sql_list_lower_trim(cities)})"
            if include_overrides:
                platform_incl = f"LOWER(TRIM({prefix}platform)) IN ({_sql_list_lower_trim(include_overrides)})"
                region_cond = f"({region_cond} OR {platform_incl})"
            if exclude_overrides:
                platform_excl = f"LOWER(TRIM({prefix}platform)) NOT IN ({_sql_list_lower_trim(exclude_overrides)})"
                conditions.append(f"({region_cond} AND {platform_excl})")
            else:
                conditions.append(region_cond)

    skus = filters.get("sku") or []
    if skus:
        safe_skus = [str(int(v)) for v in skus]
        conditions.append(f"{prefix}units IN ({', '.join(safe_skus)})")

    quantities = filters.get("quantity") or []
    if quantities:
        quantity_condition = _build_quantity_filter_condition(
            quantities, f"{prefix}quantity", partial_text=partial_text
        )
        if quantity_condition:
            conditions.append(quantity_condition)

    return conditions


def _use_local_pricing(filters: dict | None = None) -> bool:
    return bool((filters or {}).get("local", False))


def _get_price_columns(filters: dict | None = None) -> tuple[str, str]:
    if _use_local_pricing(filters):
        return "original_price_local", "discounted_price_local"
    return "original_price_usd", "discounted_price_usd"


def _get_pricing_currency(filters: dict | None = None) -> str:
    if not _use_local_pricing(filters):
        return "USD"

    markets = (filters or {}).get("market") or []
    if not markets:
        return "USD"

    market = str(markets[0]).strip().lower()
    if market in {"uae", "united arab emirates", "u.a.e", "ae", "united-arab-emirates"}:
        return "AED"
    if market in {"bahrain", "baharain", "bh"}:
        return "BHD"
    return "LOCAL"


async def fetch_overview(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)

    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)

    # Build conditions like brand-sales does - match exactly
    # NOTE: _build_common_filter_conditions uses original region, but we need to apply region remap to WHERE clause
    conditions = _build_common_filter_conditions(filters, table_alias="")
    conditions.append(f"({date_expr}) IS NOT NULL")
    conditions.append("cleaned_brand IS NOT NULL")
    conditions.append("TRIM(cleaned_brand) <> ''")

    # For availability calculation, we need conditions WITHOUT availability filter
    conditions_for_availability = conditions.copy()

    # For product pricing, add availability filter
    conditions.append("LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')")

    where_clause_for_availability = f"WHERE {' AND '.join(conditions_for_availability)}" if conditions_for_availability else ""

    # Global latest date across the whole dataset (independent of filters), so
    # "Last Updated" always reflects the freshest data in the DB, not just this filter combo
    global_latest_date_query = f"""
    SELECT MAX(DATE_TRUNC('day', ({date_expr}))::date) AS latest_date
    FROM {DEFAULT_TABLE_REF}
    WHERE ({date_expr}) IS NOT NULL;
    """
    latest_df = db.query(global_latest_date_query)
    latest_date = (latest_df.to_dicts()[0] or {}).get("latest_date")

    # For base CTE: use conditions WITH availability filter for product pricing
    full_where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # For availability calculation: use conditions WITHOUT availability filter
    full_where_for_availability = where_clause_for_availability

    # Get region remap SQL
    region_remap = _region_remap_sql("region")

    # Match brand-sales exactly: include DATE in grouping, filter to latest date AFTER key_daily
    query = """
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price,
            availability
        FROM {DEFAULT_TABLE_REF}
        {full_where}
    ),
    latest_date AS (
        SELECT '{global_latest_date}'::date AS date
    ),
    retailer_daily AS (
        SELECT
            date, brand, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    latest AS (
        SELECT *
        FROM key_daily
        WHERE date = (SELECT date FROM latest_date)
    ),
    base_unfiltered AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            availability
        FROM {DEFAULT_TABLE_REF}
        {full_where_for_availability}
    ),
    promo_stats AS (
        SELECT
            ROUND(100.0 * COUNT(*) FILTER (WHERE promo_price < regular_price) / NULLIF(COUNT(*)::numeric, 0), 2) AS promo_percentage,
            ROUND(AVG(CASE WHEN regular_price > 0 THEN (100.0 * (regular_price - promo_price) / regular_price) ELSE NULL END)::numeric, 2) AS avg_promo_pct
        FROM latest
    ),
    availability_stats AS (
        SELECT
            ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(TRIM(COALESCE(availability::text, ''))) = 'yes') / NULLIF(COUNT(*)::numeric, 0), 2) AS availability_pct,
            COUNT(*) FILTER (WHERE LOWER(TRIM(COALESCE(availability::text, ''))) <> 'yes') AS out_of_stock_count
        FROM base_unfiltered
        WHERE date = (SELECT date FROM latest_date)
    )
    SELECT
        COUNT(*) total_skus,
        COUNT(DISTINCT brand) total_brands,
        ROUND(AVG(regular_price)::numeric, 2) avg_original_price,
        ROUND(AVG(promo_price)::numeric, 2) avg_discounted_price,
        ROUND((AVG(regular_price) - AVG(promo_price))::numeric, 2) list_vs_promo_gap,
        (SELECT promo_percentage FROM promo_stats) as skus_on_promotion_percentage,
        (SELECT avg_promo_pct FROM promo_stats) as avg_discount_pct,
        (SELECT availability_pct FROM availability_stats) as availability_percentage,
        (SELECT out_of_stock_count FROM availability_stats) as out_of_stock_skus,
        0 as max_discount_pct,
        0 as min_discount_pct
    FROM latest;
    """.format(
        date_expr=date_expr,
        list_col=list_col,
        promo_col=promo_col,
        full_where=full_where,
        full_where_for_availability=full_where_for_availability,
        region_remap=region_remap,
        DEFAULT_TABLE_REF=DEFAULT_TABLE_REF,
        global_latest_date=latest_date,
    )

    df = db.query(query)
    data = df.to_dicts()[0] if df.height > 0 else {}

    row = data
    pricing_currency = _get_pricing_currency(filters)
    row["pricing_currency"] = pricing_currency
    row["latest_data_point_used_date"] = latest_date

    # Calculate price difference
    avg_original = row.get("avg_original_price")
    avg_discounted = row.get("avg_discounted_price")
    if avg_original and avg_discounted:
        row["price_difference"] = round(float(avg_original) - float(avg_discounted), 2)
    else:
        row["price_difference"] = None

    if latest_date:
        row["latest_data_point"] = {
            "week_start": latest_date,
            "week_end": latest_date,
            "total_skus": row.get("total_skus"),
            "total_brands": row.get("total_brands"),
            "avg_original_price": row.get("avg_original_price"),
            "avg_discounted_price": row.get("avg_discounted_price"),
            "avg_discount_pct": row.get("avg_discount_pct"),
            "max_discount_pct": row.get("max_discount_pct"),
            "min_discount_pct": row.get("min_discount_pct"),
            "pricing_currency": pricing_currency,
        }
    else:
        row["latest_data_point"] = None

    # KPI highlights: biggest price move and biggest visibility move across hero SKUs
    try:
        hero_result = await fetch_hero_sku_tracker(filters)
        all_sku_rows: list[dict] = []
        for section in hero_result.get("sections", []):
            all_sku_rows.extend(section.get("rows", []))

        price_candidates = [r for r in all_sku_rows if r.get("delta_eff_pct") is not None]
        if price_candidates:
            best_p = max(price_candidates, key=lambda r: abs(r["delta_eff_pct"]))
            is_promo_driven = (
                best_p.get("promo_price") is not None
                and best_p.get("regular_price") is not None
                and float(best_p["promo_price"]) < float(best_p["regular_price"])
            )
            row["biggest_price_move"] = {
                "sku_label":      best_p["sku_label"],
                "brand":          best_p["brand"],
                "pack_type":      best_p["pack_type"],
                "pack_size":      best_p["pack_size"],
                "delta_eff_pct":  best_p["delta_eff_pct"],
                "is_promo_driven": is_promo_driven,
                "price_flag":     best_p["price_flag"],
            }
        else:
            row["biggest_price_move"] = None

        vis_candidates = [r for r in all_sku_rows if r.get("delta_top10_pt") is not None]
        if vis_candidates:
            best_v = max(vis_candidates, key=lambda r: abs(r["delta_top10_pt"]))
            row["biggest_visibility_move"] = {
                "sku_label":          best_v["sku_label"],
                "brand":              best_v["brand"],
                "pack_type":          best_v["pack_type"],
                "pack_size":          best_v["pack_size"],
                "delta_top10_pt":     best_v["delta_top10_pt"],
                "delta_first_page_pt": best_v["delta_first_page_pt"],
                "vis_flag":           best_v["vis_flag"],
            }
        else:
            row["biggest_visibility_move"] = None
    except Exception:
        row["biggest_price_move"] = None
        row["biggest_visibility_move"] = None

    return row


async def fetch_distribution():
    query = """
    SELECT
        'brand' AS type,
        cleaned_brand AS name,
        COUNT(*) AS sku_count
    FROM {DEFAULT_TABLE_REF}
    GROUP BY cleaned_brand

    UNION ALL

    SELECT
        'format',
        pack_format,
        COUNT(*)
    FROM {DEFAULT_TABLE_REF}
    GROUP BY pack_format

    UNION ALL

    SELECT
        'size',
        quantity,
        COUNT(*)
    FROM {DEFAULT_TABLE_REF}
    GROUP BY quantity;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_pricing(filters: dict | None = None):
    list_col, promo_col = _get_price_columns(filters)
    pricing_currency = _get_pricing_currency(filters)
    query = """
    SELECT
        cleaned_brand AS brand,
        pack_format,
        quantity,
        {list_col} AS listing_price,
        {promo_col} AS promo_price,
        discount_percentage
    FROM {DEFAULT_TABLE_REF}
    ORDER BY cleaned_brand, discount_percentage DESC;
    """.format(list_col=list_col, promo_col=promo_col, DEFAULT_TABLE_REF=DEFAULT_TABLE_REF)

    df = db.query(query)
    rows = df.to_dicts()
    for row in rows:
        row["pricing_currency"] = pricing_currency
    return rows


async def fetch_availability():
    query = """
    SELECT
        ROUND(100 * AVG((availability = 'yes')::int)::numeric, 2) AS availability_percentage,
        ROUND(100 * AVG((features_in_top10 = 'yes')::int)::numeric, 2) AS top10_percentage,
        ROUND(100 * AVG((features_on_first_page = 'yes')::int)::numeric, 2) AS first_page_percentage
    FROM {DEFAULT_TABLE_REF};
    """

    df = db.query(query)
    return df.to_dicts()[0]


async def fetch_format_insights():
    query = """
    SELECT
        pack_format,
        ROUND(AVG(original_price_local)::numeric, 2) AS avg_original_price,
        ROUND(AVG(discounted_price_local)::numeric, 2) AS avg_discounted_price,
        ROUND(AVG(discount_percentage)::numeric, 2) AS avg_discount_by_format
    FROM {DEFAULT_TABLE_REF}
    GROUP BY pack_format
    ORDER BY pack_format;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_products():
    query = """
    SELECT
        platform,
        cleaned_brand AS brand,
        type,
        quantity,
        units,
        pack_format,
        original_price_local,
        original_price_usd,
        discounted_price_local,
        discounted_price_usd,
        currency,
        discount_percentage,
        link,
        image_link,
        availability,
        features_in_top10,
        features_on_first_page
    FROM {DEFAULT_TABLE_REF}
    ORDER BY cleaned_brand, pack_format;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_export(
    filters: dict | None = None,
    page: int = 1,
    limit: int = 50,
):
    page = max(1, int(page))
    limit = max(1, min(int(limit), 100))
    offset = (page - 1) * limit

    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)

    filter_conditions = _build_common_filter_conditions(filters)
    specific_date = (filters or {}).get("date")
    if specific_date:
        specific_date = _validate_iso_date(specific_date)
    if specific_date:
        filter_conditions = list(filter_conditions) + [
            f"DATE_TRUNC('day', ({date_expr}))::date = '{specific_date}'::date"
        ]
    where_clause = (
        "WHERE " + " AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    comp_select = "comp" if _default_table_has_column("comp") else "NULL::text AS comp"
    region_remap = _region_remap_sql("region")
    query = f"""
    SELECT
        DATE_TRUNC('day', ({date_expr}))::date AS date,
        CASE WHEN LOWER(TRIM(country)) IN ('baharain') THEN 'Bahrain' ELSE TRIM(country) END AS market,
        platform AS retailer,
        {region_remap} AS region,
        segment,
        {comp_select},
        cleaned_brand AS brand,
        sub_type,
        type,
        quantity,
        units,
        pack_format,
        original_price_local,
        original_price_usd,
        discounted_price_local,
        discounted_price_usd,
        currency,
        discount_percentage,
        availability,
        features_in_top10,
        features_on_first_page,
        link,
        image_link
    FROM {DEFAULT_TABLE_REF}
    {where_clause}
    ORDER BY date DESC, cleaned_brand, platform, region, pack_format
    LIMIT {limit}
    OFFSET {offset};
    """

    count_query = f"""
    SELECT COUNT(*) AS total_count
    FROM {DEFAULT_TABLE_REF}
    {where_clause};
    """

    df = db.query(query)
    count_df = db.query(count_query)
    total_count = int((count_df.to_dicts()[0] or {}).get("total_count") or 0)

    return {
        "rows": df.to_dicts(),
        "total_count": total_count,
        "page": page,
        "limit": limit,
    }


async def fetch_brand_sales(filters: dict | None = None):
    table_ref = DEFAULT_TABLE_REF

    date_cols = _default_table_columns()
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in date_cols else ""
    )
    date_column = next(
        (
            c
            for c in [
                "date",
                "snapshot_date",
                "captured_at",
                "created_at",
                "updated_at",
                "scraped_at",
                "crawl_date",
                "ingested_at",
                "timestamp",
            ]
            if c in date_cols
        ),
        None,
    )
    if not date_column:
        raise ValueError(
            f"No supported date column found in {table_ref}. "
            "Expected one of: date, snapshot_date, captured_at, created_at, "
            "updated_at, scraped_at, crawl_date, ingested_at, timestamp"
        )

    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    pricing_currency = _get_pricing_currency(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    specific_date = (filters or {}).get("date")
    if specific_date:
        specific_date = _validate_iso_date(specific_date)
    # Strict: a requested date must resolve to exactly that date, never an
    # earlier date silently substituted because nothing was "available" here.
    latest_date_cte = (
        f"SELECT '{specific_date}'::date AS date"
        if specific_date
        else "SELECT MAX(date) AS date FROM base"
    )

    retailer_query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {_region_remap_sql("region")} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          {and_filters}{avail_filter}
    ),
    latest_date AS (
        {latest_date_cte}
    ),
    key_daily AS (
        SELECT
            date,
            brand,
            retailer,
            region,
            pack_type,
            pack_size,
            pack,
            sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    latest AS (
        SELECT *
        FROM key_daily
        WHERE date = (SELECT date FROM latest_date)
    ),
    previous_date AS (
        SELECT MAX(date) AS date FROM key_daily
        WHERE date <= ((SELECT date FROM latest_date) - INTERVAL '7 day')
    ),
    previous AS (
        SELECT * FROM key_daily
        WHERE date = (SELECT date FROM previous_date)
    )
    SELECT
        l.brand,
        l.pack_type,
        l.pack_size,
        l.pack,
        l.sub_type,
        l.retailer,
        l.region,
        l.regular_price,
        ROUND((l.regular_price - p.regular_price)::numeric, 2) AS regular_price_diff_vs_previous_week,
        l.promo_price,
        ROUND((l.promo_price - p.promo_price)::numeric, 2) AS promo_price_diff_vs_previous_week,
        ROUND(
            CASE WHEN l.regular_price > 0
                THEN (100.0 * (l.regular_price - l.promo_price) / l.regular_price)
                ELSE NULL
            END::numeric,
            2
        ) AS promo_pct,
        ROUND(
            (
                CASE WHEN l.regular_price > 0
                    THEN (100.0 * (l.regular_price - l.promo_price) / l.regular_price)
                    ELSE NULL
                END
                -
                CASE WHEN p.regular_price > 0
                    THEN (100.0 * (p.regular_price - p.promo_price) / p.regular_price)
                    ELSE NULL
                END
            )::numeric,
            2
        ) AS promo_pct_diff_vs_previous_week,
        (SELECT date FROM latest_date) AS latest_data_point_used_date,
        p.date AS previous_week_data_point_used_date
    FROM latest l
    LEFT JOIN previous p
      ON l.brand = p.brand
     AND l.retailer = p.retailer
     AND COALESCE(l.region, '') = COALESCE(p.region, '')
     AND COALESCE(l.pack_type, '') = COALESCE(p.pack_type, '')
     AND COALESCE(l.pack_size, '') = COALESCE(p.pack_size, '')
     AND COALESCE(l.pack, -1) = COALESCE(p.pack, -1)
     AND COALESCE(l.sub_type, '') = COALESCE(p.sub_type, '')
    ORDER BY l.brand, l.retailer, l.region, l.pack_type, l.pack_size, l.pack, l.sub_type;
    """

    region_query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {_region_remap_sql("region")} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND platform IS NOT NULL
          AND TRIM(platform) <> ''
          AND TRIM(region) <> ''
          {and_filters}{avail_filter}
    ),
    latest_date AS (
        {latest_date_cte}
    ),
    retailer_daily AS (
        SELECT
            date, brand, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date,
            brand,
            region,
            pack_type,
            pack_size,
            pack,
            sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    latest AS (
        SELECT *
        FROM key_daily
        WHERE date = (SELECT date FROM latest_date)
    ),
    previous_date AS (
        SELECT MAX(date) AS date FROM key_daily
        WHERE date <= ((SELECT date FROM latest_date) - INTERVAL '7 day')
    ),
    previous AS (
        SELECT * FROM key_daily
        WHERE date = (SELECT date FROM previous_date)
    )
    SELECT
        l.brand,
        l.pack_type,
        l.pack_size,
        l.pack,
        l.sub_type,
        l.region,
        l.regular_price,
        ROUND((l.regular_price - p.regular_price)::numeric, 2) AS regular_price_diff_vs_previous_week,
        l.promo_price,
        ROUND((l.promo_price - p.promo_price)::numeric, 2) AS promo_price_diff_vs_previous_week,
        ROUND(
            CASE WHEN l.regular_price > 0
                THEN (100.0 * (l.regular_price - l.promo_price) / l.regular_price)
                ELSE NULL
            END::numeric,
            2
        ) AS promo_pct,
        ROUND(
            (
                CASE WHEN l.regular_price > 0
                    THEN (100.0 * (l.regular_price - l.promo_price) / l.regular_price)
                    ELSE NULL
                END
                -
                CASE WHEN p.regular_price > 0
                    THEN (100.0 * (p.regular_price - p.promo_price) / p.regular_price)
                    ELSE NULL
                END
            )::numeric,
            2
        ) AS promo_pct_diff_vs_previous_week
    FROM latest l
    LEFT JOIN previous p
      ON l.brand = p.brand
     AND l.region = p.region
     AND COALESCE(l.pack_type, '') = COALESCE(p.pack_type, '')
     AND COALESCE(l.pack_size, '') = COALESCE(p.pack_size, '')
     AND COALESCE(l.pack, -1) = COALESCE(p.pack, -1)
     AND COALESCE(l.sub_type, '') = COALESCE(p.sub_type, '')
    ORDER BY l.brand, l.region, l.pack_type, l.pack_size, l.pack, l.sub_type;
    """

    retailer_df, region_df = await asyncio.gather(
        asyncio.to_thread(db.query, retailer_query),
        asyncio.to_thread(db.query, region_query),
    )
    rows = retailer_df.to_dicts()
    region_rows = region_df.to_dicts()

    focus_brands = [
        "heineken",
        "kingfisher",
        "amstel",
        "tiger",
        "birra moretti",
    ]
    trading_brands = [
        "brewdog",
        "kirin",
        "strongbow",
        "sol",
        "paulaner",
        "estrella",
        "desperados",
        "thatchers",
        "almazza",
        "noam",
    ]
    competition_brands = [
        "corona",
        "stella",
        "stella artois",
        "peroni",
    ]

    def _norm_brand(value: str) -> str:
        v = (value or "").strip().lower()
        if v == "stella artois":
            return "stella"
        return v

    def _brand_bucket_and_rank(brand_name: str) -> tuple[int, int, str]:
        norm = _norm_brand(brand_name)
        if norm in focus_brands:
            return (0, focus_brands.index(norm), norm)
        if norm in trading_brands:
            return (1, trading_brands.index(norm), norm)
        if norm in competition_brands:
            idx = [
                "corona",
                "stella",
                "peroni",
            ].index("stella" if norm == "stella artois" else norm)
            return (2, idx, norm)
        return (3, 9999, norm)

    def _pack_size_sort_key(value):
        s = str(value or "").strip().lower()
        if not s:
            return (9999, "zz")
        num = ""
        unit = ""
        for ch in s:
            if ch.isdigit() or ch == ".":
                num += ch
            elif ch.isalpha():
                unit += ch
        try:
            n = float(num) if num else 9999.0
        except ValueError:
            n = 9999.0
        unit_rank = 0 if unit == "ml" else 1 if unit == "cl" else 2 if unit == "l" else 3
        if unit == "ml":
            n = n / 10.0
        elif unit == "l":
            n = n * 100.0
        return (n, unit_rank, s)

    _sales_override_keys = {k.lower() for k in RETAILER_REGION_OVERRIDE}

    def _sales_retailer_display(platform: str, region: str) -> str:
        if platform.lower() in _sales_override_keys:
            return _make_combined_retailer_display(platform, RETAILER_REGION_OVERRIDE[platform.lower()])
        return _make_retailer_display(platform, region)

    retailers = sorted(
        {
            _sales_retailer_display((r.get("retailer") or "").strip(), (r.get("region") or "").strip())
            for r in rows if (r.get("retailer") or "").strip()
        },
        key=_retailer_sort_key,
    )
    regions = sorted({(r.get("region") or "").strip() for r in region_rows if (r.get("region") or "").strip()})
    pivot = {}
    latest_used_date = specific_date or None
    previous_used_date = None
    for row in rows:
        brand = _norm_brand((row.get("brand") or "").strip())
        pack_type = (row.get("pack_type") or "").strip()
        pack_size = (row.get("pack_size") or "").strip()
        pack = row.get("pack")
        sub_type = (row.get("sub_type") or "").strip()
        platform = (row.get("retailer") or "").strip()
        region = (row.get("region") or "").strip()
        retailer = _sales_retailer_display(platform, region)
        if not brand or not retailer:
            continue
        latest_used_date = row.get("latest_data_point_used_date") or latest_used_date
        previous_used_date = row.get("previous_week_data_point_used_date") or previous_used_date

        key = (brand, pack_type, pack_size, pack, sub_type)
        if key not in pivot:
            pivot[key] = {
                "brand": brand,
                "pack_type": pack_type,
                "pack_size": pack_size,
                "pack": pack,
                "sub_type": sub_type,
                "pricing_currency": pricing_currency,
                "retailers": {},
                "regions": {},
            }
        pivot[key]["retailers"][retailer] = {
            "regular_price": row.get("regular_price"),
            "regular_price_diff_vs_previous_week": row.get("regular_price_diff_vs_previous_week"),
            "promo_price": row.get("promo_price"),
            "promo_price_diff_vs_previous_week": row.get("promo_price_diff_vs_previous_week"),
            "promo_pct": row.get("promo_pct"),
            "promo_pct_diff_vs_previous_week": row.get("promo_pct_diff_vs_previous_week"),
            "has_data": True,
        }

    for row in region_rows:
        brand = _norm_brand((row.get("brand") or "").strip())
        pack_type = (row.get("pack_type") or "").strip()
        pack_size = (row.get("pack_size") or "").strip()
        pack = row.get("pack")
        sub_type = (row.get("sub_type") or "").strip()
        region = (row.get("region") or "").strip()
        if not brand or not region:
            continue
        key = (brand, pack_type, pack_size, pack, sub_type)
        if key not in pivot:
            pivot[key] = {
                "brand": brand,
                "pack_type": pack_type,
                "pack_size": pack_size,
                "pack": pack,
                "sub_type": sub_type,
                "pricing_currency": pricing_currency,
                "retailers": {},
                "regions": {},
            }
        pivot[key]["regions"][region] = {
            "regular_price": row.get("regular_price"),
            "regular_price_diff_vs_previous_week": row.get("regular_price_diff_vs_previous_week"),
            "promo_price": row.get("promo_price"),
            "promo_price_diff_vs_previous_week": row.get("promo_price_diff_vs_previous_week"),
            "promo_pct": row.get("promo_pct"),
            "promo_pct_diff_vs_previous_week": row.get("promo_pct_diff_vs_previous_week"),
            "has_data": True,
        }

    pivot_rows = list(pivot.values())
    for item in pivot_rows:
        item["brand_group"] = (
            "FOCUS BRANDS"
            if _brand_bucket_and_rank(item["brand"])[0] == 0
            else "TRADING BRANDS"
            if _brand_bucket_and_rank(item["brand"])[0] == 1
            else "COMPETITION BRANDS"
            if _brand_bucket_and_rank(item["brand"])[0] == 2
            else "AND MORE"
        )
        for retailer in retailers:
            item["retailers"].setdefault(
                retailer,
                {
                    "regular_price": None,
                    "regular_price_diff_vs_previous_week": None,
                    "promo_price": None,
                    "promo_price_diff_vs_previous_week": None,
                    "promo_pct": None,
                    "promo_pct_diff_vs_previous_week": None,
                    "has_data": False,
                },
            )
        for region in regions:
            item["regions"].setdefault(
                region,
                {
                    "regular_price": None,
                    "regular_price_diff_vs_previous_week": None,
                    "promo_price": None,
                    "promo_price_diff_vs_previous_week": None,
                    "promo_pct": None,
                    "promo_pct_diff_vs_previous_week": None,
                    "has_data": False,
                },
            )

    pivot_rows.sort(
        key=lambda x: (
            _brand_bucket_and_rank(x["brand"]),
            x.get("pack_type") or "",
            _pack_size_sort_key(x.get("pack_size")),
            x.get("pack") if x.get("pack") is not None else 9999,
            x.get("sub_type") or "",
        )
    )

    return {
        "source_table": "plaformsV2",
        "latest_data_point_used_date": latest_used_date,
        "previous_week_data_point_used_date": previous_used_date,
        "retailers": retailers,
        "regions": regions,
        "rows": pivot_rows,
    }


REGION_ABBREV: dict[str, str] = {
    "dubai": "D",
    "abu dhabi": "AD",
    "other emirates": "NE",
    "northern emirates": "NE",
    "bahrain": "B",
}

REGION_SORT_RANK: dict[str, int] = {
    "D": 1,
    "AD": 2,
    "NE": 3,
    "B": 4,
}


def _make_retailer_display(platform: str, region: str = "") -> str:
    if not region:
        return platform
    abbrev = REGION_ABBREV.get(region.strip().lower(), region)
    return f"{platform} ({abbrev})"


def _make_combined_retailer_display(platform: str, regions: list[str]) -> str:
    abbrevs = sorted(
        [REGION_ABBREV.get(r.strip().lower(), r) for r in regions if r],
        key=lambda a: REGION_SORT_RANK.get(a, 99),
    )
    suffix = " ".join(f"({a})" for a in abbrevs)
    return f"{platform} {suffix}" if suffix else platform


def _platform_key(display_name: str) -> str:
    """Strip region suffix like 'citydrinks (D)' → 'citydrinks' for capacity map lookup."""
    if "(" in display_name:
        return display_name[:display_name.rfind("(")].strip().lower().replace(" ", "")
    return display_name.lower().replace(" ", "")


def _retailer_sort_key(display_name: str) -> tuple:
    first_open = display_name.find("(")
    if first_open != -1:
        first_close = display_name.find(")", first_open)
        first_abbrev = display_name[first_open + 1:first_close].strip() if first_close != -1 else ""
        rank = REGION_SORT_RANK.get(first_abbrev, 99)
    else:
        rank = 99
    platform = display_name.split("(")[0].strip()
    return (rank, platform)


RETAILER_REGION_OVERRIDE: dict[str, list[str]] = {
    "citydrinks": ["Abu Dhabi"],
    "centaurusint": ["Abu Dhabi"],
}

RETAILER_FIRST_PAGE_CAPACITY: dict[str, int] = {
    "africaneasternonline": 90,
    "africanandeastern": 20,
    "bdutyfree": 36,
    "bmmishops": 12,
    "centaurusint": 20,
    "citydrinks": 48,
    "dubaidutyfree": 20,
    "gbiexpress": 16,
    "gmp": 12,
    "highspiritsuae": 30,
    "jmkcellars": 12,
    "mmihomedelivery": 25,
    "nhsc": 16,
    "royalspirit": 36,
    "spinneysauh": 12,
    "supercellar": 50,
    "thebottlestore": 15,
    "unisatgt": 45,
    "windmillgt": 30,
}


async def fetch_brand_visibility_by_retailer(filters: dict | None = None):
    table_ref = DEFAULT_TABLE_REF

    available_columns = _default_table_columns()
    date_column = next(
        (
            c
            for c in [
                "date",
                "snapshot_date",
                "captured_at",
                "created_at",
                "updated_at",
                "scraped_at",
                "crawl_date",
                "ingested_at",
                "timestamp",
            ]
            if c in available_columns
        ),
        None,
    )
    if not date_column:
        raise ValueError(
            f"No supported date column found in {table_ref}. "
            "Expected one of: date, snapshot_date, captured_at, created_at, "
            "updated_at, scraped_at, crawl_date, ingested_at, timestamp"
        )
    date_expr = _get_trend_date_expression(date_column)
    region_source_column = (
        "region"
        if "region" in available_columns
        else "country"
        if "country" in available_columns
        else None
    )
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in available_columns else ""
    )
    specific_date = (filters or {}).get("date")
    if specific_date:
        specific_date = _validate_iso_date(specific_date)
    # Strict: a requested date must resolve to exactly that date, never an
    # earlier date silently substituted because nothing was "available" here.
    latest_date_cte = (
        f"SELECT '{specific_date}'::date AS date"
        if specific_date
        else "SELECT MAX(date) AS date FROM base"
    )

    retailer_query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {_region_remap_sql(region_source_column) if region_source_column else "''"} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            LOWER(TRIM(COALESCE(features_in_top10::text, ''))) AS features_in_top10,
            LOWER(TRIM(COALESCE(features_on_first_page::text, ''))) AS features_on_first_page
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND platform IS NOT NULL
          {and_filters}{avail_filter}
    ),
    latest_date AS (
        {latest_date_cte}
    ),
    previous_week_date AS (
        SELECT MAX(date) AS date
        FROM base
        WHERE date <= ((SELECT date FROM latest_date) - INTERVAL '7 day')
    ),
    latest AS (
        SELECT
            brand,
            retailer,
            region,
            pack_type,
            pack_size,
            pack,
            sub_type,
            BOOL_OR(features_in_top10 IN ('yes', 'true', '1', 'y')) AS in_top10,
            BOOL_OR(features_on_first_page IN ('yes', 'true', '1', 'y')) AS on_first_page
        FROM base
        WHERE date = (SELECT date FROM latest_date)
        GROUP BY brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    previous AS (
        SELECT
            brand,
            retailer,
            region,
            pack_type,
            pack_size,
            pack,
            sub_type,
            BOOL_OR(features_in_top10 IN ('yes', 'true', '1', 'y')) AS in_top10,
            BOOL_OR(features_on_first_page IN ('yes', 'true', '1', 'y')) AS on_first_page
        FROM base
        WHERE date = (SELECT date FROM previous_week_date)
        GROUP BY brand, retailer, region, pack_type, pack_size, pack, sub_type
    )
    SELECT
        l.brand,
        l.retailer,
        l.region,
        l.pack_type,
        l.pack_size,
        l.pack,
        l.sub_type,
        l.in_top10,
        l.on_first_page,
        COALESCE(p.in_top10, FALSE) AS prev_in_top10,
        COALESCE(p.on_first_page, FALSE) AS prev_on_first_page,
        (SELECT date FROM latest_date) AS latest_data_point_used_date,
        (SELECT date FROM previous_week_date) AS previous_week_data_point_used_date
    FROM latest l
    LEFT JOIN previous p
      ON l.brand = p.brand
     AND l.retailer = p.retailer
     AND COALESCE(l.region, '') = COALESCE(p.region, '')
     AND COALESCE(l.pack_type, '') = COALESCE(p.pack_type, '')
     AND COALESCE(l.pack_size, '') = COALESCE(p.pack_size, '')
     AND COALESCE(l.pack, -1) = COALESCE(p.pack, -1)
     AND COALESCE(l.sub_type, '') = COALESCE(p.sub_type, '')
    ORDER BY l.brand, l.pack_type, l.pack_size, l.pack, l.sub_type, l.retailer, l.region;
    """

    region_rows: list[dict] = []
    if region_source_column:
        region_query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            {_region_remap_sql(region_source_column)} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            LOWER(TRIM(COALESCE(features_in_top10::text, ''))) AS features_in_top10,
            LOWER(TRIM(COALESCE(features_on_first_page::text, ''))) AS features_on_first_page
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND platform IS NOT NULL
          AND TRIM(platform) <> ''
          AND TRIM({region_source_column}) <> ''
          {and_filters}{avail_filter}
    ),
    latest_date AS (
        {latest_date_cte}
    ),
    previous_week_date AS (
        SELECT MAX(date) AS date
        FROM base
        WHERE date <= ((SELECT date FROM latest_date) - INTERVAL '7 day')
    ),
    latest AS (
        SELECT
            brand,
            region,
            pack_type,
            pack_size,
            pack,
            sub_type,
            BOOL_OR(features_in_top10 IN ('yes', 'true', '1', 'y')) AS in_top10,
            BOOL_OR(features_on_first_page IN ('yes', 'true', '1', 'y')) AS on_first_page
        FROM base
        WHERE date = (SELECT date FROM latest_date)
        GROUP BY brand, region, pack_type, pack_size, pack, sub_type
    ),
    previous AS (
        SELECT
            brand,
            region,
            pack_type,
            pack_size,
            pack,
            sub_type,
            BOOL_OR(features_in_top10 IN ('yes', 'true', '1', 'y')) AS in_top10,
            BOOL_OR(features_on_first_page IN ('yes', 'true', '1', 'y')) AS on_first_page
        FROM base
        WHERE date = (SELECT date FROM previous_week_date)
        GROUP BY brand, region, pack_type, pack_size, pack, sub_type
    )
    SELECT
        l.brand,
        l.region,
        l.pack_type,
        l.pack_size,
        l.pack,
        l.sub_type,
        l.in_top10,
        l.on_first_page,
        COALESCE(p.in_top10, FALSE) AS prev_in_top10,
        COALESCE(p.on_first_page, FALSE) AS prev_on_first_page,
        (SELECT date FROM latest_date) AS latest_data_point_used_date,
        (SELECT date FROM previous_week_date) AS previous_week_data_point_used_date
    FROM latest l
    LEFT JOIN previous p
      ON l.brand = p.brand
     AND l.region = p.region
     AND COALESCE(l.pack_type, '') = COALESCE(p.pack_type, '')
     AND COALESCE(l.pack_size, '') = COALESCE(p.pack_size, '')
     AND COALESCE(l.pack, -1) = COALESCE(p.pack, -1)
     AND COALESCE(l.sub_type, '') = COALESCE(p.sub_type, '')
    ORDER BY l.brand, l.pack_type, l.pack_size, l.pack, l.sub_type, l.region;
    """
        rr_query = f"""
        SELECT DISTINCT
            TRIM(platform) AS retailer,
            TRIM({region_source_column}) AS region
        FROM {table_ref}
        WHERE platform IS NOT NULL
          AND TRIM(platform) <> ''
          AND {region_source_column} IS NOT NULL
          AND TRIM({region_source_column}) <> ''
          {and_filters}{avail_filter}
        """
        region_df, rr_df, retailer_df = await asyncio.gather(
            asyncio.to_thread(db.query, region_query),
            asyncio.to_thread(db.query, rr_query),
            asyncio.to_thread(db.query, retailer_query),
        )
        region_rows = region_df.to_dicts()
        retailer_region_rows = rr_df.to_dicts()
    else:
        retailer_region_rows = []
        retailer_df = await asyncio.to_thread(db.query, retailer_query)

    # apply hardcoded region overrides: replace DB-derived regions with override list
    override_keys = {k.lower() for k in RETAILER_REGION_OVERRIDE}
    retailer_region_rows = [
        rr for rr in retailer_region_rows
        if (rr.get("retailer") or "").strip().lower() not in override_keys
    ]
    for platform, override_regions in RETAILER_REGION_OVERRIDE.items():
        for region in override_regions:
            retailer_region_rows.append({"retailer": platform, "region": region})

    region_retailers: dict[str, list[str]] = {}
    for rr in retailer_region_rows:
        reg = (rr.get("region") or "").strip()
        ret = (rr.get("retailer") or "").strip()
        if reg and ret:
            region_retailers.setdefault(reg, [])
            if ret not in region_retailers[reg]:
                region_retailers[reg].append(ret)

    rows = retailer_df.to_dicts()

    focus_brands = ["heineken", "kingfisher", "amstel", "tiger", "birra moretti"]
    trading_brands = [
        "brewdog",
        "kirin",
        "strongbow",
        "sol",
        "paulaner",
        "estrella",
        "desperados",
        "thatchers",
        "almazza",
        "noam",
    ]
    competition_brands = ["corona", "stella", "stella artois", "peroni"]

    def _norm_brand(value: str) -> str:
        v = (value or "").strip().lower()
        return "stella" if v == "stella artois" else v

    def _brand_bucket_and_rank(brand_name: str) -> tuple[int, int, str]:
        norm = _norm_brand(brand_name)
        if norm in focus_brands:
            return (0, focus_brands.index(norm), norm)
        if norm in trading_brands:
            return (1, trading_brands.index(norm), norm)
        if norm in competition_brands:
            ordered = ["corona", "stella", "peroni"]
            return (2, ordered.index("stella" if norm == "stella artois" else norm), norm)
        return (3, 9999, norm)

    def _pack_size_sort_key(value):
        s = str(value or "").strip().lower()
        if not s:
            return (9999, "zz")
        num = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        unit = "".join(ch for ch in s if ch.isalpha())
        try:
            n = float(num) if num else 9999.0
        except ValueError:
            n = 9999.0
        if unit == "ml":
            n = n / 10.0
        elif unit == "l":
            n = n * 100.0
        unit_rank = 0 if unit == "ml" else 1 if unit == "cl" else 2 if unit == "l" else 3
        return (n, unit_rank, s)

    # build override display names: combined brackets for hardcoded retailers
    _override_keys = {k.lower() for k in RETAILER_REGION_OVERRIDE}

    def _vis_retailer_display(platform: str, region: str) -> str:
        if platform.lower() in _override_keys:
            override_regions = RETAILER_REGION_OVERRIDE[platform.lower()]
            return _make_combined_retailer_display(platform, override_regions)
        return _make_retailer_display(platform, region)

    retailers = sorted(
        {
            _vis_retailer_display((r.get("retailer") or "").strip(), (r.get("region") or "").strip())
            for r in rows if (r.get("retailer") or "").strip()
        },
        key=_retailer_sort_key,
    )
    regions = sorted({(r.get("region") or "").strip() for r in region_rows if (r.get("region") or "").strip()})

    # rebuild region_retailers with display names so brand_totals lookups match
    for reg, ret_list in region_retailers.items():
        region_retailers[reg] = [
            _vis_retailer_display(ret, reg) for ret in ret_list
        ]

    matrix = {}
    latest_date = specific_date or None
    previous_week_date = None
    for row in rows:
        brand = _norm_brand((row.get("brand") or "").strip())
        platform = (row.get("retailer") or "").strip()
        region = (row.get("region") or "").strip()
        retailer = _vis_retailer_display(platform, region)
        pack_type = (row.get("pack_type") or "").strip()
        pack_size = (row.get("pack_size") or "").strip()
        pack = row.get("pack")
        sub_type = (row.get("sub_type") or "").strip()
        if not brand or not retailer:
            continue
        latest_date = row.get("latest_data_point_used_date")
        previous_week_date = row.get("previous_week_data_point_used_date")

        key = (brand, pack_type, pack_size, pack, sub_type)
        if key not in matrix:
            matrix[key] = {
                "brand": brand,
                "pack_type": pack_type,
                "pack_size": pack_size,
                "pack": pack,
                "sub_type": sub_type,
                "retailers": {},
                "regions": {},
            }
        matrix[key]["retailers"][retailer] = {
            "top_10": "Y" if row.get("in_top10") else "N",
            "first_page": "Y" if row.get("on_first_page") else "N",
            "top_10_prev": "Y" if row.get("prev_in_top10") else "N",
            "first_page_prev": "Y" if row.get("prev_on_first_page") else "N",
            "has_data": True,
        }

    for row in region_rows:
        brand = _norm_brand((row.get("brand") or "").strip())
        region = (row.get("region") or "").strip()
        pack_type = (row.get("pack_type") or "").strip()
        pack_size = (row.get("pack_size") or "").strip()
        pack = row.get("pack")
        sub_type = (row.get("sub_type") or "").strip()
        if not brand or not region:
            continue
        latest_date = row.get("latest_data_point_used_date") or latest_date
        previous_week_date = row.get("previous_week_data_point_used_date") or previous_week_date

        key = (brand, pack_type, pack_size, pack, sub_type)
        if key not in matrix:
            matrix[key] = {
                "brand": brand,
                "pack_type": pack_type,
                "pack_size": pack_size,
                "pack": pack,
                "sub_type": sub_type,
                "retailers": {},
                "regions": {},
            }
        matrix[key]["regions"][region] = {
            "top_10": "Y" if row.get("in_top10") else "N",
            "first_page": "Y" if row.get("on_first_page") else "N",
            "top_10_prev": "Y" if row.get("prev_in_top10") else "N",
            "first_page_prev": "Y" if row.get("prev_on_first_page") else "N",
            "has_data": True,
        }

    matrix_rows = list(matrix.values())
    for item in matrix_rows:
        for retailer in retailers:
            item["retailers"].setdefault(
                retailer,
                {
                    "top_10": "N",
                    "first_page": "N",
                    "top_10_prev": "N",
                    "first_page_prev": "N",
                    "has_data": False,
                },
            )
        for region in regions:
            item["regions"].setdefault(
                region,
                {
                    "top_10": "N",
                    "first_page": "N",
                    "top_10_prev": "N",
                    "first_page_prev": "N",
                    "has_data": False,
                },
            )

    matrix_rows.sort(
        key=lambda x: (
            _brand_bucket_and_rank(x["brand"]),
            x.get("pack_type") or "",
            _pack_size_sort_key(x.get("pack_size")),
            x.get("pack") if x.get("pack") is not None else 9999,
            x.get("sub_type") or "",
        )
    )

    total_skus = len(matrix_rows)
    cumulative = []
    for retailer in retailers:
        top10_count = 0
        first_page_count = 0
        top10_prev_count = 0
        first_page_prev_count = 0
        retailer_skus = 0
        for item in matrix_rows:
            rv = item["retailers"].get(retailer) or {}
            if not rv.get("has_data"):
                continue
            retailer_skus += 1
            if rv.get("top_10") == "Y":
                top10_count += 1
            if rv.get("first_page") == "Y":
                first_page_count += 1
            if rv.get("top_10_prev") == "Y":
                top10_prev_count += 1
            if rv.get("first_page_prev") == "Y":
                first_page_prev_count += 1
        first_page_capacity = RETAILER_FIRST_PAGE_CAPACITY.get(_platform_key(retailer), retailer_skus)
        top10_capacity = min(10, retailer_skus) if retailer_skus else 10
        top10_share = round((top10_count / top10_capacity) * 100, 2) if top10_capacity else None
        top10_prev_share = round((top10_prev_count / top10_capacity) * 100, 2) if top10_capacity else None
        first_page_share = round((first_page_count / first_page_capacity) * 100, 2) if first_page_capacity else None
        first_page_prev_share = round((first_page_prev_count / first_page_capacity) * 100, 2) if first_page_capacity else None
        cumulative.append(
            {
                "retailer": retailer,
                "total_skus": retailer_skus,
                "first_page_capacity": first_page_capacity,
                "top_10_total": top10_count,
                "top_10_share_pct": top10_share,
                "top_10_diff_vs_pp": (
                    round(top10_share - top10_prev_share, 2)
                    if top10_share is not None and top10_prev_share is not None
                    else None
                ),
                "first_page_total": first_page_count,
                "first_page_share_pct": first_page_share,
                "first_page_diff_vs_pp": (
                    round(first_page_share - first_page_prev_share, 2)
                    if first_page_share is not None and first_page_prev_share is not None
                    else None
                ),
            }
        )

    cumulative_region = []
    for region in regions:
        region_skus = 0
        for item in matrix_rows:
            rv = item["regions"].get(region) or {}
            if not rv.get("has_data"):
                continue
            region_skus += 1
        # Sum of SKU×retailer occurrences across retailers in region (consistent with brand_totals)
        region_ret_list_agg = region_retailers.get(region, [])
        top10_sum = sum(
            sum(1 for it in matrix_rows if (it["retailers"].get(ret) or {}).get("top_10") == "Y")
            for ret in region_ret_list_agg
        )
        top10_prev_sum = sum(
            sum(1 for it in matrix_rows if (it["retailers"].get(ret) or {}).get("top_10_prev") == "Y")
            for ret in region_ret_list_agg
        )
        first_page_sum = sum(
            sum(1 for it in matrix_rows if (it["retailers"].get(ret) or {}).get("first_page") == "Y")
            for ret in region_ret_list_agg
        )
        first_page_prev_sum = sum(
            sum(1 for it in matrix_rows if (it["retailers"].get(ret) or {}).get("first_page_prev") == "Y")
            for ret in region_ret_list_agg
        )
        agg_denom = len(region_ret_list_agg) * 10
        fp_agg_denom = sum(
            RETAILER_FIRST_PAGE_CAPACITY.get(_platform_key(r), total_skus)
            for r in region_ret_list_agg
        )
        top10_share = round((top10_sum / agg_denom) * 100, 2) if agg_denom else None
        top10_prev_share = round((top10_prev_sum / agg_denom) * 100, 2) if agg_denom else None
        first_page_share = round((first_page_sum / fp_agg_denom) * 100, 2) if fp_agg_denom else None
        first_page_prev_share = round((first_page_prev_sum / fp_agg_denom) * 100, 2) if fp_agg_denom else None
        cumulative_region.append(
            {
                "region": region,
                "total_skus": region_skus,
                "top_10_total": top10_sum,
                "pct_in_top10": top10_share,
                "diff_vs_pp_in_top10": (
                    round(top10_share - top10_prev_share, 2)
                    if top10_share is not None and top10_prev_share is not None
                    else None
                ),
                "first_page_total": first_page_sum,
                "pct_on_first_page": first_page_share,
                "diff_vs_pp_on_first_page": (
                    round(first_page_share - first_page_prev_share, 2)
                    if first_page_share is not None and first_page_prev_share is not None
                    else None
                ),
            }
        )

    # Brand-level totals — computed before _prev fields are stripped from rows
    brand_groups: dict[str, list] = {}
    for item in matrix_rows:
        brand_groups.setdefault(item["brand"], []).append(item)
    seen_brands: set[str] = set()
    brand_order: list[str] = []
    for item in matrix_rows:
        b = item["brand"]
        if b not in seen_brands:
            brand_order.append(b)
            seen_brands.add(b)

    brand_totals: list[dict] = []
    for brand in brand_order:
        items = brand_groups[brand]
        num_skus = len(items)
        retailer_totals: dict[str, dict] = {}
        for retailer in retailers:
            top10_count = sum(1 for it in items if (it["retailers"].get(retailer) or {}).get("top_10") == "Y")
            fp_count = sum(1 for it in items if (it["retailers"].get(retailer) or {}).get("first_page") == "Y")
            top10_count_prev = sum(1 for it in items if (it["retailers"].get(retailer) or {}).get("top_10_prev") == "Y")
            fp_count_prev = sum(1 for it in items if (it["retailers"].get(retailer) or {}).get("first_page_prev") == "Y")
            fp_capacity = RETAILER_FIRST_PAGE_CAPACITY.get(_platform_key(retailer), total_skus)
            t10_share = round(top10_count / 10 * 100, 2)
            t10_prev_share = round(top10_count_prev / 10 * 100, 2)
            fp_share = round(fp_count / fp_capacity * 100, 2) if fp_capacity else None
            fp_prev_share = round(fp_count_prev / fp_capacity * 100, 2) if fp_capacity else None
            retailer_totals[retailer] = {
                "top10_count": top10_count,
                "top10_share_pct": t10_share,
                "top10_diff_vs_pp": round(t10_share - t10_prev_share, 2),
                "first_page_count": fp_count,
                "first_page_share_pct": fp_share,
                "first_page_diff_vs_pp": (
                    round(fp_share - fp_prev_share, 2)
                    if fp_share is not None and fp_prev_share is not None
                    else None
                ),
            }
        region_totals: dict[str, dict] = {}
        for region in regions:
            region_ret_list = region_retailers.get(region, [])
            # % in top10: retailers in region where brand has any SKU in top10 / total retailers in region
            # count SKU×retailer pairs in top10 across retailers in this region
            t10_numerator = sum(
                sum(1 for it in items if (it["retailers"].get(ret) or {}).get("top_10") == "Y")
                for ret in region_ret_list
            )
            t10_numerator_prev = sum(
                sum(1 for it in items if (it["retailers"].get(ret) or {}).get("top_10_prev") == "Y")
                for ret in region_ret_list
            )
            t10_denom = len(region_ret_list) * 10
            t10_share = round(t10_numerator / t10_denom * 100, 2) if t10_denom else None
            t10_prev_share = round(t10_numerator_prev / t10_denom * 100, 2) if t10_denom else None
            # % on 1st page: total brand SKUs on 1st page across retailers in region / sum of those retailers' capacities
            fp_numerator = sum(
                sum(1 for it in items if (it["retailers"].get(ret) or {}).get("first_page") == "Y")
                for ret in region_ret_list
            )
            fp_numerator_prev = sum(
                sum(1 for it in items if (it["retailers"].get(ret) or {}).get("first_page_prev") == "Y")
                for ret in region_ret_list
            )
            fp_denom = sum(
                RETAILER_FIRST_PAGE_CAPACITY.get(_platform_key(ret), total_skus)
                for ret in region_ret_list
            )
            fp_share = round(fp_numerator / fp_denom * 100, 2) if fp_denom else None
            fp_prev_share = round(fp_numerator_prev / fp_denom * 100, 2) if fp_denom else None
            region_totals[region] = {
                "top10_count": t10_numerator,
                "pct_in_top10": t10_share,
                "diff_vs_pp_in_top10": (
                    round(t10_share - t10_prev_share, 2)
                    if t10_share is not None and t10_prev_share is not None
                    else None
                ),
                "first_page_count": fp_numerator,
                "pct_on_first_page": fp_share,
                "diff_vs_pp_on_first_page": (
                    round(fp_share - fp_prev_share, 2)
                    if fp_share is not None and fp_prev_share is not None
                    else None
                ),
            }
        brand_totals.append({
            "brand": brand,
            "num_skus": num_skus,
            "retailers": retailer_totals,
            "regions": region_totals,
        })

    # Compute row-level region values BEFORE stripping _prev from retailers
    precomputed_regions: list[dict] = []
    for item in matrix_rows:
        item_regions: dict[str, dict] = {}
        for region in regions:
            rv = item["regions"].get(region) or {}
            region_ret_list = region_retailers.get(region, [])
            t10_denom = len(region_ret_list)
            fp_denom = len(region_ret_list)
            t10_count = sum(
                1 for r in region_ret_list
                if (item["retailers"].get(r) or {}).get("top_10") == "Y"
            )
            t10_count_prev = sum(
                1 for r in region_ret_list
                if (item["retailers"].get(r) or {}).get("top_10_prev") == "Y"
            )
            fp_count = sum(
                1 for r in region_ret_list
                if (item["retailers"].get(r) or {}).get("first_page") == "Y"
            )
            fp_count_prev = sum(
                1 for r in region_ret_list
                if (item["retailers"].get(r) or {}).get("first_page_prev") == "Y"
            )
            pct_top10 = round(t10_count / t10_denom * 100, 2) if t10_denom else 0.0
            pct_top10_prev = round(t10_count_prev / t10_denom * 100, 2) if t10_denom else 0.0
            pct_fp = round(fp_count / fp_denom * 100, 2) if fp_denom else 0.0
            pct_fp_prev = round(fp_count_prev / fp_denom * 100, 2) if fp_denom else 0.0
            item_regions[region] = {
                "pct_in_top10": pct_top10,
                "diff_vs_pp_in_top10": round(pct_top10 - pct_top10_prev, 2),
                "pct_on_first_page": pct_fp,
                "diff_vs_pp_on_first_page": round(pct_fp - pct_fp_prev, 2),
                "has_data": bool(rv.get("has_data")) or t10_count > 0 or fp_count > 0,
            }
        precomputed_regions.append(item_regions)

    # Strip _prev fields from retailers, then apply pre-computed region values
    for item, item_regions in zip(matrix_rows, precomputed_regions):
        for retailer in retailers:
            rv = item["retailers"].get(retailer) or {}
            item["retailers"][retailer] = {
                "top_10": rv.get("top_10", "N"),
                "first_page": rv.get("first_page", "N"),
                "has_data": bool(rv.get("has_data")),
            }
        item["regions"] = item_regions

    return {
        "latest_data_point_used_date": latest_date,
        "previous_week_data_point_used_date": previous_week_date,
        "total_skus": total_skus,
        "retailers": retailers,
        "regions": regions,
        "rows": matrix_rows,
        "cumulative_by_retailer": cumulative,
        "cumulative_by_region": cumulative_region,
        "brand_totals": brand_totals,
    }


async def fetch_filters(filters: dict | None = None, partial: bool = False):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    active_filters = dict(filters or {})
    base_conditions = _build_common_filter_conditions(
        active_filters,
        partial_text=partial,
    )
    where_clause = (
        "WHERE " + " AND ".join(base_conditions)
        if base_conditions
        else ""
    )
    hero_conditions = _build_common_filter_conditions(
        active_filters,
        table_alias="t",
        partial_text=partial,
    )
    hero_and_filters = (
        "\n              AND " + "\n              AND ".join(hero_conditions)
        if hero_conditions
        else ""
    )
    # sub_types and cities options must not filter by their own field — otherwise
    # once a value is selected the dropdown collapses to only that value
    filters_without_sub_type = {k: v for k, v in active_filters.items() if k != "sub_type"}
    sub_type_conditions = _build_common_filter_conditions(
        filters_without_sub_type,
        partial_text=partial,
    )
    sub_type_where_clause = (
        "WHERE " + " AND ".join(sub_type_conditions)
        if sub_type_conditions
        else ""
    )
    filters_without_city = {k: v for k, v in active_filters.items() if k != "city"}
    city_conditions = _build_common_filter_conditions(
        filters_without_city,
        partial_text=partial,
    )
    city_where_clause = (
        "WHERE " + " AND ".join(city_conditions)
        if city_conditions
        else ""
    )
    filters_without_brand = {k: v for k, v in active_filters.items() if k != "brand"}
    brand_conditions = _build_common_filter_conditions(
        filters_without_brand,
        partial_text=partial,
    )
    brand_where_clause = (
        "WHERE " + " AND ".join(brand_conditions)
        if brand_conditions
        else ""
    )

    comp_subquery = (
        f"""
        (
            SELECT ARRAY_AGG(DISTINCT NULLIF(TRIM(comp), ''))
            FILTER (WHERE NULLIF(TRIM(comp), '') IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS comp,
        """
        if _default_table_has_column("comp")
        else "ARRAY[]::text[] AS comp,"
    )
    query = f"""
    SELECT
        (
            SELECT ARRAY_AGG(DISTINCT NULLIF(CASE
                WHEN LOWER(TRIM(country)) IN ('baharain') THEN 'Bahrain'
                ELSE TRIM(country)
            END, ''))
            FILTER (WHERE NULLIF(TRIM(country), '') IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS markets,
        (
            SELECT ARRAY_AGG(DISTINCT NULLIF(TRIM(platform), ''))
            FILTER (WHERE NULLIF(TRIM(platform), '') IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS all_retailers,
        (
            SELECT ARRAY_AGG(DISTINCT NULLIF(TRIM(segment), ''))
            FILTER (WHERE NULLIF(TRIM(segment), '') IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS segments,
        {comp_subquery}
        (
            SELECT ARRAY_AGG(DISTINCT cleaned_brand)
            FILTER (WHERE cleaned_brand IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {brand_where_clause}
        ) AS brands,
        (
            SELECT ARRAY_AGG(DISTINCT pack_format)
            FILTER (WHERE pack_format IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS types,
        (
            SELECT ARRAY_AGG(DISTINCT quantity)
            FILTER (WHERE quantity IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS quantity,
        (
            SELECT ARRAY_AGG(DISTINCT units)
            FILTER (WHERE units IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS skus,
        (
            SELECT ARRAY_AGG(DISTINCT NULLIF(LOWER(TRIM(sub_type)), ''))
            FILTER (WHERE NULLIF(TRIM(sub_type), '') IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {sub_type_where_clause}
        ) AS sub_types,
        (
            SELECT ARRAY_AGG(DISTINCT NULLIF(TRIM({_region_remap_sql("region")}), ''))
            FILTER (WHERE NULLIF(TRIM({_region_remap_sql("region")}), '') IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {city_where_clause}
        ) AS cities,
        (
            SELECT ARRAY_AGG(DISTINCT DATE_TRUNC('day', ({date_expr}))::date ORDER BY DATE_TRUNC('day', ({date_expr}))::date DESC)
            FILTER (WHERE ({date_expr}) IS NOT NULL)
            FROM {DEFAULT_TABLE_REF}
            {where_clause}
        ) AS dates,
        (
            SELECT MIN(hd.date) FROM (
                SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
                FROM {DEFAULT_TABLE_REF} t
                JOIN beer_pricing_analysis.beer_sku_reference ref
                  ON LOWER(TRIM(t.cleaned_brand)) = LOWER(TRIM(ref.brand))
                 AND TRIM(t.pack_format) = TRIM(ref.pack_type)
                 AND REGEXP_REPLACE(UPPER(TRIM(t.quantity)), '\\.0([A-Z]+)$', '\\1') = UPPER(TRIM(ref.pack_size))
                 AND t.units = ref.pack
                 AND CASE
                        WHEN LOWER(TRIM(COALESCE(t.sub_type, ''))) = '' THEN 'regular'
                        ELSE LOWER(TRIM(t.sub_type))
                     END = LOWER(TRIM(ref.sub_type))
                WHERE ({date_expr}) IS NOT NULL
                  AND LOWER(TRIM(COALESCE(t.availability::text, ''))) IN ('yes', 'true', '1', 'y')
                  {hero_and_filters}
            ) hd
        ) AS hero_min_date,
        (
            SELECT MAX(hd.date) FROM (
                SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
                FROM {DEFAULT_TABLE_REF} t
                JOIN beer_pricing_analysis.beer_sku_reference ref
                  ON LOWER(TRIM(t.cleaned_brand)) = LOWER(TRIM(ref.brand))
                 AND TRIM(t.pack_format) = TRIM(ref.pack_type)
                 AND REGEXP_REPLACE(UPPER(TRIM(t.quantity)), '\\.0([A-Z]+)$', '\\1') = UPPER(TRIM(ref.pack_size))
                 AND t.units = ref.pack
                 AND CASE
                        WHEN LOWER(TRIM(COALESCE(t.sub_type, ''))) = '' THEN 'regular'
                        ELSE LOWER(TRIM(t.sub_type))
                     END = LOWER(TRIM(ref.sub_type))
                WHERE ({date_expr}) IS NOT NULL
                  AND LOWER(TRIM(COALESCE(t.availability::text, ''))) IN ('yes', 'true', '1', 'y')
                  {hero_and_filters}
            ) hd
        ) AS hero_max_date;
    """

    df = db.query(query)
    row = df.to_dicts()[0]
    raw_quantities = row.get("quantity") or []
    quantity_buckets_in_data = {
        label
        for value in raw_quantities
        for label in [_quantity_bucket_label_from_value(value)]
        if label
    }
    quantity_labels = [
        label for label in QUANTITY_BUCKET_LABELS if label in quantity_buckets_in_data
    ]
    if not quantity_labels:
        quantity_labels = QUANTITY_BUCKET_LABELS.copy()

    raw_dates = row.get("dates") or []
    dates = [str(d) for d in raw_dates if d is not None]

    hero_min_date = row.get("hero_min_date")
    hero_max_date = row.get("hero_max_date")

    return {
        "markets": sorted(row.get("markets") or []),
        "all-retailers": sorted(row.get("all_retailers") or []),
        "segments": sorted(row.get("segments") or []),
        "comp": sorted(row.get("comp") or []),
        "brands": sorted(row.get("brands") or []),
        "types": sorted(row.get("types") or []),
        "quantity": quantity_labels,
        "skus": sorted(row.get("skus") or []),
        "sub_types": sorted(row.get("sub_types") or []),
        "cities": sorted(row.get("cities") or []),
        "dates": dates,
        "date_range": {
            "min": str(hero_min_date) if hero_min_date is not None else None,
            "max": str(hero_max_date) if hero_max_date is not None else None,
        },
    }


async def fetch_retailers(market: list[str] | None = None):
    market_filters = market or []
    where_clause = ""
    if market_filters:
        market_values = _expand_market_aliases(market_filters)
        where_clause = (
            "WHERE LOWER(TRIM(country)) IN "
            f"({_sql_list(market_values)})"
        )

    query = f"""
    SELECT
        ARRAY_AGG(DISTINCT NULLIF(TRIM(platform), ''))
            FILTER (WHERE NULLIF(TRIM(platform), '') IS NOT NULL) AS retailers
    FROM {DEFAULT_TABLE_REF}
    {where_clause};
    """

    df = db.query(query)
    row = df.to_dicts()[0]
    return sorted(row.get("retailers") or [])


@lru_cache(maxsize=1)
def _get_trend_date_column() -> str:
    columns = _default_table_columns()

    candidates = [
        "date",
        "snapshot_date",
        "captured_at",
        "created_at",
        "updated_at",
        "scraped_at",
        "crawl_date",
        "ingested_at",
        "timestamp",
    ]

    for candidate in candidates:
        if candidate in columns:
            return candidate

    raise ValueError(
        'No supported date column found in {DEFAULT_TABLE_REF}. '
        "Expected one of: " + ", ".join(candidates)
    )


def _get_trend_date_expression(date_column: str) -> str:
    return f"""
    CASE
        WHEN NULLIF({date_column}::text, '') IS NULL THEN NULL
        WHEN {date_column}::text ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}' THEN {date_column}::timestamp
        WHEN {date_column}::text ~ '^\\d{{2}}-\\d{{2}}-\\d{{4}}' THEN TO_TIMESTAMP({date_column}::text, 'DD-MM-YYYY')
        WHEN {date_column}::text ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}' THEN TO_TIMESTAMP({date_column}::text, 'MM/DD/YYYY')
        ELSE NULL
    END
    """


async def fetch_price_trend(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in _default_table_columns() else ""
    )

    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS trend_date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY trend_date DESC
        LIMIT 6
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS trend_date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {_region_remap_sql("region")} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS listing_price_value,
            {promo_col} AS promo_price_value
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT trend_date FROM all_dates)
          {and_filters}{avail_filter}
    ),
    retailer_daily AS (
        SELECT
            trend_date, brand, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(listing_price_value)::numeric, 2) AS listing_price_value,
            ROUND(AVG(promo_price_value)::numeric, 2) AS promo_price_value
        FROM base
        GROUP BY trend_date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            trend_date, brand, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(listing_price_value)::numeric, 2) AS listing_price_value,
            ROUND(AVG(promo_price_value)::numeric, 2) AS promo_price_value
        FROM retailer_daily
        GROUP BY trend_date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    daily AS (
        SELECT
            trend_date,
            ROUND(AVG(listing_price_value)::numeric, 2) AS listing_price,
            ROUND(AVG(promo_price_value)::numeric, 2) AS promo_price
        FROM key_daily
        GROUP BY trend_date
    )
    SELECT
        ad.trend_date AS date,
        d.listing_price,
        d.promo_price
    FROM all_dates ad
    LEFT JOIN daily d ON d.trend_date = ad.trend_date
    ORDER BY ad.trend_date;
    """

    df = db.query(query)
    rows = df.to_dicts()
    pricing_currency = _get_pricing_currency(filters)
    return {
        "data": rows,
        "pricing_currency": pricing_currency,
    }


async def fetch_core_competition_pricing_comparison(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)

    # Remove brand filter - core-competition should show all brands for comparison
    filters_without_brand = {k: v for k, v in (filters or {}).items() if k != "brand"}
    filter_conditions = _build_common_filter_conditions(filters_without_brand)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in _default_table_columns() else ""
    )

    # Use exact same logic as price-trend but return all core brands for comparison
    query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS trend_date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            TRIM(platform) AS retailer,
            {_region_remap_sql("region")} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS listing_price_value,
            {promo_col} AS promo_price_value
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          {and_filters}{avail_filter}
    ),
    retailer_daily AS (
        SELECT
            trend_date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(listing_price_value)::numeric, 2) AS listing_price_value,
            ROUND(AVG(promo_price_value)::numeric, 2) AS promo_price_value
        FROM base
        GROUP BY trend_date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            trend_date, brand_key, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(listing_price_value)::numeric, 2) AS listing_price_value,
            ROUND(AVG(promo_price_value)::numeric, 2) AS promo_price_value
        FROM retailer_daily
        GROUP BY trend_date, brand_key, region, pack_type, pack_size, pack, sub_type
    ),
    daily AS (
        SELECT
            trend_date,
            brand_key,
            ROUND(AVG(listing_price_value)::numeric, 2) AS listing_price,
            ROUND(AVG(promo_price_value)::numeric, 2) AS promo_price
        FROM key_daily
        GROUP BY trend_date, brand_key
    ),
    core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    )
    SELECT
        c.brand,
        d.trend_date AS date,
        d.listing_price,
        d.promo_price
    FROM core_brands c
    LEFT JOIN daily d ON c.brand_key = d.brand_key
    WHERE d.trend_date IS NOT NULL
    ORDER BY c.brand, d.trend_date;
    """

    df = db.query(query)
    rows = df.to_dicts()

    grouped = {}
    pricing_currency = _get_pricing_currency(filters)
    for row in rows:
        brand_name = row.get("brand")
        if not brand_name:
            continue
        key = brand_name
        grouped.setdefault(key, []).append(
            {
                "date": row.get("date"),
                "listing_price": row.get("listing_price"),
                "promo_price": row.get("promo_price"),
                "pricing_currency": pricing_currency,
            }
        )

    return grouped


async def fetch_promotion_sku_trending(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview filtering
    validation_filters = (
        "\n          AND cleaned_brand IS NOT NULL"
        "\n          AND TRIM(cleaned_brand) <> ''"
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    agg AS (
        SELECT
            date,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE promo_price < regular_price
                ) / NULLIF(COUNT(*)::numeric, 0),
                2
            ) AS promo_sku_percentage
        FROM key_daily
        GROUP BY date
    )
    SELECT
        ad.date,
        a.promo_sku_percentage
    FROM all_dates ad
    LEFT JOIN agg a ON a.date = ad.date
    ORDER BY ad.date;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_promotion_sku_trending_core_competition(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview/promotion-sku-trending filtering
    validation_filters = (
        "\n          AND cleaned_brand IS NOT NULL"
        "\n          AND TRIM(cleaned_brand) <> ''"
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand_key, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand_key, region, pack_type, pack_size, pack, sub_type
    ),
    agg AS (
        SELECT
            cb.brand,
            kd.date,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE kd.promo_price < kd.regular_price
                ) / NULLIF(COUNT(*)::numeric, 0),
                2
            ) AS promo_sku_percentage
        FROM key_daily kd
        JOIN core_brands cb
          ON cb.brand_key = kd.brand_key
        GROUP BY cb.brand, kd.date
    )
    SELECT
        cb.brand,
        ad.date,
        a.promo_sku_percentage
    FROM all_dates ad
    CROSS JOIN (SELECT DISTINCT brand FROM core_brands) cb
    LEFT JOIN agg a ON a.brand = cb.brand AND a.date = ad.date
    ORDER BY ad.date, cb.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_single_metric(rows, metric_key="promo_sku_percentage")


async def fetch_discount_trending(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview filtering
    validation_filters = (
        "\n          AND cleaned_brand IS NOT NULL"
        "\n          AND TRIM(cleaned_brand) <> ''"
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    discount_pct AS (
        SELECT
            date,
            CASE WHEN regular_price > 0
                THEN 100.0 * (regular_price - promo_price) / regular_price
                ELSE NULL
            END AS discount_pct
        FROM key_daily
    ),
    agg AS (
        SELECT
            date,
            ROUND(AVG(discount_pct)::numeric, 2) AS avg_discount_pct,
            ROUND(MAX(discount_pct)::numeric, 2) AS max_discount_pct
        FROM discount_pct
        GROUP BY date
    )
    SELECT
        ad.date,
        a.avg_discount_pct,
        a.max_discount_pct
    FROM all_dates ad
    LEFT JOIN agg a ON a.date = ad.date
    ORDER BY ad.date;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_discount_trending_core_competition(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    core_brand_keys = [
        "heineken",
        "kingfisher",
        "birra moretti",
        "amstel",
        "tiger",
        "corona",
        "stella artois",
        "stella",
        "budweiser",
        "tuborg",
        "peroni",
        "guinness",
        "carlsberg",
        "haywards",
        "red horse",
    ]
    filter_conditions.append(
        f"LOWER(TRIM(cleaned_brand)) IN ({_sql_list(core_brand_keys)})"
    )
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    SELECT
        DATE_TRUNC('day', ({date_expr}))::date AS date,
        ROUND(AVG(discount_percentage)::numeric, 2) AS avg_discount_pct,
        ROUND(MAX(discount_percentage)::numeric, 2) AS max_discount_pct
    FROM {DEFAULT_TABLE_REF}
    WHERE ({date_expr}) IS NOT NULL
      AND discount_percentage IS NOT NULL
      {and_filters}
    GROUP BY DATE_TRUNC('day', ({date_expr}))::date
    ORDER BY date;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_discount_trending_core_competition_comparison(
    filters: dict | None = None
):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview/discount-trending filtering
    validation_filters = (
        "\n          AND cleaned_brand IS NOT NULL"
        "\n          AND TRIM(cleaned_brand) <> ''"
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand_key, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand_key, region, pack_type, pack_size, pack, sub_type
    ),
    discount_pct AS (
        SELECT
            date,
            brand_key,
            CASE WHEN regular_price > 0
                THEN 100.0 * (regular_price - promo_price) / regular_price
                ELSE NULL
            END AS discount_pct
        FROM key_daily
    ),
    agg AS (
        SELECT
            cb.brand,
            d.date,
            ROUND(AVG(d.discount_pct)::numeric, 2) AS avg_discount_pct,
            ROUND(MAX(d.discount_pct)::numeric, 2) AS max_discount_pct
        FROM discount_pct d
        JOIN core_brands cb
          ON cb.brand_key = d.brand_key
        GROUP BY cb.brand, d.date
    )
    SELECT
        cb.brand,
        ad.date,
        a.avg_discount_pct,
        a.max_discount_pct
    FROM all_dates ad
    CROSS JOIN (SELECT DISTINCT brand FROM core_brands) cb
    LEFT JOIN agg a ON a.brand = cb.brand AND a.date = ad.date
    ORDER BY ad.date, cb.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_multi_metric(
        rows,
        metric_keys=["avg_discount_pct", "max_discount_pct"],
    )


async def fetch_list_vs_promo_price_gap(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview filtering
    validation_filters = (
        "\n          AND cleaned_brand IS NOT NULL"
        "\n          AND TRIM(cleaned_brand) <> ''"
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    agg AS (
        SELECT
            date,
            ROUND(AVG(regular_price)::numeric, 2) AS listing_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM key_daily
        GROUP BY date
    )
    SELECT
        ad.date,
        a.listing_price,
        a.promo_price
    FROM all_dates ad
    LEFT JOIN agg a ON a.date = ad.date
    ORDER BY ad.date;
    """

    df = db.query(query)
    rows = df.to_dicts()
    pricing_currency = _get_pricing_currency(filters)
    for row in rows:
        row["pricing_currency"] = pricing_currency
    return rows


async def fetch_list_vs_promo_price_gap_core_competition(
    filters: dict | None = None
):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview/list-vs-promo-price-gap filtering
    validation_filters = (
        "\n          AND cleaned_brand IS NOT NULL"
        "\n          AND TRIM(cleaned_brand) <> ''"
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            {list_col} AS regular_price,
            {promo_col} AS promo_price
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM base
        GROUP BY date, brand_key, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand_key, region, pack_type, pack_size, pack, sub_type,
            ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
            ROUND(AVG(promo_price)::numeric, 2) AS promo_price
        FROM retailer_daily
        GROUP BY date, brand_key, region, pack_type, pack_size, pack, sub_type
    ),
    agg AS (
        SELECT
            cb.brand,
            kd.date,
            ROUND(AVG(kd.regular_price)::numeric, 2) AS listing_price,
            ROUND(AVG(kd.promo_price)::numeric, 2) AS promo_price
        FROM key_daily kd
        JOIN core_brands cb
          ON cb.brand_key = kd.brand_key
        GROUP BY cb.brand, kd.date
    )
    SELECT
        cb.brand,
        ad.date,
        a.listing_price,
        a.promo_price
    FROM all_dates ad
    CROSS JOIN (SELECT DISTINCT brand FROM core_brands) cb
    LEFT JOIN agg a ON a.brand = cb.brand AND a.date = ad.date
    ORDER BY ad.date, cb.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    pricing_currency = _get_pricing_currency(filters)
    return {
        "listing_price": _pivot_brand_rows_single_metric(
            rows,
            metric_key="listing_price",
        ),
        "promo_price": _pivot_brand_rows_single_metric(
            rows,
            metric_key="promo_price",
        ),
        "pricing_currency": pricing_currency,
    }


async def fetch_availability_trending(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 9
    )
    SELECT
        DATE_TRUNC('day', ({date_expr}))::date AS date,
        TRIM(cleaned_brand) AS brand,
        ROUND(
            100.0 * AVG((LOWER(COALESCE(availability::text, '')) = 'yes')::int)::numeric,
            2
        ) AS availability_percentage
    FROM {DEFAULT_TABLE_REF}
    WHERE ({date_expr}) IS NOT NULL
      AND cleaned_brand IS NOT NULL
      AND TRIM(cleaned_brand) <> ''
      AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
      {and_filters}
    GROUP BY DATE_TRUNC('day', ({date_expr}))::date, TRIM(cleaned_brand)
    ORDER BY date, brand;
    """

    df = db.query(query)
    return _pivot_brand_rows_single_metric(df.to_dicts(), metric_key="availability_percentage")


async def fetch_availability_trending_core_competition_comparison(
    filters: dict | None = None
):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            LOWER(COALESCE(availability::text, '')) AS availability
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          {and_filters}
    )
    SELECT
        cb.brand,
        b.date,
        ROUND(
            100.0 * AVG((b.availability = 'yes')::int)::numeric,
            2
        ) AS availability_percentage
    FROM base b
    JOIN core_brands cb
      ON cb.brand_key = b.brand_key
    GROUP BY cb.brand, b.date
    ORDER BY b.date, cb.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_single_metric(rows, metric_key="availability_percentage")


async def fetch_total_active_skus_trending(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add validation checks to match overview filtering
    validation_filters = (
        "\n      AND cleaned_brand IS NOT NULL"
        "\n      AND TRIM(cleaned_brand) <> ''"
        "\n      AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
    )
    region_remap = _region_remap_sql("region")

    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 6
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            TRIM(platform) AS retailer,
            {region_remap} AS region,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{validation_filters}
    ),
    retailer_daily AS (
        SELECT
            date, brand, retailer, region, pack_type, pack_size, pack, sub_type
        FROM base
        GROUP BY date, brand, retailer, region, pack_type, pack_size, pack, sub_type
    ),
    key_daily AS (
        SELECT
            date, brand, region, pack_type, pack_size, pack, sub_type
        FROM retailer_daily
        GROUP BY date, brand, region, pack_type, pack_size, pack, sub_type
    ),
    agg AS (
        SELECT
            date,
            COUNT(*) AS total_active_skus
        FROM key_daily
        GROUP BY date
    )
    SELECT
        ad.date,
        COALESCE(a.total_active_skus, 0) AS total_active_skus
    FROM all_dates ad
    LEFT JOIN agg a ON a.date = ad.date
    ORDER BY ad.date;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_total_active_skus_trending_core_competition_comparison(
    filters: dict | None = None
):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            LOWER(COALESCE(availability::text, '')) AS availability
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          {and_filters}
    )
    SELECT
        cb.brand,
        b.date,
        COUNT(*) FILTER (
            WHERE b.availability = 'yes'
        ) AS total_active_skus
    FROM base b
    JOIN core_brands cb
      ON cb.brand_key = b.brand_key
    GROUP BY cb.brand, b.date
    ORDER BY b.date, cb.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_single_metric(rows, metric_key="total_active_skus")


async def fetch_out_of_stock_skus_trending(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 9
    ),
    agg AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            TRIM(cleaned_brand) AS brand,
            COUNT(*) FILTER (
                WHERE LOWER(COALESCE(availability::text, '')) = 'yes'
            ) AS active_skus,
            COUNT(*) FILTER (
                WHERE LOWER(COALESCE(availability::text, '')) <> 'yes'
            ) AS out_of_stock_skus
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}
        GROUP BY DATE_TRUNC('day', ({date_expr}))::date, TRIM(cleaned_brand)
    )
    SELECT
        ad.date,
        a.brand,
        COALESCE(a.active_skus, 0)        AS active_skus,
        COALESCE(a.out_of_stock_skus, 0)  AS out_of_stock_skus
    FROM all_dates ad
    LEFT JOIN agg a ON a.date = ad.date
    ORDER BY ad.date, a.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_multi_metric(
        rows,
        metric_keys=["active_skus", "out_of_stock_skus"],
    )


async def fetch_out_of_stock_skus_trending_core_competition_comparison(
    filters: dict | None = None
):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH core_brands AS (
        SELECT display_name AS brand, brand_key
        FROM (VALUES
            ('Heineken',      'heineken'),
            ('Kingfisher',    'kingfisher'),
            ('Birra Moretti', 'birra moretti'),
            ('Amstel',        'amstel'),
            ('Tiger',         'tiger'),
            ('Corona',        'corona'),
            ('Stella',        'stella'),
            ('Stella',        'stella artois'),
            ('Budweiser',     'budweiser'),
            ('Tuborg',        'tuborg'),
            ('Peroni',        'peroni'),
            ('Guinness',      'guinness'),
            ('Carlsberg',     'carlsberg'),
            ('Haywards',      'haywards'),
            ('Red Horse',     'red horse')
        ) AS t(display_name, brand_key)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            LOWER(COALESCE(availability::text, '')) AS availability
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          {and_filters}
    )
    SELECT
        cb.brand,
        b.date,
        COUNT(*) FILTER (
            WHERE b.availability <> 'yes'
        ) AS out_of_stock_skus
    FROM base b
    JOIN core_brands cb
      ON cb.brand_key = b.brand_key
    GROUP BY cb.brand, b.date
    ORDER BY b.date, cb.brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_single_metric(rows, metric_key="out_of_stock_skus")


async def fetch_share_of_visibility_heineken_portfolio(
    filters: dict | None = None
):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)

    filter_conditions = _build_common_filter_conditions(filters)

    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    # Add same validation as brand-visibility-by-retailer
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in _default_table_columns() else ""
    )
    query = f"""
    WITH portfolio AS (
        SELECT LOWER(brand_name) AS brand_key, brand_name
        FROM (
            VALUES
                ('Heineken'),
                ('Kingfisher'),
                ('Birra Moretti'),
                ('Amstel'),
                ('Tiger')
        ) AS p(brand_name)
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            LOWER(TRIM(platform)) AS retailer,
            LOWER(TRIM(cleaned_brand)) AS brand_key,
            TRIM(pack_format) AS pack_type,
            TRIM(quantity) AS pack_size,
            units AS pack,
            LOWER(TRIM(COALESCE(sub_type, ''))) AS sub_type,
            LOWER(TRIM(COALESCE(features_in_top10::text, ''))) AS features_in_top10,
            LOWER(TRIM(COALESCE(features_on_first_page::text, ''))) AS features_on_first_page
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          AND platform IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          {and_filters}{avail_filter}
    ),
    last_6_dates AS (
        SELECT DISTINCT date
        FROM base
        ORDER BY date DESC
        LIMIT 9
    ),
    filtered_base AS (
        SELECT b.*
        FROM base b
        JOIN last_6_dates ld ON b.date = ld.date
    ),
    sku_retailer AS (
        SELECT
            fb.date,
            p.brand_name,
            fb.brand_key,
            fb.pack_type,
            fb.pack_size,
            fb.pack,
            fb.sub_type,
            fb.retailer,
            BOOL_OR(fb.features_in_top10 IN ('yes', 'true', '1', 'y')) AS in_top10,
            BOOL_OR(fb.features_on_first_page IN ('yes', 'true', '1', 'y')) AS on_first_page
        FROM filtered_base fb
        JOIN portfolio p
          ON fb.brand_key = p.brand_key
        GROUP BY fb.date, p.brand_name, fb.brand_key, fb.pack_type, fb.pack_size, fb.pack, fb.sub_type, fb.retailer
    )
    SELECT
        date,
        brand_name AS brand,
        pack_type,
        pack_size,
        pack,
        sub_type,
        retailer,
        in_top10,
        on_first_page
    FROM sku_retailer
    ORDER BY date DESC,
        CASE brand_name
            WHEN 'Heineken' THEN 1
            WHEN 'Kingfisher' THEN 2
            WHEN 'Birra Moretti' THEN 3
            WHEN 'Amstel' THEN 4
            WHEN 'Tiger' THEN 5
            ELSE 99
        END;
    """

    df = db.query(query)
    rows = df.to_dicts()

    # Group raw SKU x retailer rows by date, then apply the same
    # numerator/denominator logic as brand-visibility-by-retailer's
    # brand_totals (top10 share = Y-cells / (num_retailers * 10),
    # first-page share = Y-cells / sum(retailer first-page capacities)).
    by_date: dict = {}
    for row in rows:
        by_date.setdefault(row.get("date"), []).append(row)

    brand_order = ["Heineken", "Kingfisher", "Birra Moretti", "Amstel", "Tiger"]

    top10_by_brand: dict = {}
    first_page_by_brand: dict = {}
    dates = sorted(by_date.keys())

    for date in dates:
        date_rows = by_date[date]
        distinct_retailers = sorted({r.get("retailer") for r in date_rows})
        num_retailers = len(distinct_retailers)

        brand_rows: dict = {}
        for r in date_rows:
            brand_rows.setdefault(r.get("brand"), []).append(r)

        for brand_name in brand_order:
            brows = brand_rows.get(brand_name) or []

            total_skus_for_brand = len({
                (r.get("pack_type"), r.get("pack_size"), r.get("pack"), r.get("sub_type"))
                for r in brows
            })

            t10_numerator = sum(1 for r in brows if r.get("in_top10"))
            fp_numerator = sum(1 for r in brows if r.get("on_first_page"))

            t10_denom = num_retailers * 10
            fp_denom = sum(
                RETAILER_FIRST_PAGE_CAPACITY.get(retailer, total_skus_for_brand)
                for retailer in distinct_retailers
            )

            top10_pct = round(100.0 * t10_numerator / t10_denom, 2) if t10_denom else None
            fp_pct = round(100.0 * fp_numerator / fp_denom, 2) if fp_denom else None

            top10_by_brand.setdefault(brand_name, []).append({
                "date": date,
                "visibility_pct": top10_pct,
            })
            first_page_by_brand.setdefault(brand_name, []).append({
                "date": date,
                "visibility_pct": fp_pct,
            })

    return {
        "features_in_top10": top10_by_brand,
        "features_on_first_page": first_page_by_brand,
        "dates": dates,
    }


async def fetch_can_vs_bottle_mix(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            pack_format
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          {and_filters}
    ),
    latest_date AS (
        SELECT MAX(date) AS date
        FROM base
    ),
    normalized AS (
        SELECT
            CASE
                WHEN LOWER(TRIM(pack_format)) = 'can' THEN 'Can'
                WHEN LOWER(TRIM(pack_format)) IN ('bottle', 'glass') THEN 'Bottle'
                WHEN LOWER(TRIM(pack_format)) = 'keg' THEN 'Keg'
                ELSE NULL
            END AS format_group
        FROM base b
        JOIN latest_date ld
          ON b.date = ld.date
    ),
    grouped AS (
        SELECT
            format_group,
            COUNT(*) AS sku_count
        FROM normalized
        WHERE format_group IS NOT NULL
        GROUP BY format_group
    ),
    totals AS (
        SELECT COALESCE(SUM(sku_count), 0) AS total_count
        FROM grouped
    )
    SELECT
        g.format_group AS category,
        g.sku_count,
        ROUND(100.0 * g.sku_count::numeric / NULLIF(t.total_count::numeric, 0), 2) AS percentage
    FROM grouped g
    CROSS JOIN totals t
    ORDER BY
        CASE g.format_group
            WHEN 'Can' THEN 1
            WHEN 'Bottle' THEN 2
            WHEN 'Keg' THEN 3
            ELSE 99
        END;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_pack_mix(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            units
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          {and_filters}
    ),
    latest_date AS (
        SELECT MAX(date) AS date
        FROM base
    ),
    normalized AS (
        SELECT
            b.units
        FROM base b
        JOIN latest_date ld
          ON b.date = ld.date
    ),
    grouped AS (
        SELECT
            units,
            COUNT(*) AS sku_count
        FROM normalized
        WHERE units IS NOT NULL
        GROUP BY units
    ),
    totals AS (
        SELECT COALESCE(SUM(sku_count), 0) AS total_count
        FROM grouped
    )
    SELECT
        CASE
            WHEN g.units = 1 THEN 'Single Pack'
            ELSE CONCAT(g.units::text, ' Pack')
        END AS category,
        g.units,
        g.sku_count,
        ROUND(
            100.0 * g.sku_count::numeric / NULLIF(t.total_count::numeric, 0),
            2
        ) AS percentage
    FROM grouped g
    CROSS JOIN totals t
    ORDER BY g.units;
    """

    df = db.query(query)
    return df.to_dicts()


async def fetch_can_vs_bottle_trend(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            CASE
                WHEN LOWER(TRIM(pack_format)) = 'can' THEN 'Can'
                WHEN LOWER(TRIM(pack_format)) IN ('bottle', 'glass') THEN 'Bottle'
                WHEN LOWER(TRIM(pack_format)) = 'keg' THEN 'Keg'
                ELSE NULL
            END AS category
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          {and_filters}
    ),
    grouped AS (
        SELECT
            date,
            category,
            COUNT(*) AS sku_count
        FROM base
        WHERE category IS NOT NULL
        GROUP BY date, category
    ),
    totals AS (
        SELECT
            date,
            SUM(sku_count) AS total_count
        FROM grouped
        GROUP BY date
    )
    SELECT
        g.date,
        g.category,
        g.sku_count,
        ROUND(
            100.0 * g.sku_count::numeric / NULLIF(t.total_count::numeric, 0),
            2
        ) AS percentage
    FROM grouped g
    JOIN totals t
      ON g.date = t.date
        ORDER BY
            g.date,
            CASE g.category
                WHEN 'Can' THEN 1
                WHEN 'Bottle' THEN 2
                WHEN 'Keg' THEN 3
                ELSE 99
            END;
    """

    df = db.query(query)
    rows = df.to_dicts()

    cans = []
    bottles = []
    kegs = []
    for row in rows:
        point = {
            "date": row.get("date"),
            "sku_count": row.get("sku_count"),
            "percentage": row.get("percentage"),
        }
        category = (row.get("category") or "").lower()
        if category == "can":
            cans.append(point)
        elif category == "bottle":
            bottles.append(point)
        elif category == "keg":
            kegs.append(point)

    return {
        "cans": cans,
        "bottles": bottles,
        "kegs": kegs,
    }


async def fetch_pack_size_distribution_trend(filters: dict | None = None):
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date AS date,
            CASE
                WHEN units = 1 THEN 'single_pack'
                WHEN units = 6 THEN 'pack_6'
                WHEN units = 12 THEN 'pack_12'
                WHEN units = 24 THEN 'pack_24'
                ELSE NULL
            END AS pack_group
        FROM {DEFAULT_TABLE_REF}
        WHERE ({date_expr}) IS NOT NULL
          {and_filters}
    ),
    grouped AS (
        SELECT
            date,
            pack_group,
            COUNT(*) AS sku_count
        FROM base
        WHERE pack_group IS NOT NULL
        GROUP BY date, pack_group
    ),
    totals AS (
        SELECT
            date,
            SUM(sku_count) AS total_count
        FROM grouped
        GROUP BY date
    )
    SELECT
        g.date,
        g.pack_group,
        g.sku_count,
        ROUND(
            100.0 * g.sku_count::numeric / NULLIF(t.total_count::numeric, 0),
            2
        ) AS percentage
    FROM grouped g
    JOIN totals t
      ON g.date = t.date
    ORDER BY g.date;
    """

    df = db.query(query)
    rows = df.to_dicts()

    output = {
        "single_pack": [],
        "pack_6": [],
        "pack_12": [],
        "pack_24": [],
    }

    for row in rows:
        key = row.get("pack_group")
        if key not in output:
            continue
        output[key].append(
            {
                "date": row.get("date"),
                "sku_count": row.get("sku_count"),
                "percentage": row.get("percentage"),
            }
        )

    return output


async def fetch_price_trends_by_brand(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters, table_alias="p")
    list_col, promo_col = _get_price_columns(filters)
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    query = f"""
    SELECT
        DATE_TRUNC('day', ({date_expr}))::date AS date,
        TRIM(p.cleaned_brand) AS brand,
        ROUND(AVG(p.{list_col})::numeric, 2) AS listing_price,
        ROUND(AVG(p.{promo_col})::numeric, 2) AS promo_price
    FROM {DEFAULT_TABLE_REF} p
    WHERE ({date_expr}) IS NOT NULL
      AND p.cleaned_brand IS NOT NULL
      AND TRIM(p.cleaned_brand) <> ''
      AND LOWER(COALESCE(p.availability::text, '')) = 'yes'
      AND p.{promo_col} IS NOT NULL
      AND p.{list_col} IS NOT NULL
      AND p.{promo_col} < p.{list_col}
      {and_filters}
    GROUP BY DATE_TRUNC('day', ({date_expr}))::date, TRIM(p.cleaned_brand)
    ORDER BY date, brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    output = {}
    pricing_currency = _get_pricing_currency(filters)

    for row in rows:
        brand = row.get("brand")
        if not brand:
            continue
        output.setdefault(brand, [])
        output[brand].append(
            {
                "date": row.get("date"),
                "listing_price": row.get("listing_price"),
                "promo_price": row.get("promo_price"),
                "pricing_currency": pricing_currency,
            }
        )

    return output


async def fetch_promotion_depth_by_brand(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters, table_alias="p")
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = """
    SELECT
        TRIM(p.cleaned_brand) AS brand,
        ROUND(AVG(p.discount_percentage)::numeric, 2) AS avg_discount_pct
    FROM {DEFAULT_TABLE_REF} p
    WHERE p.cleaned_brand IS NOT NULL
      AND TRIM(p.cleaned_brand) <> ''
      {and_filters}
    GROUP BY TRIM(p.cleaned_brand)
    ORDER BY brand;
    """

    df = db.query(query.format(and_filters=and_filters))
    return df.to_dicts()


async def fetch_promotion_depth_by_brand_trend(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters, table_alias="p")
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    query = f"""
    SELECT
        DATE_TRUNC('day', ({date_expr}))::date AS date,
        TRIM(p.cleaned_brand) AS brand,
        ROUND(AVG(p.discount_percentage)::numeric, 2) AS avg_discount_pct
    FROM {DEFAULT_TABLE_REF} p
    WHERE ({date_expr}) IS NOT NULL
      AND p.cleaned_brand IS NOT NULL
      AND TRIM(p.cleaned_brand) <> ''
      AND p.discount_percentage IS NOT NULL
      {and_filters}
    GROUP BY DATE_TRUNC('day', ({date_expr}))::date, TRIM(p.cleaned_brand)
    ORDER BY date, brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_single_metric(rows, metric_key="avg_discount_pct")


async def fetch_availability_by_brand(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters, table_alias="p")
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    query = """
    SELECT
        TRIM(p.cleaned_brand) AS brand,
        ROUND(
            100.0 * AVG((LOWER(COALESCE(p.availability::text, '')) = 'yes')::int)::numeric,
            2
        ) AS availability_pct
    FROM {DEFAULT_TABLE_REF} p
    WHERE p.cleaned_brand IS NOT NULL
      AND TRIM(p.cleaned_brand) <> ''
      {and_filters}
    GROUP BY TRIM(p.cleaned_brand)
    ORDER BY brand;
    """

    df = db.query(query.format(and_filters=and_filters))
    return df.to_dicts()


async def fetch_availability_by_brand_trend(filters: dict | None = None):
    filter_conditions = _build_common_filter_conditions(filters, table_alias="p")
    and_filters = (
        "\n      AND " + "\n      AND ".join(filter_conditions)
        if filter_conditions
        else ""
    )
    date_column = _get_trend_date_column()
    date_expr = _get_trend_date_expression(date_column)
    query = f"""
    SELECT
        DATE_TRUNC('day', ({date_expr}))::date AS date,
        TRIM(p.cleaned_brand) AS brand,
        ROUND(
            100.0 * AVG((LOWER(COALESCE(p.availability::text, '')) = 'yes')::int)::numeric,
            2
        ) AS availability_pct
    FROM {DEFAULT_TABLE_REF} p
    WHERE ({date_expr}) IS NOT NULL
      AND p.cleaned_brand IS NOT NULL
      AND TRIM(p.cleaned_brand) <> ''
      {and_filters}
    GROUP BY DATE_TRUNC('day', ({date_expr}))::date, TRIM(p.cleaned_brand)
    ORDER BY date, brand;
    """

    df = db.query(query)
    rows = df.to_dicts()
    return _pivot_brand_rows_single_metric(rows, metric_key="availability_pct")


# ── Hero SKU Tracker ──────────────────────────────────────────────────────────


def _normalize_pack_size(s: str) -> str:
    """Normalize '33.0CL' → '33CL', '35.5CL' → '35.5CL' (non-zero decimal unchanged)."""
    return re.sub(r'\.0([A-Za-z]+)$', r'\1', (s or '').strip().upper())


_HERO_PORTFOLIO_BRANDS: frozenset[str] = frozenset(
    ["heineken", "amstel", "tiger", "birra moretti", "kingfisher"]
)

_CATEGORY_DISPLAY: dict[str, str] = {
    "premium": "Premium",
    "super_premium": "Super Premium",
    "mainstream": "Mainstream",
    "strong": "Strong",
}


def _hero_eff_price(regular_price, promo_price):
    if regular_price is None:
        return promo_price
    if promo_price is not None and promo_price < regular_price:
        return promo_price
    return regular_price


def _hero_price_flag(regular_price, promo_price, prev_regular_price, prev_promo_price) -> str:
    eff = _hero_eff_price(regular_price, promo_price)
    prev_eff = _hero_eff_price(prev_regular_price, prev_promo_price)

    if eff is None or prev_eff is None or prev_eff == 0:
        return "ok"

    delta_pct = (eff - prev_eff) / prev_eff * 100

    if delta_pct <= 0:
        return "red"
    if delta_pct <= 6:
        return "amber"
    return "ok"


def _hero_vis_flag(delta_top10_pt, delta_first_page_pt) -> str:
    # No visibility data = SKU not appearing anywhere = red
    if delta_top10_pt is None and delta_first_page_pt is None:
        return "red"
    if (delta_top10_pt is not None and delta_top10_pt <= 0) or (
        delta_first_page_pt is not None and delta_first_page_pt <= 0
    ):
        return "red"
    return "ok"


async def fetch_hero_sku_tracker(filters: dict | None = None):
    table_ref = DEFAULT_TABLE_REF
    date_cols = _default_table_columns()

    date_column = next(
        (
            c
            for c in [
                "date", "snapshot_date", "captured_at", "created_at",
                "updated_at", "scraped_at", "crawl_date", "ingested_at", "timestamp",
            ]
            if c in date_cols
        ),
        None,
    )
    if not date_column:
        raise ValueError(f"No supported date column found in {table_ref}.")

    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    pricing_currency = _get_pricing_currency(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions else ""
    )
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in date_cols else ""
    )

    latest_date_cte = "SELECT MAX(date) AS date FROM base"

    ref_query = """
    SELECT
        LOWER(TRIM(brand))               AS brand,
        TRIM(pack_type)                  AS pack_type,
        UPPER(TRIM(pack_size))           AS pack_size,
        pack,
        LOWER(TRIM(sub_type))            AS sub_type,
        LOWER(TRIM(category))            AS category
    FROM beer_pricing_analysis.beer_sku_reference
    ORDER BY category, brand, pack_type, pack_size, sub_type
    """

    pricing_query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date            AS date,
            {_hero_sku_brand_remap_sql()}                      AS brand,
            TRIM(platform)                                     AS retailer,
            TRIM(pack_format)                                  AS pack_type,
            UPPER(TRIM(quantity))                              AS pack_size,
            units                                              AS pack,
            CASE
                WHEN LOWER(TRIM(COALESCE(sub_type, ''))) = '' THEN 'regular'
                ELSE LOWER(TRIM(sub_type))
            END                                                AS sub_type,
            {list_col}                                         AS regular_price,
            {promo_col}                                        AS promo_price
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          {and_filters}{avail_filter}
    ),
    latest_date AS ({latest_date_cte}),
    prev_date AS (
        SELECT MAX(date) AS date FROM base
        WHERE date <= ((SELECT date FROM latest_date) - INTERVAL '7 day')
    ),
    retailer_daily AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
               ROUND(AVG(promo_price)::numeric, 2)   AS promo_price
        FROM base
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    ),
    sku_daily AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
               ROUND(AVG(promo_price)::numeric, 2)   AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    ),
    latest   AS (SELECT * FROM sku_daily WHERE date = (SELECT date FROM latest_date)),
    previous AS (SELECT * FROM sku_daily WHERE date = (SELECT date FROM prev_date))
    SELECT
        l.brand, l.pack_type, l.pack_size, l.pack, l.sub_type,
        l.regular_price,
        l.promo_price,
        p.regular_price AS prev_regular_price,
        p.promo_price   AS prev_promo_price,
        (SELECT date FROM latest_date) AS week_date,
        (SELECT date FROM prev_date)   AS prev_week_date
    FROM latest l
    LEFT JOIN previous p
      ON  l.brand                        = p.brand
     AND  COALESCE(l.pack_type,  '')     = COALESCE(p.pack_type,  '')
     AND  COALESCE(l.pack_size,  '')     = COALESCE(p.pack_size,  '')
     AND  COALESCE(l.pack,       -1)     = COALESCE(p.pack,       -1)
     AND  COALESCE(l.sub_type,   '')     = COALESCE(p.sub_type,   '')
    ORDER BY l.brand, l.pack_type, l.pack_size, l.pack, l.sub_type
    """

    vis_query = f"""
    WITH base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date             AS date,
            {_hero_sku_brand_remap_sql()}                       AS brand,
            TRIM(platform)                                      AS retailer,
            TRIM(pack_format)                                   AS pack_type,
            UPPER(TRIM(quantity))                               AS pack_size,
            units                                               AS pack,
            CASE
                WHEN LOWER(TRIM(COALESCE(sub_type, ''))) = '' THEN 'regular'
                ELSE LOWER(TRIM(sub_type))
            END                                                 AS sub_type,
            LOWER(TRIM(COALESCE(features_in_top10::text,    ''))) AS features_in_top10,
            LOWER(TRIM(COALESCE(features_on_first_page::text,''))) AS features_on_first_page
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND platform IS NOT NULL
          {and_filters}{avail_filter}
    ),
    latest_date AS ({latest_date_cte}),
    prev_date AS (
        SELECT MAX(date) AS date FROM base
        WHERE date <= ((SELECT date FROM latest_date) - INTERVAL '7 day')
    ),
    latest AS (
        SELECT brand, retailer, pack_type, pack_size, pack, sub_type,
               BOOL_OR(features_in_top10    IN ('yes','true','1','y')) AS in_top10,
               BOOL_OR(features_on_first_page IN ('yes','true','1','y')) AS on_first_page
        FROM base WHERE date = (SELECT date FROM latest_date)
        GROUP BY brand, retailer, pack_type, pack_size, pack, sub_type
    ),
    previous AS (
        SELECT brand, retailer, pack_type, pack_size, pack, sub_type,
               BOOL_OR(features_in_top10    IN ('yes','true','1','y')) AS in_top10,
               BOOL_OR(features_on_first_page IN ('yes','true','1','y')) AS on_first_page
        FROM base WHERE date = (SELECT date FROM prev_date)
        GROUP BY brand, retailer, pack_type, pack_size, pack, sub_type
    ),
    total_retailers AS (
        SELECT COUNT(DISTINCT retailer) AS cnt FROM base
        WHERE date = (SELECT date FROM latest_date)
    ),
    total_prev_retailers AS (
        SELECT COUNT(DISTINCT retailer) AS cnt FROM base
        WHERE date = (SELECT date FROM prev_date)
    )
    SELECT
        l.brand, l.pack_type, l.pack_size, l.pack, l.sub_type, l.retailer,
        l.in_top10,
        l.on_first_page,
        COALESCE(p.in_top10,       FALSE) AS prev_in_top10,
        COALESCE(p.on_first_page,  FALSE) AS prev_on_first_page,
        (SELECT cnt FROM total_retailers)      AS total_market_retailers,
        (SELECT cnt FROM total_prev_retailers) AS total_prev_market_retailers
    FROM latest l
    LEFT JOIN previous p
      ON  l.brand                    = p.brand
     AND  l.retailer                 = p.retailer
     AND  COALESCE(l.pack_type,  '') = COALESCE(p.pack_type,  '')
     AND  COALESCE(l.pack_size,  '') = COALESCE(p.pack_size,  '')
     AND  COALESCE(l.pack,       -1) = COALESCE(p.pack,       -1)
     AND  COALESCE(l.sub_type,   '') = COALESCE(p.sub_type,   '')
    ORDER BY l.brand, l.pack_type, l.pack_size, l.pack, l.sub_type, l.retailer
    """

    ref_df, pricing_df, vis_df = await asyncio.gather(
        asyncio.to_thread(db.query, ref_query),
        asyncio.to_thread(db.query, pricing_query),
        asyncio.to_thread(db.query, vis_query),
    )

    hero_skus = ref_df.to_dicts()

    # Pricing lookup: (brand, pack_type, normalized_pack_size, pack, sub_type) → row
    pricing_lookup: dict[tuple, dict] = {}
    week_date = None
    prev_week_date = None
    for row in pricing_df.to_dicts():
        key = (
            (row.get("brand") or "").strip(),
            (row.get("pack_type") or "").strip(),
            _normalize_pack_size(row.get("pack_size") or ""),
            row.get("pack"),
            (row.get("sub_type") or "").strip(),
        )
        pricing_lookup[key] = row
        if week_date is None:
            week_date = row.get("week_date")
            prev_week_date = row.get("prev_week_date")

    # Global retailer counts (same denominator as brand-visibility)
    vis_rows_all = vis_df.to_dicts()
    total_market_retailers = int(vis_rows_all[0]["total_market_retailers"]) if vis_rows_all else 0
    total_prev_market_retailers = int(vis_rows_all[0]["total_prev_market_retailers"]) if vis_rows_all else 0

    # Visibility lookup: (brand, pack_type, normalized_pack_size, pack, sub_type) → [retailer rows]
    vis_lookup: dict[tuple, list[dict]] = {}
    for row in vis_rows_all:
        key = (
            (row.get("brand") or "").strip(),
            (row.get("pack_type") or "").strip(),
            _normalize_pack_size(row.get("pack_size") or ""),
            row.get("pack"),
            (row.get("sub_type") or "").strip(),
        )
        vis_lookup.setdefault(key, []).append(row)

    portfolio_rows: list[dict] = []
    competitor_rows: list[dict] = []

    for sku in hero_skus:
        brand     = (sku.get("brand")     or "").strip()
        pack_type = (sku.get("pack_type") or "").strip()
        pack_size = _normalize_pack_size(sku.get("pack_size") or "")
        pack      = sku.get("pack")
        sub_type  = (sku.get("sub_type")  or "").strip()
        category  = (sku.get("category")  or "").strip()

        key = (brand, pack_type, pack_size, pack, sub_type)
        pricing  = pricing_lookup.get(key, {})
        vis_rows = vis_lookup.get(key, [])

        regular_price      = pricing.get("regular_price")
        promo_price        = pricing.get("promo_price")
        prev_regular_price = pricing.get("prev_regular_price")
        prev_promo_price   = pricing.get("prev_promo_price")

        eff      = _hero_eff_price(regular_price, promo_price)
        prev_eff = _hero_eff_price(prev_regular_price, prev_promo_price)

        if eff is not None and prev_eff is not None and prev_eff != 0:
            delta_eff_pct = round((eff - prev_eff) / prev_eff * 100, 1)
        else:
            delta_eff_pct = None

        # Visibility: use total market retailers as denominator (same as brand-visibility)
        if total_market_retailers > 0:
            count_top10      = sum(1 for r in vis_rows if r.get("in_top10"))
            count_top10_prev = sum(1 for r in vis_rows if r.get("prev_in_top10"))
            count_fp         = sum(1 for r in vis_rows if r.get("on_first_page"))
            count_fp_prev    = sum(1 for r in vis_rows if r.get("prev_on_first_page"))

            top10_pct      = round(count_top10      / total_market_retailers * 100)
            top10_pct_prev = round(count_top10_prev / total_prev_market_retailers * 100) if total_prev_market_retailers else 0
            fp_pct         = round(count_fp         / total_market_retailers * 100)
            fp_pct_prev    = round(count_fp_prev    / total_prev_market_retailers * 100) if total_prev_market_retailers else 0

            delta_top10_pt = top10_pct - top10_pct_prev
            delta_fp_pt    = fp_pct    - fp_pct_prev
        else:
            top10_pct = fp_pct = None
            delta_top10_pt = delta_fp_pt = None

        # SKU label: e.g. "Heineken · Can 33cl 24 reg"
        brand_display = brand.title()
        sub_label     = sub_type if sub_type and sub_type != "regular" else "reg"
        sku_label     = f"{brand_display} · {pack_type} {pack_size.lower()} {pack} {sub_label}"

        row_data = {
            "category":             category,
            "segment":              _CATEGORY_DISPLAY.get(category, category.title()),
            "brand":                brand,
            "brand_display":        brand_display,
            "sku_label":            sku_label,
            "pack_type":            pack_type,
            "pack_size":            pack_size.lower(),
            "pack":                 pack,
            "sub_type":             sub_type,
            "eff_price":            eff,
            "regular_price":        regular_price,
            "promo_price":          promo_price,
            "delta_eff_pct":        delta_eff_pct,
            "top10_pct":            top10_pct,
            "first_page_pct":       fp_pct,
            "delta_top10_pt":       delta_top10_pt,
            "delta_first_page_pt":  delta_fp_pt,
            "price_flag":           _hero_price_flag(
                                        regular_price, promo_price,
                                        prev_regular_price, prev_promo_price,
                                    ),
            "vis_flag":             _hero_vis_flag(delta_top10_pt, delta_fp_pt),
            "has_pricing_data":     eff is not None,
            "has_visibility_data":  len(vis_rows) > 0,
            "pricing_currency":     pricing_currency,
        }

        if brand in _HERO_PORTFOLIO_BRANDS:
            portfolio_rows.append(row_data)
        else:
            competitor_rows.append(row_data)

    return {
        "sections": [
            {
                "section": "our_portfolio",
                "label":   "Our portfolio",
                "rows":    portfolio_rows,
            },
            {
                "section": "key_competitors",
                "label":   "Key competitors · own week-on-week movement",
                "rows":    competitor_rows,
            },
        ],
        "week_date":        week_date,
        "prev_week_date":   prev_week_date,
        "pricing_currency": pricing_currency,
    }


# ── Hero SKU Trend (9-week history) ───────────────────────────────────────────

async def fetch_hero_sku_trend(filters: dict | None = None):
    table_ref = DEFAULT_TABLE_REF
    date_cols = _default_table_columns()

    date_column = next(
        (
            c for c in [
                "date", "snapshot_date", "captured_at", "created_at",
                "updated_at", "scraped_at", "crawl_date", "ingested_at", "timestamp",
            ]
            if c in date_cols
        ),
        None,
    )
    if not date_column:
        raise ValueError(f"No supported date column found in {table_ref}.")

    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    pricing_currency = _get_pricing_currency(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions else ""
    )
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in date_cols else ""
    )

    ref_query = """
    SELECT
        LOWER(TRIM(brand))      AS brand,
        TRIM(pack_type)         AS pack_type,
        UPPER(TRIM(pack_size))  AS pack_size,
        pack,
        LOWER(TRIM(sub_type))   AS sub_type,
        LOWER(TRIM(category))   AS category
    FROM beer_pricing_analysis.beer_sku_reference
    ORDER BY category, brand, pack_type, pack_size, sub_type
    """

    pricing_query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 9
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date                     AS date,
            {_hero_sku_brand_remap_sql()}                                AS brand,
            TRIM(platform)                                               AS retailer,
            TRIM(pack_format)                                            AS pack_type,
            REGEXP_REPLACE(UPPER(TRIM(quantity)), '\\.0([A-Z]+)$', '\\1') AS pack_size,
            units                                                        AS pack,
            CASE
                WHEN LOWER(TRIM(COALESCE(sub_type, ''))) = '' THEN 'regular'
                ELSE LOWER(TRIM(sub_type))
            END                                                          AS sub_type,
            {list_col}                                                   AS regular_price,
            {promo_col}                                                  AS promo_price
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{avail_filter}
    ),
    retailer_daily AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
               ROUND(AVG(promo_price)::numeric, 2)   AS promo_price
        FROM base
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    ),
    sku_weekly AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
               ROUND(AVG(promo_price)::numeric, 2)   AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    )
    SELECT
        ad.date,
        s.brand, s.pack_type, s.pack_size, s.pack, s.sub_type,
        s.regular_price,
        s.promo_price,
        CASE
            WHEN s.promo_price IS NOT NULL AND s.promo_price < s.regular_price
            THEN s.promo_price
            ELSE s.regular_price
        END AS eff_price
    FROM all_dates ad
    LEFT JOIN sku_weekly s ON s.date = ad.date
    ORDER BY s.brand, s.pack_type, s.pack_size, s.pack, s.sub_type, ad.date
    """

    vis_query = f"""
    WITH all_dates AS (
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 9
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date                      AS date,
            {_hero_sku_brand_remap_sql()}                                 AS brand,
            TRIM(platform)                                                AS retailer,
            TRIM(pack_format)                                             AS pack_type,
            REGEXP_REPLACE(UPPER(TRIM(quantity)), '\\.0([A-Z]+)$', '\\1') AS pack_size,
            units                                                         AS pack,
            CASE
                WHEN LOWER(TRIM(COALESCE(sub_type, ''))) = '' THEN 'regular'
                ELSE LOWER(TRIM(sub_type))
            END                                                           AS sub_type,
            LOWER(TRIM(COALESCE(features_in_top10::text,     ''))) AS features_in_top10,
            LOWER(TRIM(COALESCE(features_on_first_page::text,''))) AS features_on_first_page
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND platform IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{avail_filter}
    ),
    retailer_weekly AS (
        SELECT date, brand, retailer, pack_type, pack_size, pack, sub_type,
               BOOL_OR(features_in_top10    IN ('yes','true','1','y')) AS in_top10,
               BOOL_OR(features_on_first_page IN ('yes','true','1','y')) AS on_first_page
        FROM base
        GROUP BY date, brand, retailer, pack_type, pack_size, pack, sub_type
    ),
    sku_weekly AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               SUM(CASE WHEN in_top10     THEN 1 ELSE 0 END) AS count_top10,
               SUM(CASE WHEN on_first_page THEN 1 ELSE 0 END) AS count_fp
        FROM retailer_weekly
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    ),
    total_market_by_date AS (
        SELECT date, COUNT(DISTINCT retailer) AS total_retailers
        FROM retailer_weekly
        GROUP BY date
    )
    SELECT
        ad.date,
        s.brand, s.pack_type, s.pack_size, s.pack, s.sub_type,
        t.total_retailers,
        CASE WHEN t.total_retailers > 0
             THEN ROUND(s.count_top10::numeric / t.total_retailers * 100)
             ELSE NULL END AS top10_pct,
        CASE WHEN t.total_retailers > 0
             THEN ROUND(s.count_fp::numeric    / t.total_retailers * 100)
             ELSE NULL END AS first_page_pct
    FROM all_dates ad
    LEFT JOIN sku_weekly s ON s.date = ad.date
    LEFT JOIN total_market_by_date t ON t.date = ad.date
    ORDER BY s.brand, s.pack_type, s.pack_size, s.pack, s.sub_type, ad.date
    """

    ref_df, pricing_df, vis_df = await asyncio.gather(
        asyncio.to_thread(db.query, ref_query),
        asyncio.to_thread(db.query, pricing_query),
        asyncio.to_thread(db.query, vis_query),
    )

    hero_skus = ref_df.to_dicts()

    # Collect the 6 global week dates (sorted oldest → newest)
    weeks: list = sorted({
        row.get("date") for row in pricing_df.to_dicts() if row.get("date") is not None
    })

    # Pricing lookup: (brand, pack_type, pack_size, pack, sub_type, date) → eff_price
    pricing_lookup: dict[tuple, float | None] = {}
    for row in pricing_df.to_dicts():
        if row.get("brand") is None:
            continue
        key = (
            (row["brand"] or "").strip(),
            (row.get("pack_type") or "").strip(),
            _normalize_pack_size(row.get("pack_size") or ""),
            row.get("pack"),
            (row.get("sub_type") or "").strip(),
            row["date"],
        )
        pricing_lookup[key] = row.get("eff_price")

    # Visibility lookup: (brand, pack_type, pack_size, pack, sub_type, date) → {top10, fp}
    vis_lookup: dict[tuple, dict] = {}
    for row in vis_df.to_dicts():
        if row.get("brand") is None:
            continue
        key = (
            (row["brand"] or "").strip(),
            (row.get("pack_type") or "").strip(),
            _normalize_pack_size(row.get("pack_size") or ""),
            row.get("pack"),
            (row.get("sub_type") or "").strip(),
            row["date"],
        )
        vis_lookup[key] = {
            "top10_pct":      row.get("top10_pct"),
            "first_page_pct": row.get("first_page_pct"),
        }

    def _build_row(sku: dict) -> dict:
        brand     = (sku.get("brand")     or "").strip()
        pack_type = (sku.get("pack_type") or "").strip()
        pack_size = _normalize_pack_size(sku.get("pack_size") or "")
        pack      = sku.get("pack")
        sub_type  = (sku.get("sub_type")  or "").strip()
        category  = (sku.get("category")  or "").strip()

        pricing_series:    list = []
        top10_series:      list = []
        first_page_series: list = []

        for w in weeks:
            pkey = (brand, pack_type, pack_size, pack, sub_type, w)
            p = pricing_lookup.get(pkey)
            pricing_series.append(float(round(float(p), 2)) if p is not None else None)
            vdata = vis_lookup.get(pkey, {})
            t = vdata.get("top10_pct")
            f = vdata.get("first_page_pct")
            top10_series.append(int(t) if t is not None else None)
            first_page_series.append(int(f) if f is not None else None)

        # Per-week deltas (WoW % change for pricing, pt change for visibility)
        # First element is always None (no prior week to compare)
        def _price_deltas(series: list) -> list:
            out = [None]
            for i in range(1, len(series)):
                cur, prev = series[i], series[i - 1]
                if cur is not None and prev is not None and float(prev) != 0:
                    out.append(round((float(cur) - float(prev)) / float(prev) * 100, 1))
                else:
                    out.append(None)
            return out

        def _pt_deltas(series: list) -> list:
            out = [None]
            for i in range(1, len(series)):
                cur, prev = series[i], series[i - 1]
                out.append((int(cur) - int(prev)) if (cur is not None and prev is not None) else None)
            return out

        pricing_deltas    = _price_deltas(pricing_series)
        top10_deltas      = _pt_deltas(top10_series)
        first_page_deltas = _pt_deltas(first_page_series)

        brand_display = brand.title()
        sub_label     = sub_type if sub_type and sub_type != "regular" else "reg"
        sku_label     = f"{brand_display} · {pack_type} {pack_size.lower()} {pack} {sub_label}"

        return {
            "category":             category,
            "segment":              _CATEGORY_DISPLAY.get(category, category.title()),
            "brand":                brand,
            "brand_display":        brand_display,
            "sku_label":            sku_label,
            "pack_type":            pack_type,
            "pack_size":            pack_size.lower(),
            "pack":                 pack,
            "sub_type":             sub_type,
            "pricing":              pricing_series,
            "pricing_deltas":       pricing_deltas,
            "top10_pct":            top10_series,
            "top10_deltas":         top10_deltas,
            "first_page_pct":       first_page_series,
            "first_page_deltas":    first_page_deltas,
            "pricing_currency":     pricing_currency,
        }

    portfolio_rows: list[dict] = []
    competitor_rows: list[dict] = []

    for sku in hero_skus:
        row = _build_row(sku)
        brand = (sku.get("brand") or "").strip().lower()
        if brand in _HERO_PORTFOLIO_BRANDS:
            portfolio_rows.append(row)
        else:
            competitor_rows.append(row)

    return {
        "weeks": [str(w) for w in weeks],
        "sections": [
            {
                "section": "our_portfolio",
                "label":   "Our portfolio",
                "rows":    portfolio_rows,
            },
            {
                "section": "key_competitors",
                "label":   "Key competitors · own week-on-week movement",
                "rows":    competitor_rows,
            },
        ],
        "pricing_currency": pricing_currency,
    }


# ── Hero SKU Effective Price Trend (9-week graph) ─────────────────────────────

async def fetch_hero_sku_price_trend(filters: dict | None = None):
    table_ref = DEFAULT_TABLE_REF
    date_cols = _default_table_columns()

    date_column = next(
        (
            c for c in [
                "date", "snapshot_date", "captured_at", "created_at",
                "updated_at", "scraped_at", "crawl_date", "ingested_at", "timestamp",
            ]
            if c in date_cols
        ),
        None,
    )
    if not date_column:
        raise ValueError(f"No supported date column found in {table_ref}.")

    date_expr = _get_trend_date_expression(date_column)
    list_col, promo_col = _get_price_columns(filters)
    pricing_currency = _get_pricing_currency(filters)
    filter_conditions = _build_common_filter_conditions(filters)
    and_filters = (
        "\n          AND " + "\n          AND ".join(filter_conditions)
        if filter_conditions else ""
    )
    avail_filter = (
        "\n          AND LOWER(TRIM(COALESCE(availability::text, ''))) IN ('yes', 'true', '1', 'y')"
        if "availability" in date_cols else ""
    )

    start_date = (filters or {}).get("start_date")
    end_date = (filters or {}).get("end_date")
    if start_date:
        start_date = _validate_iso_date(start_date)
    if end_date:
        end_date = _validate_iso_date(end_date)

    # Both bounds required to activate a custom range (matches how the
    # frontend always sends them together); with only one, or neither,
    # fall back to the default last-9-weeks window unchanged.
    if start_date and end_date:
        all_dates_body = f"""
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND DATE_TRUNC('day', ({date_expr}))::date BETWEEN '{start_date}'::date AND '{end_date}'::date
        """
    else:
        all_dates_body = f"""
        SELECT DISTINCT DATE_TRUNC('day', ({date_expr}))::date AS date
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
        ORDER BY date DESC
        LIMIT 9
        """

    ref_query = """
    SELECT
        LOWER(TRIM(brand))      AS brand,
        TRIM(pack_type)         AS pack_type,
        UPPER(TRIM(pack_size))  AS pack_size,
        pack,
        LOWER(TRIM(sub_type))   AS sub_type,
        LOWER(TRIM(category))   AS category
    FROM beer_pricing_analysis.beer_sku_reference
    ORDER BY category, brand, pack_type, pack_size, sub_type
    """

    pricing_query = f"""
    WITH all_dates AS (
        {all_dates_body}
    ),
    base AS (
        SELECT
            DATE_TRUNC('day', ({date_expr}))::date                      AS date,
            {_hero_sku_brand_remap_sql()}                                 AS brand,
            TRIM(pack_format)                                             AS pack_type,
            REGEXP_REPLACE(UPPER(TRIM(quantity)), '\\.0([A-Z]+)$', '\\1') AS pack_size,
            units                                                         AS pack,
            CASE
                WHEN LOWER(TRIM(COALESCE(sub_type, ''))) = '' THEN 'regular'
                ELSE LOWER(TRIM(sub_type))
            END                                                           AS sub_type,
            {list_col}  AS regular_price,
            {promo_col} AS promo_price
        FROM {table_ref}
        WHERE ({date_expr}) IS NOT NULL
          AND cleaned_brand IS NOT NULL
          AND TRIM(cleaned_brand) <> ''
          AND DATE_TRUNC('day', ({date_expr}))::date IN (SELECT date FROM all_dates)
          {and_filters}{avail_filter}
    ),
    retailer_daily AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
               ROUND(AVG(promo_price)::numeric, 2)   AS promo_price
        FROM base
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    ),
    sku_weekly AS (
        SELECT date, brand, pack_type, pack_size, pack, sub_type,
               ROUND(AVG(regular_price)::numeric, 2) AS regular_price,
               ROUND(AVG(promo_price)::numeric, 2)   AS promo_price
        FROM retailer_daily
        GROUP BY date, brand, pack_type, pack_size, pack, sub_type
    )
    SELECT
        ad.date,
        s.brand, s.pack_type, s.pack_size, s.pack, s.sub_type,
        s.regular_price,
        s.promo_price,
        CASE
            WHEN s.promo_price IS NOT NULL AND s.promo_price < s.regular_price
            THEN s.promo_price
            ELSE s.regular_price
        END AS eff_price
    FROM all_dates ad
    LEFT JOIN sku_weekly s ON s.date = ad.date
    ORDER BY s.brand, s.pack_type, s.pack_size, s.pack, s.sub_type, ad.date
    """

    ref_df, pricing_df = await asyncio.gather(
        asyncio.to_thread(db.query, ref_query),
        asyncio.to_thread(db.query, pricing_query),
    )

    hero_skus = ref_df.to_dicts()

    weeks: list = sorted({
        row["date"] for row in pricing_df.to_dicts() if row.get("date") is not None
    })

    # (brand, pack_type, pack_size, pack, sub_type, date) → eff_price
    pricing_lookup: dict[tuple, float | None] = {}
    for row in pricing_df.to_dicts():
        if row.get("brand") is None:
            continue
        key = (
            (row["brand"] or "").strip(),
            (row.get("pack_type") or "").strip(),
            _normalize_pack_size(row.get("pack_size") or ""),
            row.get("pack"),
            (row.get("sub_type") or "").strip(),
            row["date"],
        )
        pricing_lookup[key] = row.get("eff_price")

    rows: list[dict] = []
    for sku in hero_skus:
        brand     = (sku.get("brand")     or "").strip()
        pack_type = (sku.get("pack_type") or "").strip()
        pack_size = _normalize_pack_size(sku.get("pack_size") or "")
        pack      = sku.get("pack")
        sub_type  = (sku.get("sub_type")  or "").strip()
        category  = (sku.get("category")  or "").strip()

        eff_series: list = []
        for w in weeks:
            p = pricing_lookup.get((brand, pack_type, pack_size, pack, sub_type, w))
            eff_series.append(float(round(float(p), 2)) if p is not None else None)

        deltas: list = [None]
        for i in range(1, len(eff_series)):
            cur, prev = eff_series[i], eff_series[i - 1]
            if cur is not None and prev is not None and float(prev) != 0:
                deltas.append(round((float(cur) - float(prev)) / float(prev) * 100, 1))
            else:
                deltas.append(None)

        brand_display = brand.title()
        sub_label     = sub_type if sub_type and sub_type != "regular" else "reg"
        sku_label     = f"{brand_display} · {pack_type} {pack_size.lower()} {pack} {sub_label}"

        rows.append({
            "category":         category,
            "segment":          _CATEGORY_DISPLAY.get(category, category.title()),
            "brand":            brand,
            "brand_display":    brand_display,
            "sku_label":        sku_label,
            "pack_type":        pack_type,
            "pack_size":        pack_size.lower(),
            "pack":             pack,
            "sub_type":         sub_type,
            "eff_price":        eff_series,
            "eff_price_deltas": deltas,
            "pricing_currency": pricing_currency,
        })

    return {
        "weeks":            [str(w) for w in weeks],
        "skus":             rows,
        "pricing_currency": pricing_currency,
    }
