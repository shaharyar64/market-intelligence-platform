"""
Run LLM extraction from stored raw product manifests.

Each manifest entry should include:
- link
- platform
- date
- product_html_s3_uri OR product_source_s3_uri
- optional region, position, features_in_top10, features_on_first_page, context
"""

import argparse
import html as html_lib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

from botocore.exceptions import ClientError

import settings
from data_extractor import (
    KNOWN_BRANDS,
    _detect_pack_format_from_image,
    _normalize_brand,
    _pack_format_from_text,
    _quantity_from_text,
    _resolve_sub_type,
    _resolve_type,
    parse_html_code,
)
from logger import get_logger
from s3 import S3Client

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
AED_TO_USD = 0.272
RETRY_ATTEMPTS = 3

FIRST_PAGE_LIMITS = {
    "africaneastern": 90,
    "africaneastern_auh": 90,
    "africaneastern_dubai": 90,
    "africaneastern_rak": 90,
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
    "mmihomedelivery_dubai": 25,
    "mmihomedelivery_rak": 25,
    "nhsc": 16,
    "premiumcellars": 39,
    "royalspirit": 36,
    "spinneysauh": 12,
    "supercellar": 50,
    "thebottlestore": 15,
    "unisatgt": 45,
    "windmillgt": 30,
}

MANIFESTS = {
    "africanandeastern": "beer-pricing/africanandeastern/product-html/{date}/manifest.json",
    "africaneastern": "beer-pricing/africaneastern/product-html/{date}/manifest.json",
    "africaneastern_auh": "beer-pricing/africaneastern-abu-dabhi/product-source-json/{date}/manifest.json",
    "africaneastern_dubai": "beer-pricing/africaneastern-dubai/product-source-json/{date}/manifest.json",
    "africaneastern_rak": "beer-pricing/africaneastern-rak/product-source-json/{date}/manifest.json",
    "bdutyfree": "beer-pricing/bdutyfree/product-html/{date}/manifest.json",
    "bmmishops": "beer-pricing/bmmishops/product-source-json/{date}/manifest.json",
    "centaurusint": "beer-pricing/centaurusint/product-html/{date}/manifest.json",
    "citydrinks": "beer-pricing/citydrinks/product-source-json/{date}/manifest.json",
    "dubaidutyfree": "beer-pricing/dubaidutyfree/product-source-json/{date}/manifest.json",
    "gbiexpress": "beer-pricing/gbiexpress/product-html/{date}/manifest.json",
    "gmp": "beer-pricing/gmp/product-html/{date}/manifest.json",
    "highspiritsuae": "beer-pricing/highspiritsuae/product-html/{date}/manifest.json",
    "jmkcellars": "beer-pricing/jmkcellars/product-html/{date}/manifest.json",
    "mmihomedelivery_dubai": "beer-pricing/mmihomedelivery-dubai/product-html/{date}/manifest.json",
    "mmihomedelivery_rak": "beer-pricing/mmihomedelivery-rak/product-source-json/{date}/manifest.json",
    "nhsc": "beer-pricing/nhsc/product-html/{date}/manifest.json",
    "premiumcellars": "beer-pricing/premiumcellars/product-source-json/{date}/manifest.json",
    "royalspirit": "beer-pricing/royalspirit/product-source-json/{date}/manifest.json",
    "spinneysauh": "beer-pricing/spinneysauh/product-source-json/{date}/manifest.json",
    "supercellar": "beer-pricing/supercellar/product-html/{date}/manifest.json",
    "thebottlestore": "beer-pricing/thebottlestore/product-html/{date}/manifest.json",
    "unisatgt": "beer-pricing/unisatgt/product-html/{date}/manifest.json",
    "windmillgt": "beer-pricing/windmillgt/product-source-json/{date}/manifest.json",
}

OUTPUT_KEYS = {
    "africanandeastern": "beer-pricing/africanandeastern/{date}.json",
    "africaneastern": "beer-pricing/africaneastern/{date}.json",
    "africaneastern_auh": "beer-pricing/africaneastern-abu-dabhi/{date}.json",
    "africaneastern_dubai": "beer-pricing/africaneastern-dubai/{date}.json",
    "africaneastern_rak": "beer-pricing/africaneastern-rak/{date}.json",
    "bdutyfree": "beer-pricing/bdutyfree/{date}.json",
    "bmmishops": "beer-pricing/bmmishops/{date}.json",
    "centaurusint": "beer-pricing/centaurusint/{date}.json",
    "citydrinks": "beer-pricing/citydrinks/{date}.json",
    "dubaidutyfree": "beer-pricing/dubaidutyfree/{date}.json",
    "gbiexpress": "beer-pricing/gbiexpress/{date}.json",
    "gmp": "beer-pricing/gmp/{date}.json",
    "highspiritsuae": "beer-pricing/highspiritsuae/{date}.json",
    "jmkcellars": "beer-pricing/jmkcellars/{date}.json",
    "mmihomedelivery_dubai": "beer-pricing/mmihomedelivery-dubai/{date}.json",
    "mmihomedelivery_rak": "beer-pricing/mmihomedelivery-rak/{date}.json",
    "nhsc": "beer-pricing/nhsc/{date}.json",
    "premiumcellars": "beer-pricing/premiumcellars/{date}.json",
    "royalspirit": "beer-pricing/royalspirit/{date}.json",
    "spinneysauh": "beer-pricing/spinneysauh/{date}.json",
    "supercellar": "beer-pricing/supercellar/{date}.json",
    "thebottlestore": "beer-pricing/thebottlestore/{date}.json",
    "unisatgt": "beer-pricing/unisatgt/{date}.json",
    "windmillgt": "beer-pricing/windmillgt/{date}.json",
}


def s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def read_text(s3: S3Client, uri: str) -> str:
    if uri.startswith("s3://"):
        parsed = urlparse(uri)
        response = s3.s3.get_object(
            Bucket=parsed.netloc,
            Key=parsed.path.lstrip("/"),
        )
        return response["Body"].read().decode("utf-8")

    return Path(uri).read_text(encoding="utf-8")


def read_json(s3: S3Client, uri: str):
    if uri.startswith("s3://"):
        return s3.read_json(uri)

    with Path(uri).open("r", encoding="utf-8") as f:
        return json.load(f)


def is_missing_s3_key_error(error: Exception) -> bool:
    if not isinstance(error, ClientError):
        return False

    code = error.response.get("Error", {}).get("Code")
    return code in {"NoSuchKey", "404", "NotFound"}


def infer_output_key(site: str, date: str, manifest_uri: str) -> tuple[str, str]:
    if not date:
        match = re.search(r"/(\d{4}-\d{2}-\d{2})/manifest\.json$", manifest_uri)
        if match:
            date = match.group(1)

    if not date:
        raise ValueError(f"Could not infer output date from manifest: {manifest_uri}")

    if site in OUTPUT_KEYS:
        return S3_BUCKET, OUTPUT_KEYS[site].format(date=date)

    if not manifest_uri.startswith("s3://"):
        raise ValueError("--output-uri is required when manifest is local and site has no configured output.")

    parsed = urlparse(manifest_uri)
    manifest_key = parsed.path.lstrip("/")
    output_key = manifest_key.replace("/product-html/", "/").replace("/manifest.json", ".json")
    return parsed.netloc, output_key


def apply_entry_overrides(item: dict, entry: dict) -> dict:
    item["link"] = entry["link"]
    item["platform"] = entry.get("platform", item.get("platform", "NA"))
    item["date"] = entry.get("date", item.get("date", "NA"))
    item["region"] = entry.get("region", item.get("region", "NA"))
    item["features_in_top10"] = entry.get("features_in_top10", item.get("features_in_top10", "no"))
    item["features_on_first_page"] = entry.get("features_on_first_page", item.get("features_on_first_page", "no"))

    if entry.get("availability"):
        item["availability"] = entry["availability"]

    if entry.get("currency"):
        item["currency"] = entry["currency"]

    if entry.get("image_link"):
        item["image_link"] = entry["image_link"]

    if entry.get("product_html_s3_uri"):
        item["product_html_s3_key"] = entry.get("product_html_s3_key", "")
        item["product_html_s3_uri"] = entry["product_html_s3_uri"]

    if entry.get("product_source_s3_uri"):
        item["product_source_s3_key"] = entry.get("product_source_s3_key", "")
        item["product_source_s3_uri"] = entry["product_source_s3_uri"]

    type_hint = entry.get("context", {}).get("type_hint")
    if type_hint and item.get("type") in ("NA", "other", "", None):
        item["type"] = type_hint

    return item


def first_page_limit_for(site: str, item: dict | None = None) -> int:
    platform = (item or {}).get("platform", "")
    return FIRST_PAGE_LIMITS.get(site, FIRST_PAGE_LIMITS.get(platform, 0))


def feature_group_key(item: dict) -> str:
    return (
        str(item.get("link") or "")
        or str(item.get("product_source_s3_uri") or "")
        or str(item.get("product_html_s3_uri") or "")
    )


def numeric_units(item: dict) -> int | None:
    try:
        return int(float(str(item.get("units", "")).strip()))
    except (TypeError, ValueError):
        return None


def primary_variant_index(group: list[int], products: list[dict], site: str = "") -> int:
    if site == "centaurusint" or any(products[idx].get("platform") == "centaurusint" for idx in group):
        return group[0]

    unit_values = [(idx, numeric_units(products[idx])) for idx in group]
    for idx, units in unit_values:
        if units == 1:
            return idx

    numeric = [(idx, units) for idx, units in unit_values if units is not None]
    if numeric:
        return min(numeric, key=lambda pair: pair[1])[0]

    return group[0]


def _first_value(value, default=""):
    if isinstance(value, dict):
        for key in ("value", "url", "src"):
            if value.get(key) not in (None, ""):
                return value[key]
        return default
    if isinstance(value, list):
        return _first_value(value[0], default) if value else default
    return default if value in (None, "") else value


def _clean_float(value) -> float | None:
    value = _first_value(value, None)
    if value in (None, ""):
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    if not cleaned:
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _spinneys_product(payload: dict) -> dict:
    return payload.get("product", payload) if isinstance(payload.get("product"), dict) else payload


def _spinneys_attr(payload: dict, key: str, default=""):
    return _first_value(_spinneys_product(payload).get(key), default)


def _spinneys_units(payload: dict, name: str, link: str) -> int:
    pack_size = _spinneys_attr(payload, "webSize") or _spinneys_attr(payload, "erpSize") or _first_value(payload.get("packSize"), "")
    text = " ".join(str(value).lower() for value in [pack_size, name, link] if value)

    patterns = [
        r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
        r"\b(\d+)\s*[-\s]*pack\b",
        r"\bcase\s+of\s+(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return 1


def _spinneys_availability(payload: dict) -> str:
    has_stock = payload.get("hasStock")
    if isinstance(has_stock, dict) and "A10_SPNHD" in has_stock:
        return "yes" if _clean_float(has_stock.get("A10_SPNHD")) and _clean_float(has_stock.get("A10_SPNHD")) > 0 else "no"

    stock = _first_value(payload.get("calculatedStock", payload.get("stock")), None)
    if isinstance(stock, bool):
        return "yes" if stock else "no"
    if isinstance(stock, (int, float)):
        return "yes" if stock > 0 else "no"
    if isinstance(stock, str):
        cleaned = stock.strip().lower()
        if cleaned in {"yes", "true", "in_stock", "in stock", "available"}:
            return "yes"
        if cleaned in {"no", "false", "out_of_stock", "out of stock", "sold out", "unavailable"}:
            return "no"
        try:
            return "yes" if float(cleaned) > 0 else "no"
        except ValueError:
            pass
    return "yes"


def _spinneys_price(payload: dict, kind: str) -> float | None:
    price = payload.get("price", {}) if isinstance(payload.get("price"), dict) else {}
    if kind == "original":
        return _clean_float(price.get("officialListPriceText") or price.get("officialListPrice") or price.get("listPriceText") or price.get("listPrice"))
    return _clean_float(price.get("officialSalePriceText") or price.get("officialSalePrice") or price.get("salePriceText") or price.get("salePrice"))


def _spinneys_image(payload: dict) -> str:
    image = _first_value(payload.get("image"), "")
    if image:
        return image

    image_name = _first_value(_spinneys_attr(payload, "images"), "")
    if image_name:
        return f"https://api.mircate.com/5p1hp1d2t/CALL/PIMAPI/getImage/jux9er4tf08?filename={image_name}&quality=100"

    return "NA"


def _spinneys_pack_format(payload: dict, name: str, pack_size: str, link: str, image_link: str) -> str:
    pack_format = _pack_format_from_text(name, pack_size, link)
    if pack_format != "NA":
        return pack_format

    product_text = " ".join(str(value).lower() for value in [
        name,
        pack_size,
        link,
        json.dumps(_spinneys_product(payload), ensure_ascii=False),
    ] if value)

    if "cider" in product_text and any(brand in product_text for brand in ("hunter", "hunters", "savanna", "strongbow")):
        return "Glass"

    if image_link and image_link != "NA":
        image_pack_format = _detect_pack_format_from_image(image_link, link or name)
        if image_pack_format != "NA":
            return image_pack_format

    return "NA"


def spinneys_fallback_item(payload: dict, entry: dict) -> dict:
    name = str(_spinneys_attr(payload, "title") or _spinneys_attr(payload, "erpName") or _first_value(payload.get("name"), "")).strip()
    link = entry["link"]
    brand = _normalize_brand(_spinneys_attr(payload, "webBrand") or _spinneys_attr(payload, "erpBrandName") or _first_value(payload.get("brand"), "") or name)
    pack_size = _spinneys_attr(payload, "webSize") or _spinneys_attr(payload, "erpSize") or _first_value(payload.get("packSize"), "")
    quantity = _quantity_from_text(name, _spinneys_attr(payload, "erpVolume"), pack_size, link)
    image_link = _spinneys_image(payload)
    pack_format = _spinneys_pack_format(payload, name, pack_size, link, image_link)
    original = _spinneys_price(payload, "original")
    discounted = _spinneys_price(payload, "discounted")

    if discounted is None:
        discounted = original

    item = {
        "platform": "spinneysauh",
        "product_name": name or "NA",
        "brand": brand,
        "type": _resolve_type({"product_name": name, "brand": brand, "link": link}, json.dumps(payload), link),
        "sub_type": "regular",
        "quantity": quantity,
        "units": _spinneys_units(payload, name, link),
        "pack_format": pack_format,
        "currency": "AED",
        "original_price_local": original,
        "discounted_price_local": discounted,
        "original_price_usd": round(original * AED_TO_USD, 2) if original is not None else None,
        "discounted_price_usd": round(discounted * AED_TO_USD, 2) if discounted is not None else None,
        "discount_percentage": round((original - discounted) / original * 100, 2) if original and discounted and discounted < original else 0.0,
        "link": link,
        "image_link": image_link,
        "availability": _spinneys_availability(payload),
        "features_in_top10": "no",
        "features_on_first_page": "no",
    }
    item["sub_type"] = _resolve_sub_type(item, html_content=json.dumps(payload), source_url=link)
    return item


_PREMIUMCELLARS_SPELLED_NUMBERS = {
    "one": 1, "single": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "twenty four": 24, "twenty-four": 24,
}


def _premiumcellars_units(variant_title: str) -> int | None:
    match = re.search(r"(\d+)", variant_title)
    if match:
        return int(match.group(1))

    lowered = variant_title.lower()
    if lowered in ("", "default title"):
        return 1
    for word, value in _PREMIUMCELLARS_SPELLED_NUMBERS.items():
        if re.search(rf"\b{word}\b", lowered):
            return value
    if "case" in lowered:
        # A bare "Case" with no count stated is this retailer's standard
        # 24-unit case (confirmed by client review of the 2026-09-18 export).
        return 24
    return None


def _premiumcellars_brand_from_title(title: str) -> str:
    """Shopify titles have no dedicated brand field — match against
    KNOWN_BRANDS (longest match wins, so multi-word brands like "stella
    artois" beat a shorter false-positive substring) and fall back to the
    title's first word rather than the whole (noisy) title string."""
    lowered = title.lower()
    matches = [b for b in KNOWN_BRANDS if re.search(rf"\b{re.escape(b)}\b", lowered)]
    if matches:
        return max(matches, key=len)
    first_word = title.strip().split()[0] if title.strip() else title
    return first_word


def premiumcellars_base_item(payload: dict, entry: dict) -> dict | None:
    """Builds a single placeholder item from the product-level fields (title,
    brand, type, pack_format, image) — pricing comes from the first variant.
    expand_premiumcellars_variants() (run later, post apply_entry_overrides)
    turns this into one row per variant with correct per-variant pricing and
    a unique link, the same two-step pattern used for royalspirit."""
    title = str(payload.get("title", "")).strip()
    if not title:
        return None

    brand = _normalize_brand(_premiumcellars_brand_from_title(title))
    product_type = str(payload.get("product_type", "")).strip().lower()
    type_ = "cider" if "cider" in product_type else "beer"
    link = entry["link"]

    variants = payload.get("variants") or []
    first_variant = variants[0] if variants and isinstance(variants[0], dict) else {}
    try:
        discounted = float(first_variant["price"]) if first_variant.get("price") not in (None, "") else None
    except (TypeError, ValueError):
        discounted = None

    image_link = (payload.get("images") or [{}])[0].get("src", "")
    pack_format = _pack_format_from_text(title)
    if pack_format == "NA" and image_link:
        pack_format = _detect_pack_format_from_image(image_link, title)

    item = {
        "platform": "premiumcellars",
        "product_name": title,
        "brand": brand,
        "type": type_,
        "sub_type": "regular",
        "quantity": _quantity_from_text(title),
        "units": _premiumcellars_units(str(first_variant.get("title", ""))),
        "pack_format": pack_format,
        "currency": "AED",
        "original_price_local": discounted,
        "discounted_price_local": discounted,
        "original_price_usd": round(discounted * AED_TO_USD, 2) if discounted is not None else None,
        "discounted_price_usd": round(discounted * AED_TO_USD, 2) if discounted is not None else None,
        "discount_percentage": 0.0,
        "link": link,
        "image_link": image_link,
        "availability": "yes" if first_variant.get("available") else "no",
        "features_in_top10": entry.get("features_in_top10", "no"),
        "features_on_first_page": entry.get("features_on_first_page", "no"),
    }
    item["sub_type"] = _resolve_sub_type(item, html_content=json.dumps(payload), source_url=link)
    return item


def expand_premiumcellars_variants(items: list[dict], entry: dict, source_payload) -> list[dict]:
    if entry.get("platform") != "premiumcellars" or not isinstance(source_payload, dict):
        return items

    variants = source_payload.get("variants")
    if not isinstance(variants, list) or not variants:
        return items

    title = str(source_payload.get("title", "")).strip()
    base_item = items[0] if items else {}
    expanded = []

    for variant in variants:
        if not isinstance(variant, dict):
            continue

        variant_title = str(variant.get("title", "")).strip()
        name = title if variant_title.lower() in ("", "default title") else f"{title} {variant_title}"

        try:
            discounted = float(variant["price"]) if variant.get("price") not in (None, "") else None
        except (TypeError, ValueError):
            discounted = None
        try:
            original = float(variant["compare_at_price"]) if variant.get("compare_at_price") not in (None, "") else None
        except (TypeError, ValueError):
            original = None
        if original is None:
            original = discounted

        item = dict(base_item)
        item["product_name"] = name or "NA"
        item["quantity"] = _quantity_from_text(title, variant_title)
        item["units"] = _premiumcellars_units(variant_title)
        item["original_price_local"] = original
        item["discounted_price_local"] = discounted
        item["original_price_usd"] = round(original * AED_TO_USD, 2) if original is not None else None
        item["discounted_price_usd"] = round(discounted * AED_TO_USD, 2) if discounted is not None else None
        item["discount_percentage"] = (
            round((original - discounted) / original * 100, 2)
            if original and discounted and discounted < original
            else 0.0
        )
        item["availability"] = "yes" if variant.get("available") else "no"
        item["link"] = f"{entry['link']}?variant={variant.get('id', '')}"
        expanded.append(item)

    return expanded or items


def _variant_text(variant: dict) -> str:
    return " ".join(str(variant.get(key, "")) for key in ("name", "sku", "description", "url") if variant.get(key))


def _variant_units(variant: dict) -> int | None:
    text = _variant_text(variant).lower()
    patterns = [
        r"\bpack\s+of\s+(\d+)\b",
        r"\b(\d+)\s*[-\s]*pack\b",
        r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return None


def _variant_price(variant: dict) -> float | None:
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
        if candidate in (None, ""):
            continue
        cleaned = re.sub(r"[^\d.]", "", str(candidate))
        if not cleaned:
            continue
        try:
            return round(float(cleaned), 2)
        except ValueError:
            continue

    return None


def _variant_suffix(variant: dict, fallback: int) -> str:
    for key in ("sku", "productID", "@id", "url", "name"):
        value = str(variant.get(key, "")).strip()
        if value:
            suffix = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
            if suffix:
                return suffix
    return f"variant-{fallback}"


def _variant_image(variant: dict) -> str:
    image = variant.get("image")
    if isinstance(image, list):
        return image[0] if image else ""
    return image or ""


def expand_royalspirit_variants(items: list[dict], entry: dict, source_payload) -> list[dict]:
    if entry.get("platform") != "royalspirit" or not isinstance(source_payload, dict):
        return items

    variants = source_payload.get("hasVariant")
    if not isinstance(variants, list) or not variants:
        return items

    base_items = items or []
    base_item = base_items[0] if base_items else {}
    expanded = []

    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            continue

        units = _variant_units(variant)
        price = _variant_price(variant)

        if units is None and price is None:
            continue

        item = dict(base_item)
        variant_name = str(variant.get("name", "")).strip()

        if variant_name and variant_name.lower() not in item.get("product_name", "").lower():
            item["product_name"] = f"{item.get('product_name', '').strip()} {variant_name}".strip()

        if units is not None:
            item["units"] = units

        if price is not None:
            item["original_price_local"] = price
            item["discounted_price_local"] = price
            item["original_price_usd"] = round(price * AED_TO_USD, 2)
            item["discounted_price_usd"] = round(price * AED_TO_USD, 2)
            item["discount_percentage"] = 0.0

        image = _variant_image(variant)
        if image:
            item["image_link"] = image

        suffix = _variant_suffix(variant, index)
        separator = "&" if "?" in entry["link"] else "?"
        item["link"] = f"{entry['link']}{separator}variant={suffix}"
        expanded.append(item)

    return expanded or items


def _africaneastern_base_price(source_payload) -> float | None:
    if not isinstance(source_payload, dict):
        return None

    minimum_price = source_payload.get("price_range", {}).get("minimum_price", {})
    for key in ("final_price", "regular_price"):
        price = minimum_price.get(key, {})
        if isinstance(price, dict):
            value = price.get("value")
        else:
            value = price

        if value in (None, ""):
            continue

        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue

    return None


def filter_items_for_scope(items: list[dict], entry: dict) -> list[dict]:
    filtered = []
    for item in items:
        if _is_out_of_scope_extracted_item(item):
            log.warning(
                f"[SKIP] Filtered out-of-scope extracted product: "
                f"{item.get('link') or entry.get('link')}"
            )
            continue
        filtered.append(item)
    return filtered


def postprocess_items(items: list[dict], entry: dict, source_payload=None) -> list[dict]:
    items = expand_royalspirit_variants(items, entry, source_payload)
    items = expand_premiumcellars_variants(items, entry, source_payload)

    if entry.get("postprocess") == "price_override":
        for item in items:
            original = entry.get("original_price_local")
            discounted = entry.get("discounted_price_local")
            multiplier = entry.get("currency_multiplier")

            item["original_price_local"] = original
            item["discounted_price_local"] = discounted

            if multiplier and original is not None:
                item["original_price_usd"] = round(original * multiplier, 2)
            if multiplier and discounted is not None:
                item["discounted_price_usd"] = round(discounted * multiplier, 2)

            if original and discounted and original > 0 and discounted < original:
                item["discount_percentage"] = round((original - discounted) / original * 100, 2)
            else:
                item["discount_percentage"] = 0.0

        return filter_items_for_scope(items, entry)

    if entry.get("postprocess") not in ("citydrinks_multibuy", "africaneastern_tiers"):
        return filter_items_for_scope(items, entry)

    levels = entry.get("multibuyPriceLevels") or entry.get("price_tax_tiers") or []
    multiplier = entry.get("currency_multiplier", AED_TO_USD)
    expanded = []

    for item in items:
        if not levels:
            expanded.append(item)
            continue

        base_item = dict(item)
        base_item["units"] = 1
        base_price = None

        if entry.get("postprocess") == "africaneastern_tiers":
            base_price = _africaneastern_base_price(source_payload)
            if base_price is not None:
                base_item["original_price_local"] = base_price
                base_item["discounted_price_local"] = base_price
                base_item["original_price_usd"] = round(base_price * multiplier, 2)
                base_item["discounted_price_usd"] = round(base_price * multiplier, 2)
                base_item["discount_percentage"] = 0.0

        expanded.append(base_item)

        for level in levels:
            qty = level.get("quantity")
            unit_price = level.get("unitPrice")

            if unit_price is None:
                unit_price = level.get("final_price", {}).get("value")

            if not qty or unit_price is None:
                continue

            if entry.get("postprocess") == "citydrinks_multibuy":
                total_price = round((unit_price / 100) * qty, 2)
            else:
                total_price = round(float(unit_price), 2)

            total_usd = round(total_price * multiplier, 2)
            percent_off = level.get("discount", {}).get("percent_off", 0.0)
            tier_item = dict(base_item)
            tier_item["units"] = qty
            tier_item["original_price_local"] = total_price
            tier_item["discounted_price_local"] = total_price
            tier_item["original_price_usd"] = total_usd
            tier_item["discounted_price_usd"] = total_usd
            tier_item["discount_percentage"] = round(percent_off, 2) if percent_off else 0.0

            # Tier percent_off is the saving vs buying singles, so the original
            # must be the singles-equivalent (base x qty) or the three columns
            # contradict each other (orig == disc but discount % > 0). Skipped
            # when the site reports no tier discount (rounding-only gaps).
            if base_price is not None and percent_off and base_price * qty > total_price:
                original = round(base_price * qty, 2)
                tier_item["original_price_local"] = original
                tier_item["original_price_usd"] = round(original * multiplier, 2)
                tier_item["discount_percentage"] = round((original - total_price) / original * 100, 2)
            expanded.append(tier_item)

    return filter_items_for_scope(expanded, entry)


def _slug_tokens_from_url(url: str) -> list[str]:
    slug = urlparse(url).path.strip("/").split("/")[0]
    slug = re.sub(r"\bp-\d+\.html$", "", slug)
    tokens = re.findall(r"[a-zA-Z]+", slug.lower())
    stop_words = {
        "beer",
        "beers",
        "btl",
        "bottle",
        "bottles",
        "can",
        "cans",
        "cl",
        "ml",
        "ltr",
        "liter",
        "litre",
        "case",
        "pack",
        "promo",
        "x",
    }
    return [token for token in tokens if token not in stop_words and len(token) > 1]


def _normalize_match_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower())


def _is_centaurus_related_item(item: dict, entry: dict) -> bool:
    return False


def _html_attr(tag: str, attr: str) -> str:
    match = re.search(
        rf"\b{re.escape(attr)}\s*=\s*([\"'])(.*?)\1",
        tag or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html_lib.unescape(match.group(2)).strip() if match else ""


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _absolute_url(value: str, base_url: str) -> str:
    if not value:
        return ""
    return urljoin(base_url, html_lib.unescape(value).strip())


def _brand_from_known_text(*values: str) -> str:
    text = _normalize_match_text(" ".join(value for value in values if value))
    matches = []
    for brand in KNOWN_BRANDS:
        normalized = _normalize_match_text(str(brand))
        if normalized and re.search(rf"\b{re.escape(normalized)}\b", text):
            matches.append(str(brand))

    if not matches:
        return "NA"

    return _normalize_brand(max(matches, key=len))


def _units_from_text(*values: str) -> int:
    text = " ".join(value for value in values if value)
    patterns = [
        r"\b(?:case|pack|x)\s*(?:of\s*)?(\d{1,3})\b",
        r"\b(\d{1,3})\s*(?:x|pack|pcs|pieces|bottles|btls|cans)\b",
        r"\b(\d{1,3})\s*[-\s]*pack\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            units = int(match.group(1))
            if 1 <= units <= 100:
                return units
    return 1


def _jmk_card_item_from_html(raw_content: str, entry: dict) -> dict | None:
    """
    JMK stores each product card as an HTML fragment. Some cards are sparse
    enough that the generic extractor returns no item, so parse the
    WooCommerce card fields directly.
    """
    if not raw_content:
        return None

    source_url = entry.get("link", "https://jmkcellars.com/product-category/beer/")
    detail_href = _first_match(r"<a[^>]+href=[\"']([^\"']+)[\"']", raw_content)
    detail_url = _absolute_url(detail_href, source_url) or source_url

    title_html = _first_match(
        r"<h[23][^>]+class=[\"'][^\"']*(?:woocommerce-loop-product__title|product-title)[^\"']*[\"'][^>]*>(.*?)</h[23]>",
        raw_content,
    )
    if not title_html:
        title_html = _first_match(r"\btitle=[\"']([^\"']+)[\"']", raw_content)
    if not title_html:
        title_html = _first_match(r"\balt=[\"']([^\"']+)[\"']", raw_content)
    name = _strip_html(title_html)

    if not name:
        return None

    image_tag = _first_match(r"(<img\b[^>]*>)", raw_content)
    image = ""
    for attr in ("data-src", "data-lazy-src", "src"):
        image = _html_attr(image_tag, attr)
        if image:
            break
    image = _absolute_url(image, source_url) or "NA"

    price_block = _first_match(
        r"<span[^>]+class=[\"'][^\"']*\bprice\b[^\"']*[\"'][^>]*>(.*?)</span>",
        raw_content,
    )
    amounts = [_clean_float(value) for value in re.findall(r"(?:AED|د\.إ|&#x62f;&#x2e;&#x625;)?\s*(\d[\d,.]*)", price_block)]
    amounts = [value for value in amounts if value is not None]
    if not amounts:
        amounts = [_clean_float(_first_match(r"\b(?:AED|د\.إ)\s*(\d[\d,.]*)", raw_content))]
        amounts = [value for value in amounts if value is not None]

    original = max(amounts) if amounts else None
    discounted = min(amounts) if amounts else original
    brand = _brand_from_known_text(name, detail_url)
    product_for_type = {"product_name": name, "brand": brand, "link": detail_url}
    quantity = _quantity_from_text(name, detail_url, raw_content)
    pack_format = _pack_format_from_text(name, detail_url, image, raw_content)
    product_type = _resolve_type(product_for_type, raw_content, detail_url)
    sub_type = _resolve_sub_type(product_for_type, raw_content, detail_url)
    units = _units_from_text(name, detail_url, raw_content)

    return {
        "platform": entry.get("platform", "jmkcellars"),
        "product_name": name,
        "brand": brand,
        "type": product_type,
        "sub_type": sub_type,
        "quantity": quantity,
        "units": units,
        "pack_format": pack_format,
        "currency": "AED",
        "original_price_local": original,
        "discounted_price_local": discounted,
        "original_price_usd": round(original * AED_TO_USD, 2) if original is not None else None,
        "discounted_price_usd": round(discounted * AED_TO_USD, 2) if discounted is not None else None,
        "discount_percentage": round((original - discounted) / original * 100, 2)
        if original and discounted and discounted < original
        else 0.0,
        "link": detail_url,
        "image_link": image,
        "availability": "yes",
        "features_in_top10": entry.get("features_in_top10", "no"),
        "features_on_first_page": entry.get("features_on_first_page", "no"),
        "date": entry.get("date", "NA"),
        "region": entry.get("region", "Other Emirates"),
    }


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text or "", flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _gmp_sanitize_html(raw_content: str) -> str:
    if not raw_content:
        return raw_content

    raw_content = re.split(
        r"<(?:section|div)[^>]+class=[\"'][^\"']*\brelated\b[^\"']*[\"'][^>]*>",
        raw_content,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    # Next.js storefront: related-products slider follows the main product.
    return raw_content.split("You May Also Like", 1)[0]


def _gmp_variations(raw_content: str) -> list[dict]:
    match = re.search(
        r"\bdata-product_variations\s*=\s*([\"'])(.*?)\1",
        raw_content or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    raw_json = html_lib.unescape(match.group(2))
    try:
        variations = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    return [variation for variation in variations if isinstance(variation, dict)]


def _gmp_units_from_text(*texts: str) -> int:
    text = " ".join(str(value).lower() for value in texts if value)
    patterns = [
        r"\bcase\s+of\s+(\d+)\b",
        r"\bpack\s+of\s+(\d+)\b",
        r"\b(\d+)\s*[-\s]*pack\b",
        r"\b(\d+)\s*(?:cans?|bottles?)\b",
        r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return 1


def _gmp_variation_label(variation: dict) -> str:
    attributes = variation.get("attributes") if isinstance(variation.get("attributes"), dict) else {}
    return " ".join(str(value) for value in attributes.values() if value)


def _gmp_pack_format(raw_content: str, entry: dict, name: str, label: str, image_link: str, variation: dict | None = None) -> str:
    attributes = variation.get("attributes") if isinstance(variation, dict) and isinstance(variation.get("attributes"), dict) else {}
    attribute_text = " ".join(
        [str(key) for key in attributes.keys()]
        + [str(value) for value in attributes.values()]
    ).lower()

    if re.search(r"\bno[-_ ]of[-_ ]cans?\b|\bcans?\b", attribute_text):
        return "Can"
    if re.search(r"\bno[-_ ]of[-_ ]bottles?\b|\bbottles?\b", attribute_text):
        return "Glass"

    pack_format = _pack_format_from_text(name, label, entry.get("link", ""), image_link)
    if pack_format != "NA":
        return pack_format

    product_text = _strip_html(raw_content)
    pack_format = _pack_format_from_text(product_text)
    if pack_format != "NA":
        return pack_format

    if image_link and image_link not in ("NA", "data not available"):
        pack_format = _detect_pack_format_from_image(image_link, entry.get("link") or name)
        if pack_format != "NA":
            return pack_format

    return "NA"


def _gmp_variation_price(variation: dict, *keys: str) -> float | None:
    for key in keys:
        price = _clean_float(variation.get(key))
        if price is not None:
            return price
    return None


def _gmp_image(raw_content: str, variation: dict | None = None) -> str:
    if isinstance(variation, dict):
        image = variation.get("image")
        if isinstance(image, dict):
            for key in ("full_src", "src", "url"):
                if image.get(key):
                    return image[key]

    tag = _first_match(r"(<img\b[^>]+class=[\"'][^\"']*wp-post-image[^\"']*[\"'][^>]*>)", raw_content)
    if not tag:
        tag = _first_match(r"(<img\b[^>]*>)", raw_content)

    return _html_attr(tag, "src") or "NA"


def _gmp_availability(variation: dict | None, raw_content: str) -> str:
    text = ""
    if isinstance(variation, dict):
        text = str(variation.get("availability_html") or "")
    text = f"{text} {re.sub(r'<script.*?</script>', '', raw_content, flags=re.S)}".lower()

    if re.search(r"\bout\s+of\s+stock\b|\bunavailable\b|\bsold\s+out\b", text):
        return "no"
    if not variation and "add to cart" not in text:
        return "no"
    return "yes"


def _gmp_base_prices(raw_content: str) -> tuple[float | None, float | None]:
    price_html = _first_match(r"<p[^>]+class=[\"'][^\"']*\bprice\b[^\"']*[\"'][^>]*>(.*?)</p>", raw_content)
    amounts = [_clean_float(value) for value in re.findall(r"<bdi[^>]*>.*?(\d[\d,.]*)\s*</bdi>", price_html, flags=re.IGNORECASE | re.DOTALL)]
    amounts = [amount for amount in amounts if amount is not None]
    if len(amounts) >= 2:
        return amounts[0], amounts[-1]
    if amounts:
        return amounts[0], amounts[0]
    # Next.js storefront: <span aria-label="AED" class="dirham-symbol"></span><span ...></span>12
    amounts = [
        _clean_float(v)
        for v in re.findall(r'dirham-symbol"></span><span[^>]*></span>\s*(\d[\d,.]*)', raw_content)
    ]
    amounts = [a for a in amounts if a is not None]
    if amounts:
        return max(amounts), min(amounts)
    return None, None


def _gmp_item(raw_content: str, entry: dict, variation: dict | None = None) -> dict | None:
    name = _strip_html(_first_match(r"<h1[^>]*>(.*?)</h1>", raw_content))
    if not name:
        return None

    label = _gmp_variation_label(variation or {})
    image_link = _gmp_image(raw_content, variation)

    if variation:
        original = _gmp_variation_price(variation, "display_regular_price", "display_price")
        discounted = _gmp_variation_price(variation, "display_price", "display_regular_price")
        units = _gmp_units_from_text(label)
    else:
        original, discounted = _gmp_base_prices(raw_content)
        units = _gmp_units_from_text(name, entry.get("link", ""))

    if discounted is None:
        discounted = original

    brand = _centaurus_brand(name)
    pack_format = _gmp_pack_format(raw_content, entry, name, label, image_link, variation)

    item = {
        "platform": "gmp",
        "product_name": name,
        "brand": brand,
        "type": _resolve_type({"product_name": name, "brand": brand, "link": entry.get("link", "")}, raw_content, entry.get("link", "")),
        "sub_type": "regular",
        "quantity": _quantity_from_text(name, label, entry.get("link", "")),
        "units": units,
        "pack_format": pack_format,
        "currency": "AED",
        "original_price_local": original,
        "discounted_price_local": discounted,
        "original_price_usd": round(original * AED_TO_USD, 2) if original is not None else None,
        "discounted_price_usd": round(discounted * AED_TO_USD, 2) if discounted is not None else None,
        "discount_percentage": round((original - discounted) / original * 100, 2) if original and discounted and discounted < original else 0.0,
        "link": entry.get("link", ""),
        "image_link": image_link,
        "availability": _gmp_availability(variation, raw_content),
        "features_in_top10": "no",
        "features_on_first_page": "no",
    }
    item["sub_type"] = _resolve_sub_type(item, html_content=raw_content, source_url=entry.get("link", ""))
    return item


def gmp_items_from_html(raw_content: str, entry: dict) -> list[dict]:
    raw_content = _gmp_sanitize_html(raw_content)
    variations = _gmp_variations(raw_content)
    if variations:
        items = [
            _gmp_item(raw_content, entry, variation)
            for variation in variations
        ]
        return [item for item in items if item]

    item = _gmp_item(raw_content, entry)
    return [item] if item else []


def _centaurus_hidden_input(block: str, name: str) -> str:
    for tag in re.findall(r"<input\b[^>]*>", block or "", flags=re.IGNORECASE | re.DOTALL):
        if _html_attr(tag, "name") == name:
            return _html_attr(tag, "value")
    return ""


def _centaurus_first(pattern: str, block: str) -> str:
    match = re.search(pattern, block or "", flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _centaurus_image_url(value: str) -> str:
    image = html_lib.unescape(str(value or "")).strip()
    if not image:
        return "NA"
    if image.startswith("//"):
        return f"https:{image}"
    if image.startswith(("http://", "https://")):
        return image
    if re.search(r"\.(?:png|jpe?g|webp|gif)(?:\?|$)", image, flags=re.IGNORECASE):
        return f"https://centaurusint.net/r_imgs.php?thumb={image}&w=400&h=400"
    return "NA"


def _centaurus_price_value(value: str) -> float | None:
    return _clean_float(_strip_html(value))


def _centaurus_prices(block: str) -> tuple[float | None, float | None]:
    current_html = _centaurus_first(
        r"<span[^>]+class=[\"'][^\"']*\bcurrent-price\b[^\"']*[\"'][^>]*>(.*?)</span>",
        block,
    )
    old_html = _centaurus_first(
        r"<span[^>]+class=[\"'][^\"']*\bold-price\b[^\"']*[\"'][^>]*>(.*?)</span>",
        block,
    )

    current = _centaurus_price_value(current_html)
    old = _centaurus_price_value(old_html)

    if current is None:
        current = _clean_float(_centaurus_first(r"\bcurrent-price\b.{0,240}?(\d[\d,.]*)\s*AED", block))
    if old is None:
        old = _clean_float(_centaurus_first(r"\bold-price\b.{0,240}?(\d[\d,.]*)\s*AED", block))

    if current is None:
        current = _clean_float(_centaurus_hidden_input(block, "price"))

    if current is None:
        price_html = _centaurus_first(
            r"<div[^>]+class=[\"'][^\"']*\bproduct-price\b[^\"']*[\"'][^>]*>(.*?)</div>",
            block,
        )
        current = _centaurus_price_value(price_html)

    if old is None:
        old = current

    return old, current


def _centaurus_units(name: str) -> int:
    text = str(name or "").lower()
    patterns = [
        r"\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:cl|ml|l)\b",
        r"\bx\s*(\d+)\s*(?:case|pack)?\b",
        r"\bcase\s+of\s+(\d+)\b",
        r"\bpack\s+of\s+(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return 1


def _centaurus_brand(name: str) -> str:
    normalized = _normalize_match_text(name)
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        candidate = _normalize_match_text(brand)
        if candidate and re.search(rf"\b{re.escape(candidate)}\b", normalized):
            return _normalize_brand(brand)

    words = [
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z']*", str(name or ""))
        if word.lower() not in {
            "beer",
            "beers",
            "btl",
            "bottle",
            "bottles",
            "can",
            "cans",
            "case",
            "pack",
            "promo",
            "regular",
            "premium",
            "strong",
            "light",
            "original",
        }
    ]
    return _normalize_brand(" ".join(words[:2]) if words else name)


def _centaurus_type(name: str, block: str, source_url: str) -> str:
    resolved = _resolve_type({"product_name": name, "brand": _centaurus_brand(name), "link": source_url}, block, source_url)
    if resolved != "other":
        return resolved

    text = f"{name} {source_url} {block}".lower()
    if "cider" in text:
        return "cider"
    if re.search(r"\b(?:beer|lager|ale|ipa|pils|pilsner|stout|porter|weizen|btl|bottle|can)\b", text):
        return "beer"
    return resolved


def _centaurus_card_blocks(raw_content: str) -> list[str]:
    parts = re.split(
        r"(?=<div[^>]+class=[\"'][^\"']*\bproduct-cart-wrap\b)",
        raw_content or "",
        flags=re.IGNORECASE,
    )
    return [
        part
        for part in parts
        if re.match(r"<div[^>]+class=[\"'][^\"']*\bproduct-cart-wrap\b", part, flags=re.IGNORECASE)
    ]


def _centaurus_panel_blocks(raw_content: str) -> list[str]:
    parts = re.split(
        r"(?=<div[^>]+class=[\"'][^\"']*\bcol-lg-4\b)",
        raw_content or "",
        flags=re.IGNORECASE,
    )
    return [
        part
        for part in parts
        if re.match(r"<div[^>]+class=[\"'][^\"']*\bcol-lg-4\b", part, flags=re.IGNORECASE)
        and re.search(r"\btitle-detail\b", part, flags=re.IGNORECASE)
    ]


def _centaurus_detail_block(raw_content: str) -> str:
    block = _centaurus_first(
        r"(<div[^>]+class=[\"'][^\"']*\brow\b[^\"']*\bmb-50\b[^\"']*[\"'][^>]*>.*?</div>\s*</div>\s*</div>)",
        raw_content,
    )
    return block or raw_content


def _centaurus_item_from_block(block: str, entry: dict) -> dict | None:
    name = _strip_html(_centaurus_first(r"<h1[^>]*>(.*?)</h1>", block))
    if not name:
        name = _strip_html(_centaurus_first(r"<h2[^>]+class=[\"'][^\"']*\btitle-detail\b[^\"']*[\"'][^>]*>(.*?)</h2>", block))
    if not name:
        name = _strip_html(_centaurus_first(r"<h2[^>]*>\s*<a[^>]*>(.*?)</a>\s*</h2>", block))
    if not name:
        name = _centaurus_hidden_input(block, "name")
    if not name:
        image_tag = _centaurus_first(r"(<img\b[^>]*>)", block)
        name = _strip_html(_html_attr(image_tag, "alt"))

    if not name:
        return None

    if name.strip().lower() in {"related products", "people who bought this item also bought"}:
        return None

    image = _centaurus_hidden_input(block, "image")
    if not image:
        image_tag = _centaurus_first(r"(<img\b[^>]*>)", block)
        image = _html_attr(image_tag, "src")
    image_link = _centaurus_image_url(image)

    original, discounted = _centaurus_prices(block)
    if discounted is None:
        discounted = original

    brand = _centaurus_brand(name)
    source_url = entry.get("link", "")
    pack_format = _pack_format_from_text(name, source_url, image_link)

    item = {
        "platform": "centaurusint",
        "product_name": name,
        "brand": brand,
        "type": _centaurus_type(name, block, source_url),
        "sub_type": "regular",
        "quantity": _quantity_from_text(name, source_url),
        "units": _centaurus_units(name),
        "pack_format": pack_format,
        "currency": "AED",
        "original_price_local": original,
        "discounted_price_local": discounted,
        "original_price_usd": round(original * AED_TO_USD, 2) if original is not None else None,
        "discounted_price_usd": round(discounted * AED_TO_USD, 2) if discounted is not None else None,
        "discount_percentage": round((original - discounted) / original * 100, 2) if original and discounted and discounted < original else 0.0,
        "link": source_url,
        "image_link": image_link,
        "availability": "yes",
        "features_in_top10": "no",
        "features_on_first_page": "no",
    }
    item["sub_type"] = _resolve_sub_type(item, html_content=block, source_url=source_url)
    return item


def centaurus_items_from_html(raw_content: str, entry: dict) -> list[dict]:
    if not raw_content:
        return []

    panel_blocks = _centaurus_panel_blocks(raw_content)
    if len(panel_blocks) > 1:
        panel_items = []
        for block in panel_blocks:
            item = _centaurus_item_from_block(block, entry)
            if item:
                panel_items.append(item)
        if panel_items:
            return panel_items

    h1_item = _centaurus_item_from_block(raw_content, entry)
    if h1_item and h1_item["product_name"] != "NA":
        return [h1_item]

    card_items = []
    for block in _centaurus_card_blocks(raw_content):
        item = _centaurus_item_from_block(block, entry)
        if item:
            card_items.append(item)
    if card_items:
        return card_items

    form_item = _centaurus_item_from_block(raw_content, entry)
    return [form_item] if form_item else []


def _sanitize_centaurus_html(raw_content: str) -> str:
    """
    Older Centaurus artifacts can include the right-side related-products rail.
    Those cards use the same form class as real product variants, so trim the
    artifact before the accessory-card title markup if present.
    """
    if not raw_content:
        return raw_content

    cleaned = re.split(
        r"<h5[^>]+class=[\"'][^\"']*\btitle-detail-acc\b",
        raw_content,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    return cleaned or raw_content


def is_intentionally_filtered(entry: dict, raw_content: str) -> bool:
    text = " ".join([
        str(entry.get("link", "")),
        raw_content,
    ]).lower()

    patterns = [
        r"\bhome\s+draught\b",
        r"\bdraught\s+system\b",
        r"\bdraught\s+tap\b",
        r"\btap\s+system\b",
        r"\bblade\s+home\b",
        r"\bblade\b.*\bsystem\b",
        r"\bdraught\b",
        r"\bnon[-\s/]*alco(?:holic)?\b",
        r"\balcohol[-\s]*free\b",
        r"\bzero[-\s]*alcohol\b",
        r"\b0\.0\b",
        r"\bzero\s+zero\b",
        r"\bcero\b",
        r"\bvodka\b",
        r"\bwhisk(?:y|ey)\b",
        r"\bscotch\b",
        r"\brum\b",
        r"\btequila\b",
        r"\bliqueur\b",
        r"\bshochu\b",
        r"\bsoju\b",
        r"\bsake\b",
        r"\bjunmai\b",
        r"\bdaiginjo\b",
        r"\bginjo\b",
        r"\bdassai\b",
        r"\bchoya\b",
        r"\bgin\s+tonic\b",
        r"\bcocktail\b",
        r"\bmg[-\s]*spirit\b",
        r"\bbacardi\s+breezer\b",
        r"\b__trashed\b",
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def _is_out_of_scope_extracted_item(item: dict) -> bool:
    text = " ".join(str(value).lower() for value in [
        item.get("product_name", ""),
        item.get("brand", ""),
        item.get("type", ""),
        item.get("sub_type", ""),
        item.get("link", ""),
        item.get("image_link", ""),
    ] if value)

    patterns = [
        r"\bhome\s+draught\b",
        r"\bdraught\s+system\b",
        r"\bdraught\s+tap\b",
        r"\btap\s+system\b",
        r"\bblade\s+home\b",
        r"\bblade\b.*\bsystem\b",
        r"\bbeer\s+blade\b",
        r"\bnon[-\s/]*alco(?:holic)?\b",
        r"\balcohol[-\s]*free\b",
        r"\bzero[-\s]*alcohol\b",
        r"\b0\.0\b",
        r"\bzero\s+zero\b",
        r"\bcero\b",
        r"\bvodka\b",
        r"\bwhisk(?:y|ey)\b",
        r"\bscotch\b",
        r"\brum\b",
        r"\btequila\b",
        r"\bliqueur\b",
        r"\bshochu\b",
        r"\bsoju\b",
        r"\bsake\b",
        r"\bjunmai\b",
        r"\bdaiginjo\b",
        r"\bginjo\b",
        r"\bdassai\b",
        r"\bchoya\b",
        r"\bgin\s+tonic\b",
        r"\bgin\b",
        r"\bcocktail\b",
        r"\bmg[-\s]*spirit\b",
        r"\bbacardi\s+breezer\b",
        r"\bsmirnoff\s+ice\b",
        r"\bgrins\b",
        r"\brtd\b",
        r"\b__trashed\b",
    ]
    if any(re.search(pattern, text) for pattern in patterns):
        return True

    return str(item.get("type", "")).lower().strip() not in {"beer", "cider"}


def _dubaidutyfree_units(name: str) -> int:
    """'12 Cans x 330ml', '24x330ml', 'Sol 12 Bottle Pack 330ml' -> pack count."""
    match = re.search(r"\b(\d{1,3})\s*(?:x|bottles?|cans?|pack)", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 1


def dubaidutyfree_base_item(payload: dict, entry: dict) -> dict | None:
    """OCC /ccstore/v1 product record (+ stockStatus merged in by the scraper).
    listPrices = original, salePrices (when set) = discounted. AED-0 items are
    the shop's free-gift (GWP) placeholders, not beer — dropped."""
    title = str(payload.get("displayName", "")).strip()
    prices = payload.get("listPrices") or {}
    original = prices.get("aED")
    if not title or not original:
        return None

    sale = (payload.get("salePrices") or {}).get("aED")
    discounted = sale if sale else original
    brand = _normalize_brand(str(payload.get("brand") or title.split()[0]))
    # primaryFullImageURL is "/ccstore/v1/images/?source=/file/.../x.jpg" — the
    # storefront serves the same asset at the bare /file/... path.
    image_path = str(payload.get("primaryFullImageURL", "")).split("source=", 1)[-1]
    image_link = f"https://www.dubaidutyfree.com{image_path}" if image_path.startswith("/file/") else ""
    pack_format = _pack_format_from_text(title)
    if pack_format == "NA" and image_link:
        pack_format = _detect_pack_format_from_image(image_link, title)

    item = {
        "platform": "dubaidutyfree",
        "product_name": title,
        "brand": brand,
        "type": "NA",
        "sub_type": "regular",
        "quantity": _quantity_from_text(title),
        "units": _dubaidutyfree_units(title),
        "pack_format": pack_format,
        "currency": "AED",
        "original_price_local": original,
        "discounted_price_local": discounted,
        "original_price_usd": round(original * AED_TO_USD, 2),
        "discounted_price_usd": round(discounted * AED_TO_USD, 2),
        "discount_percentage": round((original - discounted) / original * 100, 2) if discounted < original else 0.0,
        "link": entry["link"],
        "image_link": image_link,
        "availability": "yes" if payload.get("stockStatus") == "IN_STOCK" else "no",
        "features_in_top10": entry.get("features_in_top10", "no"),
        "features_on_first_page": entry.get("features_on_first_page", "no"),
    }
    # Beer-category feed: anything _resolve_type can't place (e.g. "Golden Ales") is still beer.
    resolved_type = _resolve_type(item, html_content="", source_url=entry["link"])
    item["type"] = "cider" if resolved_type == "cider" else "beer"
    # Title only — the JSON payload's description/tasting-note text pollutes sub_type matching
    # (Brewdog IPA came out as "black heart").
    item["sub_type"] = _resolve_sub_type(item, html_content="", source_url=entry["link"])
    return item


def extract_entry(entry: dict, s3: S3Client) -> list[dict]:
    input_type = entry.get("input_type", "html")

    if input_type == "json":
        payload = entry.get("extraction_payload")

        if payload is None or entry.get("platform") == "spinneysauh":
            payload = read_json(s3, entry["product_source_s3_uri"])

        raw_content = json.dumps(payload, ensure_ascii=False)
    else:
        raw_content = read_text(s3, entry["product_html_s3_uri"])

    if entry.get("platform") == "highspiritsuae" and input_type == "html":
        # "You might also like" slider lives inside div.product-info-main; on
        # out-of-stock pages (no price block of their own) the LLM was picking
        # a related product's name/price (e.g. Red Rose @ 115) for the page.
        raw_content = raw_content.split('x-data="productSliderAll', 1)[0]

    if entry.get("platform") == "centaurusint":
        raw_content = _sanitize_centaurus_html(raw_content)
        product_data = centaurus_items_from_html(raw_content, entry)
        if product_data:
            extracted_items = [apply_entry_overrides(product, entry.copy()) for product in product_data]
            return postprocess_items(extracted_items, entry, None)

    if entry.get("platform") == "premiumcellars" and input_type == "json":
        base_item = premiumcellars_base_item(payload, entry)
        if base_item:
            extracted_items = [apply_entry_overrides(base_item, entry.copy())]
            return postprocess_items(extracted_items, entry, payload)
        log.warning(f"[SKIP] Filtered out-of-scope product: {entry['link']}")
        return []

    if entry.get("platform") == "dubaidutyfree" and input_type == "json":
        base_item = dubaidutyfree_base_item(payload, entry)
        if base_item:
            extracted_items = [apply_entry_overrides(base_item, entry.copy())]
            return postprocess_items(extracted_items, entry, payload)
        log.warning(f"[SKIP] Filtered out-of-scope product: {entry['link']}")
        return []

    if entry.get("platform") == "gmp" and input_type == "html":
        product_data = gmp_items_from_html(raw_content, entry)
        product_data = [
            product
            for product in product_data
            if not _is_out_of_scope_extracted_item(product)
        ]
        if product_data:
            extracted_items = [apply_entry_overrides(product, entry.copy()) for product in product_data]
            return postprocess_items(extracted_items, entry, None)
        log.warning(f"[SKIP] Filtered out-of-scope product: {entry['link']}")
        return []

    if input_type == "json" and entry.get("platform") == "spinneysauh" and isinstance(payload, dict):
        extracted_items = [apply_entry_overrides(spinneys_fallback_item(payload, entry), entry.copy())]
        return postprocess_items(extracted_items, entry, payload)

    product_data = parse_html_code(
        raw_content,
        input_type=input_type,
        source_url=entry["link"],
    )

    if not product_data:
        if entry.get("platform") == "jmkcellars" and input_type == "html":
            fallback_item = _jmk_card_item_from_html(raw_content, entry)
            if fallback_item and not _is_out_of_scope_extracted_item(fallback_item):
                log.warning(f"[FALLBACK] Deterministic JMK card extraction for {entry['link']}")
                extracted_items = [apply_entry_overrides(fallback_item, entry.copy())]
                return postprocess_items(extracted_items, entry, None)
            if fallback_item:
                log.warning(f"[SKIP] Filtered out-of-scope product: {entry['link']}")
                return []
        if input_type == "json" and entry.get("platform") == "spinneysauh" and isinstance(payload, dict):
            log.warning(f"[FALLBACK] Deterministic Spinneys extraction for {entry['link']}")
            extracted_items = [apply_entry_overrides(spinneys_fallback_item(payload, entry), entry.copy())]
            return postprocess_items(extracted_items, entry, payload)
        if is_intentionally_filtered(entry, raw_content):
            log.warning(f"[SKIP] Filtered out-of-scope product: {entry['link']}")
            return []
        raise ValueError(f"parse_html_code returned no items for {entry['link']}")

    extracted_items = [
        apply_entry_overrides(product, entry.copy())
        for product in product_data
        if not _is_centaurus_related_item(product, entry)
    ]

    if entry.get("platform") == "highspiritsuae" and input_type == "html":
        extracted_items = _highspirits_pack_items(extracted_items, raw_content)
        _highspirits_fix_items(extracted_items, raw_content)

    return postprocess_items(extracted_items, entry, payload if input_type == "json" else None)


_HIGHSPIRITS_PACK_BUTTON = re.compile(
    r'<button[^>]*class="tier-button[^"]*"[^>]*data-price="([\d.]+)"\s+data-old-price="([\d.]+)"\s+data-qty="(\d+)"[^>]*>\s*([^<]+?)\s*<br',
)


def _highspirits_pack_items(items: list[dict], raw_content: str) -> list[dict]:
    """One row per PACK SIZE button ("Pack of 6", "Pack of 12", "CASE24",
    "NOS" = single). The LLM returns a single item priced as whichever option
    is preselected (usually the case) with units=1. Each button carries a
    per-qty price: total = data-price * data-qty; units = the number in the
    label, else data-qty (NOS)."""
    if not items:
        return items
    expanded = []
    for price, old_price, qty, label in _HIGHSPIRITS_PACK_BUTTON.findall(raw_content):
        units = re.search(r"\d+", label)
        discounted = round(float(price) * int(qty), 2)
        original = round(float(old_price) * int(qty), 2)
        item = dict(items[0])
        item["units"] = int(units.group()) if units else int(qty)
        item["original_price_local"] = original
        item["discounted_price_local"] = discounted
        item["original_price_usd"] = round(original * AED_TO_USD, 2)
        item["discounted_price_usd"] = round(discounted * AED_TO_USD, 2)
        item["discount_percentage"] = (
            round((original - discounted) / original * 100, 2) if original and discounted < original else 0.0
        )
        expanded.append(item)
    return expanded or items


def _highspirits_fix_items(items: list[dict], raw_content: str) -> None:
    """Deterministic overrides for what the LLM gets wrong on the Magento/Hyva
    pages: stock (Add to Cart button present == in stock), the shop's own
    0-price placeholder on unavailable products (-> no price), and 'o' typed
    for '0' in the volume ('5ocl' -> 50cl)."""
    main = re.sub(r"<script.*?</script>", "", raw_content, flags=re.S)
    in_stock = "add to cart" in main.lower()
    for item in items:
        item["availability"] = "yes" if in_stock else "no"
        for key in ("original_price_local", "discounted_price_local"):
            if item.get(key) == 0:
                item[key] = None
        if item.get("discounted_price_local") is None and item.get("original_price_local") is None:
            for key in ("original_price_usd", "discounted_price_usd"):
                item[key] = None
            item["discount_percentage"] = 0.0
        m = re.search(r"\b(\d+)o(\d*)\s*cl\b", item.get("product_name", ""), re.I)
        if m:
            item["quantity"] = f"{float(m.group(1) + '0' + m.group(2))}CL"


def extract_entry_with_retries(entry: dict, s3: S3Client) -> list[dict]:
    last_error = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            if attempt > 1:
                log.warning(f"[RETRY] {entry.get('link')} attempt {attempt}/{RETRY_ATTEMPTS}")
            return extract_entry(entry, s3)
        except Exception as e:
            last_error = e
            log.warning(f"[RETRY] {entry.get('link')} failed attempt {attempt}/{RETRY_ATTEMPTS}: {e}")

    raise RuntimeError(f"Extraction failed after {RETRY_ATTEMPTS} attempts: {last_error}")


def extract_manifest(
    site: str,
    manifest_uri: str,
    output_uri: str = "",
    concurrency: int | None = None,
) -> list[dict]:
    s3 = S3Client()

    try:
        manifest = read_json(s3, manifest_uri)
    except Exception as e:
        if is_missing_s3_key_error(e):
            log.warning(f"[{site}] Manifest not found, skipping: {manifest_uri}")
            return []
        raise

    if not isinstance(manifest, list):
        raise ValueError(f"Manifest must be a list: {manifest_uri}")

    products = []
    skipped = 0
    failed_entries = []
    total = len(manifest)

    max_workers = concurrency or settings.CONCURRENCY

    log.info(f"[{site}] Extracting {total} products from {manifest_uri} with concurrency={max_workers}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_entry = {
            executor.submit(extract_entry_with_retries, entry, s3): entry
            for entry in manifest
        }

        for completed, future in enumerate(as_completed(future_to_entry), start=1):
            entry = future_to_entry[future]

            try:
                extracted_items = future.result()
            except Exception as e:
                failed_entries.append(entry)
                log.error(f"[{site}] Extraction failed for {entry.get('link')}: {e}")
                continue

            if not extracted_items:
                skipped += 1
                continue

            products.extend(extracted_items)
            log.info(f"[{site}] Progress {completed}/{total} extracted={len(products)} skipped={skipped}")

    if failed_entries:
        failed_links = "\n".join(f"- {entry.get('link')}" for entry in failed_entries)
        log.warning(
            f"[{site}] {len(failed_entries)} product(s) failed after retries — "
            f"skipping and uploading partial output ({len(products)} products extracted).\n"
            f"{failed_links}"
        )

    position_by_link = {
        entry["link"]: entry.get("position", idx)
        for idx, entry in enumerate(manifest, start=1)
    }
    products.sort(key=lambda item: position_by_link.get(item["link"], 999999))
    first_page_limit = first_page_limit_for(site, products[0] if products else None)

    groups: dict[str, list[int]] = {}
    ordered_group_keys: list[str] = []
    for idx, item in enumerate(products):
        key = feature_group_key(item) or f"row:{idx}"
        if key not in groups:
            groups[key] = []
            ordered_group_keys.append(key)
        groups[key].append(idx)

    for item in products:
        item["features_in_top10"] = "no"
        if first_page_limit:
            item["features_on_first_page"] = "no"

    for group_position, key in enumerate(ordered_group_keys, start=1):
        primary_idx = primary_variant_index(groups[key], products, site)
        products[primary_idx]["features_in_top10"] = "yes" if group_position <= 10 else "no"
        if first_page_limit:
            products[primary_idx]["features_on_first_page"] = "yes" if group_position <= first_page_limit else "no"

    if output_uri:
        parsed = urlparse(output_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    else:
        date = manifest[0].get("date") if manifest else ""
        bucket, key = infer_output_key(site, date, manifest_uri)

    s3.put_json(bucket, key, products)
    log.success(f"[{site}] Uploaded {len(products)} products → s3://{bucket}/{key}")
    return products


def selected_sites(only: str) -> list[str]:
    if not only:
        return list(MANIFESTS)

    requested = [site.strip() for site in only.split(",") if site.strip()]
    unknown = sorted(set(requested) - set(MANIFESTS))

    if unknown:
        raise SystemExit(f"Unknown site(s): {', '.join(unknown)}")

    return requested


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract product JSON from stored HTML manifests."
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Date partition to extract, e.g. 2026-05-27.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated configured site names to extract. Default: all configured sites.",
    )
    parser.add_argument(
        "--manifest-uri",
        default="",
        help="Single manifest URI/path. Use with --only for an ad hoc run.",
    )
    parser.add_argument(
        "--output-uri",
        default="",
        help="Optional output s3:// URI for a single manifest run.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=settings.CONCURRENCY,
        help=f"Products to extract in parallel per site. Default: {settings.CONCURRENCY}.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.manifest_uri:
        site = args.only or "custom"
        extract_manifest(
            site,
            args.manifest_uri,
            output_uri=args.output_uri,
            concurrency=args.concurrency,
        )
        return

    for site in selected_sites(args.only):
        manifest_uri = s3_uri(S3_BUCKET, MANIFESTS[site].format(date=args.date))
        extract_manifest(site, manifest_uri, concurrency=args.concurrency)


if __name__ == "__main__":
    main()
