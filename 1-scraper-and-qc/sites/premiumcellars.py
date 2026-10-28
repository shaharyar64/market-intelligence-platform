"""
Collector for premiumcellars.ae — a Shopify store. Shopify exposes a public
`/products.json` endpoint per collection with full structured product data
(title, vendor, variants incl. price/sku), so this hits that API directly
instead of scraping HTML with Playwright.
"""

import argparse
import os
import sys
from datetime import UTC, datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/premiumcellars"
BASE_URL = "https://premiumcellars.ae"
COLLECTION_HANDLE = "beer-cider-new-collection"
PRODUCTS_JSON_URL = f"{BASE_URL}/collections/{COLLECTION_HANDLE}/products.json"
REGION = "Other Emirates"


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Premium Cellars beer/cider product JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def fetch_all_products() -> list[dict]:
    products = []
    page = 1

    while True:
        response = requests.get(PRODUCTS_JSON_URL, params={"limit": 250, "page": page}, timeout=30)
        response.raise_for_status()
        batch = response.json().get("products", [])

        if not batch:
            break

        products.extend(batch)
        log.info(f"[premiumcellars] Page {page}: {len(batch)} products")

        if len(batch) < 250:
            break

        page += 1

    return products


def source_key(handle: str, date: str) -> str:
    return f"{S3_PREFIX}/product-source-json/{date}/{handle}.json"


def manifest_entry(product: dict, position: int, total: int, date: str) -> dict:
    handle = product["handle"]
    link = f"{BASE_URL}/products/{handle}"
    key = source_key(handle, date)

    return {
        "link": link,
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= total else "no",
        "platform": "premiumcellars",
        "region": REGION,
        "date": date,
        "input_type": "json",
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
    }


def main() -> None:
    args = parse_args()
    products = fetch_all_products()
    log.info(f"[premiumcellars] Total products: {len(products)}")

    s3 = S3Client()
    manifest = []

    for position, product in enumerate(products, start=1):
        entry = manifest_entry(product, position, len(products), args.date)
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], product)
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-source-json/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(
        f"[premiumcellars] Uploaded source manifest with {len(manifest)} products → "
        f"s3://{S3_BUCKET}/{manifest_key}"
    )


if __name__ == "__main__":
    main()
