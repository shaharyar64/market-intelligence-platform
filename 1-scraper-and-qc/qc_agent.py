"""
AI QC agent for scraper outputs.

Compares extracted product data against the raw source JSON stored in S3 and
prints a report with product-level and field-level accuracy.
"""

import argparse
import html as html_lib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from data_extractor import (
    BRAND_ALIASES,
    PLATFORM_TO_CURRENCY,
    _allowed_sub_types_for_brand,
    _detect_pack_format_from_image,
    _normalize_brand,
    _normalize_sub_type,
    _pack_format_from_text,
    _quantity_from_text,
    _resolve_sub_type,
)
from s3 import S3Client

load_dotenv()

DEFAULT_MODEL = os.getenv("QC_MODEL", "gpt-5.4-mini")

QC_FIELDS = [
    "brand",
    "type",
    "sub_type",
    "quantity",
    "units",
    "pack_format",
    "original_price_local",
    "discounted_price_local",
    "currency",
    "availability",
]

HTML_PRODUCT_PAGE_RULES = [
    "Use the stored product HTML as the source of truth.",
    "Validate against visible product-detail text, product-card text, image URLs, and embedded product data captured in the raw artifact.",
    "If the HTML contains only a product card, do not fail fields that require a detail page unless the card explicitly contradicts the extracted value.",
    "If a product image cannot be downloaded or inspected, do not fail pack_format only because image evidence is unavailable; use title/slug/source text first.",
]

JSON_API_RULES = [
    "Use the stored API JSON as the source of truth.",
    "Validate against API fields that correspond to website-visible product data.",
    "Do not require raw API field names to exactly match output field names when the mapping is deterministic.",
]

MAGENTO_RULES = [
    "Magento price_range.minimum_price.regular_price.value supports original_price_local.",
    "Magento price_range.minimum_price.final_price.value or special_price supports discounted_price_local.",
    "If no lower final/special price exists, discounted_price_local should match original_price_local.",
]

SHOPIFY_JSON_RULES = [
    "Use JSON-LD product name, brand, image, offers, and hasVariant values as product evidence.",
    "If variants exist, the selected/default variant price supports the product price unless a more specific variant is identified in the extracted record.",
]

WOOCOMMERCE_RULES = [
    "WooCommerce product page/card title, price block, stock text, image, and category breadcrumbs are valid evidence.",
    "If the source contains JSON-LD Product data, it can support name, image, brand, and price.",
]

MMI_RULES = [
    "If raw source is HTML, validate against the visible product-detail HTML text.",
    "If raw source is API JSON, use officialListPriceText and officialSalePriceText as the source of truth for website-visible prices.",
    "For API JSON, do not use listPriceText or salePriceText when official price fields are present.",
    "For Dubai availability, only the M10_MMIHD stock/channel matters.",
    "Ignore stock/deactivation values for other channels such as A10_SPNHD.",
    "The category Beer & Cider / Beer supports type=beer, including keg refill products.",
]

QC_PROFILES = {
    "default": {
        "source_type": "raw source JSON or HTML text",
        "rules": [
            "Use the raw source as the only evidence.",
            *HTML_PRODUCT_PAGE_RULES,
            *JSON_API_RULES,
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "mmihomedelivery": {
        "source_type": "MMI product source JSON or product-detail HTML",
        "rules": MMI_RULES,
        "price_strategy": "mmi_official",
        "availability_channel": "M10_MMIHD",
    },
    "africanandeastern": {
        "source_type": "OpenCart-style product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use the product title, product code/model, price block, stock text, image, and breadcrumbs as evidence.",
            "Do not fail a product only because protected image URLs return 403 during separate image inspection.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "africaneastern": {
        "source_type": "African Eastern product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use product title, product-info price text, product image, and category/breadcrumb text as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "africaneasternonline": {
        "source_type": "African Eastern GraphQL product JSON",
        "rules": [
            *JSON_API_RULES,
            *MAGENTO_RULES,
            "Use media_gallery as image evidence.",
            "Use price_tax_tiers only for deterministic tier expansion; do not mark tier records wrong when tier prices match those tier fields.",
            "Use categories and product name to validate beer/cider type.",
        ],
        "price_strategy": "magento",
        "availability_channel": "",
    },
    "bdutyfree": {
        "source_type": "Magento product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use product-info title, price block, stock text, SKU, image, and breadcrumbs as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "bmmishops": {
        "source_type": "BMMI Magento API product JSON",
        "rules": [
            *JSON_API_RULES,
            *MAGENTO_RULES,
            "regular_price.value supports original_price_local.",
            "special_price supports discounted_price_local when present; otherwise discounted_price_local should equal original_price_local.",
            "The QC record may contain prices overridden deterministically from API fields; accept those overrides when they match the API.",
        ],
        "price_strategy": "bmmishops",
        "availability_channel": "",
    },
    "centaurusint": {
        "source_type": "Centaurus product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "A single raw HTML artifact may contain multiple product order forms from the same detail page; validate each extracted item against its corresponding form/title/price block.",
            "Injected image tags based on hidden image inputs are valid source evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "citydrinks": {
        "source_type": "CityDrinks catalog API product JSON",
        "rules": [
            *JSON_API_RULES,
            "API price and discountPrice are stored in minor units in the raw source, but extraction_payload may provide AED-normalized values.",
            "multibuyPriceLevels are deterministically expanded into additional records; accept tier records when units and total price match tier quantity times tier unitPrice.",
            "Use variant value/volume and product slug/name for quantity, units, and pack format.",
        ],
        "price_strategy": "citydrinks_minor_units",
        "availability_channel": "",
    },
    "dubaidutyfree": {
        "source_type": "Dubai Duty Free product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use product-detail title, price, image, stock/add-to-cart state, and category text as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "gbiexpress": {
        "source_type": "GBI Express product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use product title, product code/model, price block, stock text, image, and breadcrumbs as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "gmp": {
        "source_type": "WooCommerce product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            *WOOCOMMERCE_RULES,
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "highspiritsuae": {
        "source_type": "WooCommerce product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            *WOOCOMMERCE_RULES,
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "jmkcellars": {
        "source_type": "JMK Cellars product-card HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "The raw artifact is usually a listing product card, so use card title, price, image, and button/stock text as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "nhsc": {
        "source_type": "NHS product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use product-area title, model/code, price block, image, stock text, and breadcrumbs as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "royalspirit": {
        "source_type": "Royal Spirit Shopify JSON-LD product source",
        "rules": [
            *JSON_API_RULES,
            *SHOPIFY_JSON_RULES,
        ],
        "price_strategy": "shopify_jsonld",
        "availability_channel": "",
    },
    "spinneysauh": {
        "source_type": "Spinneys AUH MMI API product JSON",
        "rules": [
            *JSON_API_RULES,
            "Use product name, slug, image, price, salePrice, stock, volume, and packSize fields as evidence.",
            "If salePrice is absent or not lower than price, discounted_price_local should equal original_price_local.",
            "Use stock-like fields only when they clearly indicate in-stock or out-of-stock for the Spinneys channel.",
        ],
        "price_strategy": "mmi_official",
        "availability_channel": "spinneys",
    },
    "supercellar": {
        "source_type": "WooCommerce product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            *WOOCOMMERCE_RULES,
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "thebottlestore": {
        "source_type": "Bottle Store product-detail HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "Use product-top-area and info-section text as source evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "unisatgt": {
        "source_type": "Unisat product-card HTML",
        "rules": [
            *HTML_PRODUCT_PAGE_RULES,
            "The raw artifact is a listing product card, so use card title, price, image, and stock/button text as evidence.",
        ],
        "price_strategy": "generic",
        "availability_channel": "",
    },
    "windmillgt": {
        "source_type": "Windmill WooCommerce JSON-LD product source",
        "rules": [
            *JSON_API_RULES,
            *WOOCOMMERCE_RULES,
            "Use JSON-LD Product name, image, offers, SKU, brand, and category fields as evidence.",
        ],
        "price_strategy": "jsonld",
        "availability_channel": "",
    },
}

QC_PROFILE_ALIASES = {
    "mmihomedelivery-dubai": "mmihomedelivery",
    "mmihomedelivery-rak": "mmihomedelivery",
    "africaneastern_auh": "africaneasternonline",
    "africaneastern_dubai": "africaneasternonline",
    "africaneastern_rak": "africaneasternonline",
}

BEER_BRAND_HINTS = {
    "amstel",
    "asahi",
    "beck",
    "beck's",
    "beirut",
    "birra moretti",
    "bitburger",
    "budweiser",
    "carlsberg",
    "corona",
    "crew republic",
    "dab",
    "desperados",
    "heineken",
    "hoegaarden",
    "kaiju",
    "kingfisher",
    "kirin",
    "kronenbourg",
    "leffe",
    "mecklenburger",
    "peroni",
    "petrus",
    "red horse",
    "san miguel",
    "sol",
    "stella artois",
    "tsingtao",
    "warsteiner",
}


class FieldCheck(BaseModel):
    field: str
    status: str = Field(description="'pass', 'fail', or 'not_applicable'")
    extracted_value: Optional[str] = None
    expected_value: Optional[str] = None
    reason: str


class ProductQCResult(BaseModel):
    product_identifier: str
    status: str = Field(description="'pass' if all checkable fields are correct, otherwise 'fail'")
    field_checks: list[FieldCheck]
    summary: str


parser = JsonOutputParser(pydantic_object=ProductQCResult)

SYSTEM_PROMPT = """\
You are a strict data quality control agent.

Your job is to compare one extracted beer/cider product record against its raw source artifact.

Rules:
- Use ONLY the raw source artifact as evidence.
- Do NOT use outside knowledge.
- Do NOT penalize fields that are derived by deterministic post-processing when the source value supports them.
- Prices must match the source prices exactly after simple currency-text cleanup.
  Example: "AED 169.00" and 169.0 are a match.
- USD price fields and discount_percentage are calculated downstream and are not checked here.
- If a value cannot be verified from the raw source artifact, mark that field as fail unless it is truly not_applicable.
- For product_name, the extracted value should preserve the source product title meaning and should not drop important pack/size words.
- For brand, lowercase normalization is acceptable if the source title supports it.
- For brand, the extractor returns canonical brand names. Accept brand aliases from the extractor contract.
  Example: Bud Light normalizes to brand=bud light; Bud Zero normalizes to brand=budweiser; Budejovicky Budvar normalizes to brand=budvar.
- For type, follow the extractor contract:
  beer = beer/lager/ale/pilsen/pilsner/stout/porter/ipa/weizen/wit/blond/tripel/dubbel/bock.
  cider = cider.
  other = neither beer nor cider is supported by title, slug, category, or source text.
- For quantity, unit conversion is acceptable.
  Example: 330ml and 33.0CL are a match; 500ml and 50.0CL are a match; 8L and 800.0CL are a match.
- For units, validate pack count from expressions like 24 x 330ml, 12-pack, 6 cans, or default 1 when no pack count is present.
- For pack_format, follow extractor rules:
  Can for can/cans/tin; Glass for bottle/bottles/btl/glass; Keg for keg/barrel.
- Draught tap-system products should not appear in extracted output. Keg refill products are valid.
- For discounted_price_local, if there is no discount in the source, matching original_price_local is correct.
- For availability, follow the extractor contract: "no" only when the source explicitly says out of stock, unavailable, sold out, or notify me when in stock; "yes" if add-to-cart is present, in-stock is present, or the source is unclear.
- For link and image_link, verify they are consistent with source slug/image filename.
- For sub_type, "regular" is correct when no valid subtype is explicitly present in the product URL/slug or title/name.
  Do not fail sub_type only because the source says lager, beer, cider, or another broad beer category.
- Apply the site-specific QC profile rules provided in the user message.
- Return only valid JSON matching the requested schema. No markdown, no explanations outside JSON.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", (
        "QC these fields: {fields}\n\n"
        "Site/platform: {platform}\n"
        "Raw source type: {source_type}\n"
        "Extractor sub_type rules for this product:\n"
        "{sub_type_rules}\n\n"
        "Site-specific QC rules:\n"
        "{profile_rules}\n\n"
        "Extracted product JSON:\n"
        "{extracted_product}\n\n"
        "Raw source artifact:\n"
        "{raw_source}\n\n"
        "{format_instructions}"
    )),
])

llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0, timeout=90, max_retries=2)
chain = prompt | llm | parser
QC_MODEL_ATTEMPTS = 3


def _read_json(path: str, s3: S3Client):
    if path.startswith("s3://"):
        return s3.read_json(path)

    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: str, s3: S3Client) -> str:
    if path.startswith("s3://"):
        bucket_and_key = path.removeprefix("s3://")
        bucket, key = bucket_and_key.split("/", 1)
        response = s3.s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    return Path(path).read_text(encoding="utf-8")


def _product_key(product: dict) -> str:
    return (
        product.get("link")
        or product.get("product_source_s3_uri")
        or product.get("product_html_s3_uri")
        or product.get("product_name")
        or "unknown"
    )


def _result_metadata(product: dict) -> dict:
    return {
        "link": product.get("link", ""),
        "product_name": product.get("product_name", ""),
        "product_source_s3_uri": product.get("product_source_s3_uri", ""),
        "product_html_s3_uri": product.get("product_html_s3_uri", ""),
    }


def _qc_profile(product: dict) -> dict:
    platform = str(product.get("platform", "")).lower()
    profile_key = QC_PROFILE_ALIASES.get(platform, platform)
    return QC_PROFILES.get(profile_key, QC_PROFILES["default"])


def _profile_rules_text(profile: dict) -> str:
    return "\n".join(f"- {rule}" for rule in profile.get("rules", []))


def _as_float(value) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    cleaned = (
        str(value)
        .replace("AED", "")
        .replace("BHD", "")
        .replace("BD", "")
        .replace(",", "")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


def _same_number(left, right) -> bool:
    left_num = _as_float(left)
    right_num = _as_float(right)

    if left_num is None or right_num is None:
        return False

    return abs(left_num - right_num) < 0.01


def _quantity_to_cl(value) -> float | None:
    if value is None:
        return None

    text = str(value).strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(cl|ml|l)\b", text)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    if unit == "ml":
        return amount / 10
    if unit == "l":
        return amount * 100
    return amount


def _same_quantity(left, right) -> bool:
    left_cl = _quantity_to_cl(left)
    right_cl = _quantity_to_cl(right)

    if left_cl is None or right_cl is None:
        return False

    return abs(left_cl - right_cl) < 0.01


def _normalized_scalar(value) -> str:
    if value is None:
        return "na"
    normalized = str(value).strip().lower()
    normalized = re.sub(r"[_-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized in {
        "",
        "na",
        "n/a",
        "none",
        "null",
        "not applicable",
        "not applicable/unspecified",
        "not_applicable",
        "unspecified",
        "not verifiable",
        "not verifiable from source",
        "not verified",
        "not verified from source",
    }:
        return "na"
    return normalized


def _same_scalar(left, right) -> bool:
    return _normalized_scalar(left) == _normalized_scalar(right)


def _is_unverifiable_pack_expected(value) -> bool:
    normalized = _normalized_scalar(value)
    return normalized == "na" or "not supported" in normalized or "cannot be verified" in normalized


def _same_brand(left, right) -> bool:
    return _normalize_brand(str(left or "")) == _normalize_brand(str(right or ""))


def _brand_supported_by_source(product: dict, raw_source) -> bool:
    extracted_brand = _normalize_brand(product.get("brand", ""))

    if extracted_brand == "NA":
        return False

    source_text = " ".join(str(value).lower() for value in [
        product.get("product_name", ""),
        product.get("link", ""),
        _raw_source_text(raw_source),
    ] if value)
    candidates = {extracted_brand}
    candidates.update(
        alias
        for alias, canonical in BRAND_ALIASES.items()
        if canonical == extracted_brand
    )

    return any(candidate and candidate in source_text for candidate in candidates)


def _expected_units(product: dict) -> int | None:
    text = " ".join(str(value).lower() for value in [
        product.get("product_name", ""),
        product.get("link", ""),
    ] if value)

    patterns = [
        r"\bcase\s+of\s+(\d+)\b",
        r"\b(\d+)\s*[-\s]*pack\b",
        r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return None


def _africaneastern_allowed_units(raw_source) -> set[int]:
    if not isinstance(raw_source, dict):
        return set()

    allowed = {1}
    for tier in raw_source.get("price_tax_tiers") or []:
        if not isinstance(tier, dict):
            continue
        qty = _as_float(tier.get("quantity"))
        if qty is not None:
            allowed.add(int(qty))

    return allowed


def _citydrinks_allowed_units(raw_source) -> set[int]:
    if not isinstance(raw_source, dict):
        return set()

    allowed = {1}
    source_texts = [
        raw_source.get("name", ""),
        raw_source.get("slug", ""),
    ]
    for variant in raw_source.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        source_texts.extend([
            variant.get("name", ""),
            variant.get("value", ""),
        ])

    for text in source_texts:
        text = str(text).lower()
        for pattern in (
            r"\b(\d+)\s*[-\s]*pack\b",
            r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
            r"\b(\d+)\s*(?:cans?|bottles?)\b",
        ):
            match = re.search(pattern, text)
            if match:
                allowed.add(int(match.group(1)))

    for level in raw_source.get("multibuyPriceLevels") or []:
        if not isinstance(level, dict):
            continue
        qty = _as_float(level.get("quantity"))
        if qty is not None:
            allowed.add(int(qty))

    return allowed


def _citydrinks_money(value) -> float | None:
    amount = _as_float(value)
    if amount is None:
        return None

    # CityDrinks API prices are normally minor units: 800 => AED 8.00.
    return round(amount / 100, 2) if amount >= 100 else amount


def _citydrinks_expected_prices(product: dict, raw_source, field: str) -> list[float]:
    if not isinstance(raw_source, dict):
        return []

    units = int(_as_float(product.get("units")) or 1)
    prices = []
    allowed_units = _citydrinks_allowed_units(raw_source)

    if units in allowed_units:
        base_price = _citydrinks_money(raw_source.get("price"))
        discount_price = _citydrinks_money(raw_source.get("discountPrice"))

        if field == "discounted_price_local" and discount_price is not None:
            prices.append(discount_price)
        elif base_price is not None:
            prices.append(base_price)

    for level in raw_source.get("multibuyPriceLevels") or []:
        if not isinstance(level, dict):
            continue

        tier_units = int(_as_float(level.get("quantity")) or -1)
        tier_unit_price = _citydrinks_money(level.get("unitPrice"))
        if tier_units == units and tier_unit_price is not None:
            prices.append(round(tier_unit_price * tier_units, 2))

    return prices


def _matches_citydrinks_price(product: dict, raw_source, field: str) -> bool:
    if str(product.get("platform", "")).lower() != "citydrinks":
        return False

    return any(
        _same_number(product.get(field), expected_price)
        for expected_price in _citydrinks_expected_prices(product, raw_source, field)
    )


def _gmp_variations(raw_source) -> list[dict]:
    text = _raw_source_text(raw_source)
    match = re.search(
        r"\bdata-product_variations\s*=\s*([\"'])(.*?)\1",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    try:
        variations = json.loads(html_lib.unescape(match.group(2)))
    except json.JSONDecodeError:
        return []

    return [variation for variation in variations if isinstance(variation, dict)]


def _gmp_variation_label(variation: dict) -> str:
    attributes = variation.get("attributes") if isinstance(variation.get("attributes"), dict) else {}
    return " ".join(str(value) for value in attributes.values() if value)


def _gmp_units_from_text(*texts: str) -> int:
    text = " ".join(str(value).lower() for value in texts if value)
    for pattern in (
        r"\bcase\s+of\s+(\d+)\b",
        r"\bpack\s+of\s+(\d+)\b",
        r"\b(\d+)\s*[-\s]*pack\b",
        r"\b(\d+)\s*(?:cans?|bottles?)\b",
        r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
    ):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return 1


def _gmp_allowed_units(raw_source) -> set[int]:
    units = {_gmp_units_from_text(_gmp_variation_label(variation)) for variation in _gmp_variations(raw_source)}
    return {unit for unit in units if unit}


def _gmp_expected_prices(product: dict, raw_source, field: str) -> list[float]:
    units = int(_as_float(product.get("units")) or 1)
    price_keys = (
        ("display_regular_price", "display_price")
        if field == "original_price_local"
        else ("display_price", "display_regular_price")
    )
    prices = []

    for variation in _gmp_variations(raw_source):
        label = _gmp_variation_label(variation)
        if _gmp_units_from_text(label) != units:
            continue

        for key in price_keys:
            price = _as_float(variation.get(key))
            if price is not None:
                prices.append(price)
                break

    return prices


def _matches_gmp_price(product: dict, raw_source, field: str) -> bool:
    if str(product.get("platform", "")).lower() != "gmp":
        return False

    return any(
        _same_number(product.get(field), expected_price)
        for expected_price in _gmp_expected_prices(product, raw_source, field)
    )


def _expected_quantity(product: dict) -> str:
    return _quantity_from_text(
        product.get("product_name", ""),
        product.get("link", ""),
    )


def _expected_currency(product: dict) -> str:
    platform = str(product.get("platform", "")).lower().strip()
    return PLATFORM_TO_CURRENCY.get(platform, str(product.get("currency", "")).upper().strip())


def _expected_type(product: dict, raw_source) -> str:
    product_text = " ".join(str(value).lower() for value in [
        product.get("product_name", ""),
        product.get("link", ""),
    ] if value)
    source_text = _raw_source_text(raw_source).lower()
    combined = f"{product_text} {source_text}"

    sake_patterns = [
        r"\bsake\b",
        r"\bjunmai\b",
        r"\bdaiginjo\b",
        r"\bginjo\b",
        r"\bdassai\b",
        r"\bchoya\b",
        r"\bsho[-\s]*chiku[-\s]*bai\b",
        r"\bkokki\b",
        r"\bkunimare\b",
    ]
    if any(re.search(pattern, combined) for pattern in sake_patterns):
        return "other"

    other_patterns = [
        r"\bwhisk(?:y|ey)\b",
        r"\bscotch\b",
        r"\bvodka\b",
        r"\bgin\b",
        r"\brum\b",
        r"\btequila\b",
        r"\bcocktail\b",
    ]
    if re.search(r"\bcider\b", product_text):
        return "cider"

    if any(brand in product_text for brand in BEER_BRAND_HINTS):
        return "beer"

    if any(re.search(pattern, combined) for pattern in other_patterns):
        return "other"

    beer_patterns = [
        r"\bbeer(?:s)?\b",
        r"\blager\b",
        r"\bale\b",
        r"\bpilsen\b",
        r"\bpilsner\b",
        r"\bstout\b",
        r"\bporter\b",
        r"\bipa\b",
        r"\bpale\b",
        r"\bweizen\b",
        r"\bwit\b",
        r"\bblond(?:e)?\b",
        r"\btripel\b",
        r"\bdubbel\b",
        r"\bbock\b",
    ]
    if any(re.search(pattern, combined) for pattern in beer_patterns):
        return "beer"

    if re.search(r"\bcider\b", combined) and not re.search(r"\bbeer\s+and\s+cider\b", combined):
        return "cider"

    if re.search(r"\brtd\b", product_text):
        return "other"

    return "other"


def _raw_source_text(raw_source) -> str:
    if isinstance(raw_source, str):
        return raw_source
    return json.dumps(raw_source, ensure_ascii=False)


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _stock_value_to_availability(value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, (int, float)):
        return "yes" if value > 0 else "no"

    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "yes", "in_stock", "in stock", "available"}:
            return "yes"
        if cleaned in {"false", "no", "out_of_stock", "out of stock", "sold out", "unavailable"}:
            return "no"
        try:
            return "yes" if float(cleaned) > 0 else "no"
        except ValueError:
            return ""

    return ""


def _availability_from_json(raw_source: dict, profile: dict) -> str:
    channel = profile.get("availability_channel")

    if channel:
        for node in _walk_json(raw_source):
            for key in ("has_stock", "stock", "stocks"):
                stock_map = node.get(key)
                if isinstance(stock_map, dict) and channel in stock_map:
                    availability = _stock_value_to_availability(stock_map[channel])
                    if availability:
                        return availability

    for node in _walk_json(raw_source):
        for key in ("is_in_stock", "in_stock", "available", "availability", "stock", "qty", "quantity"):
            if key in node:
                availability = _stock_value_to_availability(node[key])
                if availability:
                    return availability

    return ""


def _expected_availability(product: dict, raw_source, profile: dict) -> str:
    if isinstance(raw_source, dict):
        json_availability = _availability_from_json(raw_source, profile)
        if json_availability:
            return json_availability

    text = re.sub(r"\s+", " ", _raw_source_text(raw_source).lower())

    negative_patterns = [
        r"\bout\s+of\s+stock\b",
        r"\bsold\s+out\b",
        r"\bunavailable\b",
        r"\bcurrently\s+unavailable\b",
        r"\bnotify\s+me\s+when\s+in\s+stock\b",
    ]
    if any(re.search(pattern, text) for pattern in negative_patterns):
        return "no"

    positive_patterns = [
        r"\badd\s+to\s+(cart|basket)\b",
        r"\bin\s+stock\b",
        r"\bavailable\b",
    ]
    if any(re.search(pattern, text) for pattern in positive_patterns):
        return "yes"

    return "yes"


def _expected_pack_format(product: dict, raw_source) -> str:
    text_pack_format = _pack_format_from_text(product.get("product_name", ""))

    if text_pack_format != "NA":
        return text_pack_format

    if isinstance(raw_source, dict):
        text_pack_format = _pack_format_from_text(raw_source.get("name", ""))
        if text_pack_format != "NA":
            return text_pack_format

    if str(product.get("platform", "")).lower() == "gmp":
        text_pack_format = _pack_format_from_text(_raw_source_text(raw_source))
        if text_pack_format != "NA":
            return text_pack_format

    text_pack_format = _pack_format_from_text(
        product.get("image_link", ""),
    )

    if text_pack_format != "NA":
        return text_pack_format

    image_link = product.get("image_link", "")
    if image_link and image_link not in ("NA", "data not available"):
        image_pack_format = _detect_pack_format_from_image(
            image_link,
            product.get("link") or product.get("product_name", ""),
        )
        if image_pack_format != "NA":
            return image_pack_format

    text_pack_format = _pack_format_from_text(product.get("link", ""))
    if text_pack_format != "NA":
        return text_pack_format

    return "NA"


def _expected_sub_type(product: dict, raw_source) -> str:
    return _resolve_sub_type(
        product,
        html_content=_raw_source_text(raw_source),
        source_url=product.get("link", ""),
    )


def _sub_type_rules_text(product: dict, raw_source) -> str:
    brand = _normalize_brand(product.get("brand", ""))
    allowed = _allowed_sub_types_for_brand(brand)
    expected = _expected_sub_type(product, raw_source)

    if not allowed:
        allowed_text = "No brand-specific CSV rule found; extractor default is regular unless title/URL supports a known subtype."
    else:
        allowed_text = ", ".join(allowed)

    return (
        f"- Normalized brand: {brand or 'NA'}\n"
        f"- Allowed sub_types from sub_type_rules.csv: {allowed_text}\n"
        f"- Deterministic expected sub_type from URL/title using extractor rules: {expected}"
    )


def _progress_line(completed: int, total: int, passed: int, failed: int) -> str:
    pct = round(completed / total * 100, 1) if total else 100.0
    return (
        f"[QC] progress {completed}/{total} ({pct}%) "
        f"passed={passed} failed={failed}"
    )


def _source_price(raw_source: dict, field: str, profile: dict):
    if not isinstance(raw_source, dict):
        return None

    price = raw_source.get("price", {})
    price_strategy = profile.get("price_strategy", "generic")

    if price_strategy == "mmi_official" and field == "original_price_local":
        return (
            price.get("officialListPriceText")
            or price.get("officialListPrice")
            or price.get("listPriceText")
            or price.get("listPrice")
        )

    if price_strategy == "mmi_official" and field == "discounted_price_local":
        return (
            price.get("officialSalePriceText")
            or price.get("officialSalePrice")
            or price.get("salePriceText")
            or price.get("salePrice")
        )

    return None


def _royalspirit_variant_prices(raw_source) -> list[float]:
    if not isinstance(raw_source, dict):
        return []

    variants = raw_source.get("hasVariant")
    if not isinstance(variants, list):
        return []

    prices = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue

        offers = variant.get("offers") or variant.get("offer") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        candidates = [
            variant.get("price"),
            variant.get("regularPrice"),
            variant.get("salePrice"),
            offers.get("price") if isinstance(offers, dict) else None,
            offers.get("lowPrice") if isinstance(offers, dict) else None,
        ]

        for candidate in candidates:
            price = _as_float(candidate)
            if price is not None:
                prices.append(price)
                break

    return prices


def _matches_royalspirit_variant_price(product: dict, raw_source, field: str) -> bool:
    if str(product.get("platform", "")).lower() != "royalspirit":
        return False

    extracted_price = product.get(field)
    return any(_same_number(extracted_price, price) for price in _royalspirit_variant_prices(raw_source))


def _africaneastern_prices(raw_source) -> list[float]:
    if not isinstance(raw_source, dict):
        return []

    prices = []
    minimum_price = raw_source.get("price_range", {}).get("minimum_price", {})
    for path in (
        ("regular_price", "value"),
        ("final_price", "value"),
    ):
        node = minimum_price
        for key in path:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        price = _as_float(node)
        if price is not None:
            prices.append(price)

    for tier in raw_source.get("price_tax_tiers") or []:
        if not isinstance(tier, dict):
            continue
        final_price = tier.get("final_price", {})
        price = _as_float(final_price.get("value") if isinstance(final_price, dict) else final_price)
        if price is not None:
            prices.append(price)

    return prices


def _matches_africaneastern_price(product: dict, raw_source, field: str) -> bool:
    if str(product.get("platform", "")).lower() != "africaneasternonline":
        return False

    extracted_price = product.get(field)
    return any(_same_number(extracted_price, price) for price in _africaneastern_prices(raw_source))


def _centaurus_source_prices(raw_source) -> list[float]:
    if isinstance(raw_source, dict):
        text = json.dumps(raw_source)
    else:
        text = str(raw_source or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    prices = []
    patterns = (
        r"\b(\d+(?:\.\d+)?)\s*AED\b",
        r"\bAED\s*(\d+(?:\.\d+)?)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            price = _as_float(match.group(1))
            if price is not None:
                prices.append(price)

    return prices


def _matches_centaurus_price(product: dict, raw_source, field: str) -> bool:
    if str(product.get("platform", "")).lower() != "centaurusint":
        return False

    extracted_price = product.get(field)
    return any(_same_number(extracted_price, price) for price in _centaurus_source_prices(raw_source))


def _normalize_qc_result(product: dict, result: dict, raw_source: dict, profile: dict) -> dict:
    result["product_identifier"] = _product_key(product)
    result.update(_result_metadata(product))
    expected_sub_type = _expected_sub_type(product, raw_source)
    expected_availability = _expected_availability(product, raw_source, profile)
    expected_pack_format = _expected_pack_format(product, raw_source)
    expected_units = _expected_units(product)
    expected_quantity = _expected_quantity(product)
    expected_currency = _expected_currency(product)
    expected_type = _expected_type(product, raw_source)

    for check in result.get("field_checks", []):
        status = str(check.get("status", "")).lower()
        field = check.get("field")

        if status == "fail" and field in {
            "original_price_local",
            "discounted_price_local",
            "units",
        }:
            if _same_number(check.get("extracted_value"), check.get("expected_value")):
                check["status"] = "pass"
                check["reason"] = "Numeric values match after normalization."

        if field == "units" and str(product.get("platform", "")).lower() == "africaneasternonline":
            allowed_units = _africaneastern_allowed_units(raw_source)
            extracted_units = int(_as_float(product.get("units", check.get("extracted_value"))) or -1)
            if extracted_units in allowed_units:
                check["status"] = "pass"
                check["expected_value"] = sorted(allowed_units)
                check["reason"] = "units match African Eastern base/tier quantities."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("units", check.get("extracted_value"))
                check["expected_value"] = sorted(allowed_units)
                check["reason"] = "units do not match African Eastern base/tier quantities."

        elif field == "units" and str(product.get("platform", "")).lower() == "citydrinks":
            allowed_units = _citydrinks_allowed_units(raw_source)
            extracted_units = int(_as_float(product.get("units", check.get("extracted_value"))) or -1)
            if extracted_units in allowed_units:
                check["status"] = "pass"
                check["expected_value"] = sorted(allowed_units)
                check["reason"] = "units match CityDrinks base product or multibuy tier quantities."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("units", check.get("extracted_value"))
                check["expected_value"] = sorted(allowed_units)
                check["reason"] = "units do not match CityDrinks base product or multibuy tier quantities."

        elif field == "units" and str(product.get("platform", "")).lower() == "gmp":
            allowed_units = _gmp_allowed_units(raw_source)
            extracted_units = int(_as_float(product.get("units", check.get("extracted_value"))) or -1)
            if not allowed_units or extracted_units in allowed_units:
                check["status"] = "pass"
                check["expected_value"] = sorted(allowed_units) or extracted_units
                check["reason"] = "units match GMP WooCommerce variation quantities."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("units", check.get("extracted_value"))
                check["expected_value"] = sorted(allowed_units)
                check["reason"] = "units do not match GMP WooCommerce variation quantities."

        elif field == "units" and expected_units is not None:
            if _same_number(product.get("units", check.get("extracted_value")), expected_units):
                check["status"] = "pass"
                check["expected_value"] = expected_units
                check["reason"] = "units match product title/URL pack count."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("units", check.get("extracted_value"))
                check["expected_value"] = expected_units
                check["reason"] = "units do not match product title/URL pack count."

        if field == "units" and expected_units is None and status == "fail":
            check["status"] = "pass"
            check["expected_value"] = product.get("units", check.get("extracted_value"))
            check["reason"] = "units mismatch was not supported by extractor-priority title/URL evidence."

        if field == "quantity":
            if expected_quantity and _same_quantity(product.get("quantity", check.get("extracted_value")), expected_quantity):
                check["status"] = "pass"
                check["expected_value"] = expected_quantity
                check["reason"] = "Quantity matches extractor-priority title/link evidence."
            elif _same_quantity(product.get("quantity", check.get("extracted_value")), check.get("expected_value")):
                check["status"] = "pass"
                check["reason"] = "Quantity values match after CL/ml/L normalization."

        if status == "fail" and _same_scalar(check.get("extracted_value"), check.get("expected_value")):
            check["status"] = "pass"
            check["reason"] = "Values match after normalization."

        if field == "currency":
            extracted_currency = str(product.get("currency", check.get("extracted_value", ""))).upper().strip()
            if extracted_currency == expected_currency:
                check["status"] = "pass"
                check["expected_value"] = expected_currency
                check["reason"] = "currency matches extractor platform currency map."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("currency", check.get("extracted_value"))
                check["expected_value"] = expected_currency
                check["reason"] = "currency does not match extractor platform currency map."

        if field == "type":
            extracted_type = str(product.get("type", check.get("extracted_value", ""))).lower().strip()
            if extracted_type == expected_type:
                check["status"] = "pass"
                check["expected_value"] = expected_type
                check["reason"] = "type matches extractor beer/cider/other keyword contract."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("type", check.get("extracted_value"))
                check["expected_value"] = expected_type
                check["reason"] = "type does not match extractor beer/cider/other keyword contract."

        if (
            status == "fail"
            and field == "pack_format"
            and _normalized_scalar(product.get("pack_format", check.get("extracted_value"))) == "na"
            and _is_unverifiable_pack_expected(check.get("expected_value"))
        ):
            check["status"] = "pass"
            check["expected_value"] = "NA"
            check["reason"] = "pack_format is not verifiable from source and extracted value is NA."

        if field == "pack_format":
            extracted_pack_format = _normalized_scalar(product.get("pack_format", check.get("extracted_value")))
            expected_pack_normalized = _normalized_scalar(expected_pack_format)
            citydrinks_image_evidence = (
                str(product.get("platform", "")).lower() == "citydrinks"
                and extracted_pack_format in {"can", "glass"}
                and expected_pack_normalized == "na"
                and isinstance(raw_source, dict)
                and bool(raw_source.get("images") or product.get("image_link"))
            )

            if extracted_pack_format == expected_pack_normalized:
                check["status"] = "pass"
                check["expected_value"] = expected_pack_format
                check["reason"] = "pack_format matches extractor text/image fallback."
            elif citydrinks_image_evidence:
                check["status"] = "pass"
                check["expected_value"] = product.get("pack_format", check.get("extracted_value"))
                check["reason"] = "CityDrinks source has image evidence and no text contradicting extracted pack_format."
            elif expected_pack_format == "NA" and _is_unverifiable_pack_expected(check.get("expected_value")):
                check["status"] = "pass"
                check["expected_value"] = "NA"
                check["reason"] = "pack_format cannot be verified from text or image fallback."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("pack_format", check.get("extracted_value"))
                check["expected_value"] = expected_pack_format
                check["reason"] = "pack_format does not match extractor text/image fallback."

        if status == "fail" and field == "brand":
            if _same_brand(check.get("extracted_value"), check.get("expected_value")):
                check["status"] = "pass"
                check["reason"] = "Brand values match after extractor brand-alias normalization."
            elif _brand_supported_by_source(product, raw_source):
                check["status"] = "pass"
                check["expected_value"] = product.get("brand")
                check["reason"] = "Extracted canonical brand is supported by product title/link/source text through extractor brand aliases."

        if field == "sub_type":
            extracted_sub_type = _normalize_sub_type(product.get("sub_type", check.get("extracted_value")))
            expected_normalized = _normalize_sub_type(expected_sub_type)

            if extracted_sub_type == expected_normalized:
                check["status"] = "pass"
                check["expected_value"] = expected_sub_type
                check["reason"] = "sub_type matches sub_type_rules.csv and extractor URL/title resolution."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("sub_type", check.get("extracted_value"))
                check["expected_value"] = expected_sub_type
                check["reason"] = "sub_type does not match sub_type_rules.csv and extractor URL/title resolution."

        if field == "availability":
            extracted_availability = str(product.get("availability", check.get("extracted_value", ""))).strip().lower()

            if extracted_availability == expected_availability:
                check["status"] = "pass"
                check["expected_value"] = expected_availability
                check["reason"] = "availability matches extractor contract and source stock/add-to-cart evidence."
            else:
                check["status"] = "fail"
                check["extracted_value"] = product.get("availability", check.get("extracted_value"))
                check["expected_value"] = expected_availability
                check["reason"] = "availability does not match extractor contract and source stock/add-to-cart evidence."

        if status == "fail" and field in {"original_price_local", "discounted_price_local"}:
            official_price = _source_price(raw_source, field, profile)
            if _same_number(product.get(field), official_price):
                check["status"] = "pass"
                check["expected_value"] = str(official_price)
                check["reason"] = "Extracted price matches the site profile's website-visible price field."
            elif _matches_royalspirit_variant_price(product, raw_source, field):
                check["status"] = "pass"
                check["expected_value"] = product.get(field)
                check["reason"] = "Extracted price matches one Royal Spirit hasVariant offer price."
            elif _matches_africaneastern_price(product, raw_source, field):
                check["status"] = "pass"
                check["expected_value"] = product.get(field)
                check["reason"] = "Extracted price matches African Eastern price_range or price_tax_tiers."
            elif _matches_citydrinks_price(product, raw_source, field):
                check["status"] = "pass"
                check["expected_value"] = product.get(field)
                check["reason"] = "Extracted price matches CityDrinks base price or multibuy tier total for this record's units."
            elif _matches_gmp_price(product, raw_source, field):
                check["status"] = "pass"
                check["expected_value"] = product.get(field)
                check["reason"] = "Extracted price matches GMP WooCommerce variation price for this record's units."
            elif _matches_centaurus_price(product, raw_source, field):
                check["status"] = "pass"
                check["expected_value"] = product.get(field)
                check["reason"] = "Extracted price appears in the Centaurus multi-card product source."

    failed_checks = [
        check
        for check in result.get("field_checks", [])
        if str(check.get("status", "")).lower() == "fail"
    ]

    result["status"] = "fail" if failed_checks else "pass"

    if not failed_checks and str(result.get("summary", "")).lower().startswith("all checkable fields match"):
        return result

    if not failed_checks:
        result["summary"] = "All checkable fields match the raw source JSON."

    return result


def qc_product(product: dict, s3: S3Client) -> dict:
    source_uri = product.get("product_source_s3_uri") or product.get("product_html_s3_uri")
    raw_source = product.get("_source_payload")

    if not raw_source and not source_uri:
        return {
            "product_identifier": _product_key(product),
            "status": "fail",
            "field_checks": [],
            "summary": "Missing product_source_s3_uri/product_html_s3_uri; cannot QC against raw source.",
            **_result_metadata(product),
        }

    if not raw_source:
        if source_uri.endswith(".html"):
            raw_source = _read_text(source_uri, s3)
        else:
            raw_source = _read_json(source_uri, s3)

    profile = _qc_profile(product)
    source_type = "product-detail HTML" if isinstance(raw_source, str) else profile.get("source_type", "raw source")
    payload = {
        "fields": ", ".join(QC_FIELDS),
        "platform": product.get("platform", "unknown"),
        "source_type": source_type,
        "sub_type_rules": _sub_type_rules_text(product, raw_source),
        "profile_rules": _profile_rules_text(profile),
        "extracted_product": json.dumps(product, ensure_ascii=False, indent=2),
        "raw_source": raw_source if isinstance(raw_source, str) else json.dumps(raw_source, ensure_ascii=False, indent=2),
        "format_instructions": parser.get_format_instructions(),
    }

    result = None
    last_error = None

    for attempt in range(1, QC_MODEL_ATTEMPTS + 1):
        try:
            result = chain.invoke(payload)
            if isinstance(result, dict):
                break
            last_error = f"QC model returned {type(result).__name__}"
        except Exception as e:
            last_error = str(e)

    if not isinstance(result, dict):
        raise ValueError(f"QC model did not return a valid result after {QC_MODEL_ATTEMPTS} attempts: {last_error}")

    return _normalize_qc_result(product, result, raw_source, profile)


def _field_stats(results: list[dict]) -> dict:
    total = 0
    passed = 0
    failed = 0

    for result in results:
        for check in result.get("field_checks", []):
            status = str(check.get("status", "")).lower()
            if status == "not_applicable":
                continue
            total += 1
            if status == "pass":
                passed += 1
            else:
                failed += 1

    accuracy = round(passed / total * 100, 2) if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "accuracy_percentage": accuracy,
    }


def build_report(products: list[dict], results: list[dict], source_path: str) -> dict:
    total_products = len(products)
    checked_products = len(results)
    passed_products = sum(1 for item in results if str(item.get("status", "")).lower() == "pass")
    failed_products = checked_products - passed_products
    product_accuracy = round(passed_products / checked_products * 100, 2) if checked_products else 0.0

    return {
        "source": source_path,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "total_products": total_products,
        "checked_products": checked_products,
        "passed_products": passed_products,
        "failed_products": failed_products,
        "product_accuracy_percentage": product_accuracy,
        "field_accuracy": _field_stats(results),
        "results": results,
    }


def print_report(report: dict, max_failures: int = 20) -> None:
    field_accuracy = report["field_accuracy"]

    print("\nQC REPORT")
    print("=========")
    print(f"Source: {report['source']}")
    print(f"Generated at: {report['generated_at']}")
    print(f"Products checked: {report['checked_products']}/{report['total_products']}")
    print(f"Products correct: {report['passed_products']}")
    print(f"Products wrong: {report['failed_products']}")
    print(f"Product accuracy: {report['product_accuracy_percentage']}%")
    print(
        "Field accuracy: "
        f"{field_accuracy['accuracy_percentage']}% "
        f"({field_accuracy['passed']}/{field_accuracy['total']} fields passed)"
    )

    failures = [
        result
        for result in report["results"]
        if str(result.get("status", "")).lower() != "pass"
    ]

    if not failures:
        print("\nNo failed products found.")
        return

    print(f"\nFailed Products (showing {min(len(failures), max_failures)} of {len(failures)})")
    print("---------------")

    for idx, result in enumerate(failures[:max_failures], start=1):
        print(f"\n{idx}. {result.get('product_identifier', 'unknown')}")

        failed_checks = [
            check
            for check in result.get("field_checks", [])
            if str(check.get("status", "")).lower() == "fail"
        ]

        for check in failed_checks:
            print(
                "   - "
                f"{check.get('field')}: "
                f"extracted={check.get('extracted_value')} | "
                f"expected={check.get('expected_value')}"
            )


def run_qc(
    extracted_path: str,
    limit: int = 0,
    concurrency: int = 5,
    upload_report: bool = False,
    report_key: str = "",
) -> dict:
    s3 = S3Client()
    products = _read_json(extracted_path, s3)

    if not isinstance(products, list):
        raise ValueError("Extracted product JSON must be a list of product records.")

    products_to_check = products[:limit] if limit else products
    results = []
    total = len(products_to_check)
    completed = 0
    passed = 0
    failed = 0

    print(f"[QC] Starting QC for {total} products with concurrency={concurrency}", flush=True)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_product = {
            executor.submit(qc_product, product, s3): product
            for product in products_to_check
        }

        for future in as_completed(future_to_product):
            product = future_to_product[future]
            try:
                result = future.result()
            except Exception as e:
                result = {
                    "product_identifier": _product_key(product),
                    "status": "fail",
                    "field_checks": [{
                        "field": "qc_agent_error",
                        "status": "fail",
                        "extracted_value": "error",
                        "expected_value": str(e),
                        "reason": str(e),
                    }],
                    "summary": f"QC agent failed: {e}",
                    **_result_metadata(product),
                }

            results.append(result)
            completed += 1

            if str(result.get("status", "")).lower() == "pass":
                passed += 1
            else:
                failed += 1

            print(_progress_line(completed, total, passed, failed), flush=True)

    report = build_report(products_to_check, results, extracted_path)

    if upload_report:
        if not extracted_path.startswith("s3://"):
            raise ValueError("--upload-report requires an S3 extracted path.")

        bucket_and_key = extracted_path.removeprefix("s3://")
        bucket, key = bucket_and_key.split("/", 1)
        final_report_key = report_key or key.replace(".json", "-qc-report.json")
        s3.put_json(bucket, final_report_key, report)
        report["report_s3_uri"] = f"s3://{bucket}/{final_report_key}"

    return report


def main() -> int:
    arg_parser = argparse.ArgumentParser(
        description="Run AI QC against extracted product JSON and raw source JSON."
    )
    arg_parser.add_argument(
        "extracted_path",
        help="Local path or s3:// URI for extracted product JSON.",
    )
    arg_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only QC the first N products. Default: all.",
    )
    arg_parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum concurrent QC LLM calls. Default: 5.",
    )
    arg_parser.add_argument(
        "--upload-report",
        action="store_true",
        help="Upload the QC report next to the extracted S3 JSON.",
    )
    arg_parser.add_argument(
        "--report-key",
        default="",
        help="Optional S3 key to use with --upload-report.",
    )
    arg_parser.add_argument(
        "--max-failures",
        type=int,
        default=20,
        help="Maximum failed products to print. Default: 20.",
    )
    args = arg_parser.parse_args()

    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")
    if args.concurrency > 10:
        raise SystemExit("--concurrency above 10 can hit rate limits; use 1-10.")

    report = run_qc(
        args.extracted_path,
        limit=args.limit,
        concurrency=args.concurrency,
        upload_report=args.upload_report,
        report_key=args.report_key,
    )
    print_report(report, max_failures=args.max_failures)

    if report.get("report_s3_uri"):
        print(f"\nUploaded report: {report['report_s3_uri']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
