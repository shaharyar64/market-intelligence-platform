"""
Raw source collector for mmirak.ae.

Collects beer/cider product API JSON into S3 and uploads a manifest.
LLM extraction is handled separately by extract_from_html_manifests.py.
"""

import argparse
import os
import re
import sys
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, Timeout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from logger import get_logger
from s3 import S3Client

import settings

log = get_logger(__name__, log_file=settings.LOG_FILE)

PLATFORM = "mmihomedelivery"
REGION = "Other Emirates"
S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/mmihomedelivery-rak"

PAGE_SIZE = 100
FIRST_PAGE_LIMIT = 25
MAX_RETRIES = 5
RETRY_DELAY = 10

API_URL = "https://api.mmiprod.retter.io/o9pki8qf/CALL/ProductManager/searchProducts/default"
SITE_BASE = "https://www.mmirak.ae"
IMG_BASE = "https://api.mircate.com/5p1hp1d2t/CALL/PIMAPI/getImage/jux9er4tf08"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en;q=0.5",
    "channel-id": "alhamra",
    "content-type": "application/json",
    "origin": SITE_BASE,
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

PARAMS = {"__culture": "en-us"}
RAK_STOCK_CHANNEL = "H20_RAKAH"


def source_s3_key(url: str, date: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] or "product"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") or "product"
    return f"{S3_PREFIX}/product-source-json/{date}/{slug}.json"


def manifest_s3_key(date: str) -> str:
    return f"{S3_PREFIX}/product-source-json/{date}/manifest.json"


def localized_value(value, default: str = "") -> str:
    if isinstance(value, dict):
        return value.get("value", default)

    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("locale") == "en_US":
                return item.get("value", default)

    return value or default


def is_draught_product(*values: str) -> bool:
    return any("draught" in str(value).lower() for value in values if value)


def product_type_from_categories(categories: list[str]) -> str:
    category_segments = {
        segment.lower()
        for category in categories
        for segment in str(category).split("#")
    }

    if "cider" in category_segments:
        return "cider"
    if "beer" in category_segments or "beercider" in category_segments:
        return "beer"

    return ""


def image_url(filenames: list) -> str:
    if not filenames:
        return "NA"

    filename = filenames[0]
    if filename.startswith("http"):
        return filename

    return f"{IMG_BASE}?filename={filename}&quality=100"


def parse_price_text(text: str | None) -> float | None:
    if not text:
        return None

    cleaned = text.replace("AED", "").replace(",", "").strip()

    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def availability_from_api(api_item: dict) -> str:
    has_stock = api_item.get("hasStock", {})

    if isinstance(has_stock, dict) and RAK_STOCK_CHANNEL in has_stock:
        return "yes" if has_stock.get(RAK_STOCK_CHANNEL, 0) else "no"

    stock = api_item.get("calculatedStock", api_item.get("stock"))
    if isinstance(stock, (int, float)):
        return "yes" if stock > 0 else "no"

    return "yes"


def slim_product(api_item: dict) -> dict:
    product = api_item.get("product", {})
    price = api_item.get("price", {})
    slug = product.get("slug", {}).get("value", "")
    images = product.get("images", {}).get("value", [])

    list_price = parse_price_text(price.get("officialListPriceText"))
    sale_price = parse_price_text(price.get("officialSalePriceText"))

    return {
        "name": localized_value(product.get("title")),
        "sku": product.get("sku", ""),
        "slug": slug,
        "category": "Beer & Cider",
        "categories": product.get("categories", []),
        "platform": PLATFORM,
        "price": list_price,
        "discountPrice": sale_price if sale_price != list_price else None,
        "image_link": image_url(images),
        "link": f"{SITE_BASE}/product/{slug}",
        "availability": availability_from_api(api_item),
    }


def fetch_page(from_offset: int) -> dict:
    payload = {
        "from": from_offset,
        "pageSize": PAGE_SIZE,
        "categories": ["beerCider"],
        "sorting": "-stock",
    }

    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.post(
                API_URL,
                headers=HEADERS,
                params=PARAMS,
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
            return res.json()

        except (ConnectionError, Timeout, OSError) as e:
            if attempt == MAX_RETRIES:
                log.error(f"API offset {from_offset}: failed after {MAX_RETRIES} attempts — {e}")
                raise

            log.warning(f"API offset {from_offset}: network error on attempt {attempt}/{MAX_RETRIES}: {e}; retrying in {delay}s")
            time.sleep(delay)
            delay *= 2

        except Exception as e:
            log.error(f"API offset {from_offset}: unexpected error — {e}")
            raise

    raise RuntimeError(f"Failed to fetch API offset {from_offset}")


def fetch_products() -> list[dict]:
    first_page = fetch_page(0)
    total = first_page.get("total", 0)
    products = first_page.get("result", [])

    log.info(f"API reported {total} beer/cider products")

    for offset in range(PAGE_SIZE, total, PAGE_SIZE):
        page = fetch_page(offset)
        products.extend(page.get("result", []))

    return products[:total] if total else products


def collect_sources(date: str) -> list[dict]:
    s3 = S3Client()
    products = fetch_products()
    manifest = []
    skipped_draught = 0

    for position, api_item in enumerate(products, start=1):
        product = api_item.get("product", {})
        slug = product.get("slug", {}).get("value", f"unknown-{position}")
        title = localized_value(product.get("title"))
        link = f"{SITE_BASE}/product/{slug}"

        if is_draught_product(slug, title):
            skipped_draught += 1
            log.warning(f"[SKIP] Draught product: {slug}")
            continue

        key = source_s3_key(link, date)
        s3.put_json(S3_BUCKET, key, api_item)

        categories = product.get("categories", [])
        slim = slim_product(api_item)
        manifest.append({
            "link": link,
            "position": len(manifest) + 1,
            "features_in_top10": "yes" if len(manifest) < 10 else "no",
            "features_on_first_page": "yes" if len(manifest) < FIRST_PAGE_LIMIT else "no",
            "platform": PLATFORM,
            "region": REGION,
            "date": date,
            "availability": slim["availability"],
            "input_type": "json",
            "product_source_s3_key": key,
            "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
            "context": {
                "category": "Beer & Cider",
                "type_hint": product_type_from_categories(categories),
            },
            "extraction_payload": slim,
        })

        log.info(f"[JSON] Uploaded s3://{S3_BUCKET}/{key}")

    manifest_key = manifest_s3_key(date)
    s3.put_json(S3_BUCKET, manifest_key, manifest)

    log.success(f"Uploaded JSON manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    log.info(f"Skipped {skipped_draught} draught products")
    return manifest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect MMI RAK product API JSON and upload an S3 manifest."
    )
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collect_sources(args.date)
