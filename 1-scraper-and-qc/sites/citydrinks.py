import argparse
import os
import sys
import time
import urllib.parse
from datetime import UTC, datetime

import requests
from requests.exceptions import ConnectionError, Timeout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/citydrinks"
BASE_URL = "https://api2.citydrinks.com/catalog/v1/client/categories/beer-18/products"
WAREHOUSE = "DSKEZ"
PAGE_SIZE = 48
MAX_RETRIES = 5
RETRY_DELAY = 10

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "origin": "https://citydrinks.com",
    "referer": "https://citydrinks.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "x-company-id": "1eb53a13-5f9e-4deb-92d7-090a4b53fd21",
    "x-lang": "en",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Collect CityDrinks product source JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def slim_product(product: dict) -> dict:
    variant = product.get("variants", [{}])[0] if product.get("variants") else {}
    images = product.get("images", [])
    image_url = ""

    if images:
        image_url = images[0].get("orig") or images[0].get("url") or ""

    price = product.get("price")
    discount_price = product.get("discountPrice")

    return {
        "name": product.get("name", ""),
        "slug": product.get("slug", ""),
        "price": round(price / 100, 2) if price is not None else None,
        "discountPrice": round(discount_price / 100, 2) if discount_price is not None else None,
        "volume": variant.get("value", ""),
        "image_url": image_url,
    }


def _proxies() -> dict | None:
    server = os.getenv("PROXY_SERVER")
    if not server:
        return None
    username = os.getenv("PROXY_USERNAME")
    password = os.getenv("PROXY_PASSWORD")
    if username and password:
        scheme, _, host = server.partition("://")
        server = f"{scheme}://{username}:{password}@{host}"
    return {"http": server, "https": server}


def fetch_page(page: int) -> dict:
    params = {
        "warehouseCode": WAREHOUSE,
        "page[size]": str(PAGE_SIZE),
        "page[current]": str(page),
        "sort[0][field]": "salesQuantity",
        "sort[0][order]": "DESC",
    }
    target_url = BASE_URL + "?" + urllib.parse.urlencode(params)

    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(target_url, headers=HEADERS, proxies=_proxies(), timeout=60)
            response.raise_for_status()
            return response.json()
        except (ConnectionError, Timeout, OSError) as e:
            if attempt == MAX_RETRIES:
                raise
            log.warning(f"Page {page}: Network error (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(delay)
            delay *= 2


def source_key(product: dict, position: int, date: str) -> str:
    slug = product.get("slug") or f"product-{position:04d}"
    return f"{S3_PREFIX}/product-source-json/{date}/{slug}.json"


def manifest_entry(product: dict, position: int, date: str) -> dict:
    key = source_key(product, position, date)
    slug = product.get("slug") or f"product-{position:04d}"
    slim = slim_product(product)

    return {
        "link": f"https://citydrinks.com/p/{slug}",
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= PAGE_SIZE else "no",
        "platform": "citydrinks",
        "region": "Dubai",
        "date": date,
        "input_type": "json",
        "currency": "AED",
        "image_link": slim.get("image_url", ""),
        "postprocess": "citydrinks_multibuy",
        "multibuyPriceLevels": product.get("multibuyPriceLevels", []) or [],
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
        "extraction_payload": slim,
    }


def main():
    args = parse_args()
    page = 1
    total_pages = None
    raw_products = []
    skipped = 0

    while True:
        response_data = fetch_page(page)
        products = response_data["data"]["products"]
        pagination = response_data["pagination"]

        if total_pages is None:
            total = pagination["total"]
            total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
            log.info(f"Total products: {total}, total pages: {total_pages}")

        log.info(f"Page {page}/{total_pages}: Got {len(products)} products")

        for product in products:
            if "draught" in product.get("name", "").lower():
                skipped += 1
                continue
            raw_products.append(product)

        if page >= total_pages:
            break

        page += 1
        time.sleep(2)

    s3 = S3Client()
    manifest = []

    for position, product in enumerate(raw_products, start=1):
        entry = manifest_entry(product, position, args.date)
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], product)
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-source-json/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded source manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    log.info(f"Skipped draught products: {skipped}")


if __name__ == "__main__":
    main()
