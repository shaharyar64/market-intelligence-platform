import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime

import requests
from requests.exceptions import ConnectionError, Timeout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client

log = get_logger(__name__, log_file=settings.LOG_FILE)

STORES = {
    "auh": {
        "platform": "africaneasternonline",
        "store_code": "auh",
        "store_view_code": "auh",
        "website_code": "auh",
        "source_code": "musaffah",
        "region": "Abu Dhabi",
        "stock_attribute": "product_stock_musaffah",
        "customer_group": "21",
        "delivery_type": "scheduled",
        "location_name": "Al Marina",
        "source_options": [
            {"source_code": "musaffah", "stock_attribute": "product_stock_musaffah", "location_name": "Al Marina"},
            {"source_code": "rowdhat", "stock_attribute": "product_stock_rowdhat", "location_name": "Rowdhat"},
        ],
        "s3_prefix": "beer-pricing/africaneastern-abu-dabhi",
    },
    "rak": {
        "platform": "africaneasternonline",
        "store_code": "rak",
        "store_view_code": "rak",
        "website_code": "rak",
        "source_code": "rak",
        "region": "Other Emirates",
        "stock_attribute": "product_stock_rak",
        "customer_group": "19",
        "delivery_type": "scheduled",
        "location_name": "Al Araibi",
        "source_options": [
            {"source_code": "rak", "stock_attribute": "product_stock_rak", "location_name": "Al Araibi"},
            {"source_code": "marina", "stock_attribute": "product_stock_marina", "location_name": "Marina"},
        ],
        "s3_prefix": "beer-pricing/africaneastern-rak",
    },
    "dubai": {
        "platform": "africaneasternonline",
        "store_code": "main_website_store",
        "store_view_code": "default",
        "website_code": "base",
        "source_code": "oud_ds",
        "region": "Dubai",
        "stock_attribute": "product_stock_oud_ds",
        "customer_group": "4",
        "delivery_type": "scheduled",
        "location_name": "Dubai Marina",
        "source_options": [
            {"source_code": "oud_ds", "stock_attribute": "product_stock_oud_ds", "location_name": "Dubai Marina"},
            {"source_code": "marina", "stock_attribute": "product_stock_marina", "location_name": "Dubai Marina"},
            {"source_code": "bizbay", "stock_attribute": "product_stock_bizbay", "location_name": "Business Bay"},
        ],
        "s3_prefix": "beer-pricing/africaneastern-dubai",
    },
}

CURRENCY = "AED"
CURRENCY_MULTIPLIER = 0.272
PRODUCTS_PER_PAGE = 90
S3_BUCKET = "raw-data-prod"
MAX_RETRIES = 5
RETRY_DELAY = 10
CATALOG_URL = "https://catalog-service.adobe.io/graphql"
PRODUCT_URL = "https://www.africaneasternonline.com/graphql"
COMMON_HEADERS = {"accept": "*/*", "content-type": "application/json", "user-agent": "Mozilla/5.0"}

CATALOG_QUERY = """
query productListSearch($phrase: String!, $filter: [SearchClauseInput!], $sort: [ProductSearchSortInput!], $currentPage: Int, $pageSize: Int) {
  productSearch(phrase: $phrase, filter: $filter, sort: $sort, current_page: $currentPage, page_size: $pageSize) {
    total_count
    items { productView { sku name urlKey } }
    page_info { total_pages }
  }
}
"""

PRODUCT_QUERY = """
query GetProductDetails($filter: ProductAttributeFilterInput) {
  products(filter: $filter) {
    items {
      name sku brand_image
      categories { name path }
      media_gallery { url label }
      related_products { sku }
      price_range { minimum_price { regular_price { value currency } final_price { value currency } } }
      price_tax_tiers { quantity final_price { value currency } discount { amount_off percent_off } }
      rating_summary review_count
    }
  }
}
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Collect African Eastern GraphQL source JSON.")
    parser.add_argument("--store", choices=list(STORES), required=True)
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def make_catalog_headers(store: dict) -> dict:
    headers = {
        **COMMON_HEADERS,
        "x-api-key": "077e653596a74ac5a92ace8dff2367c0",
        "magento-store-code": store["store_code"],
        "magento-store-view-code": store["store_view_code"],
        "magento-website-code": store["website_code"],
        "magento-environment-id": "900a437b-79f0-4722-987f-3e1eedcab7f4",
    }
    if store.get("customer_group"):
        headers["Magento-Customer-Group"] = hashlib.sha1(str(store["customer_group"]).encode()).hexdigest()
    return headers


def make_product_headers(store: dict) -> dict:
    return {
        **COMMON_HEADERS,
        "origin": "https://www.africaneasternonline.com",
        "store": store["store_view_code"],
        "source-code": store["source_code"],
        "delivery-type": store["delivery_type"],
    }


def get_all_skus(store: dict) -> list[dict]:
    all_skus = []
    current_page = 1
    headers = make_catalog_headers(store)

    while True:
        payload = {
            "operationName": "productListSearch",
            "variables": {
                "phrase": "",
                "filter": [
                    {"attribute": "visibility", "in": ["Catalog, Search"]},
                    {"attribute": store["stock_attribute"], "eq": "1"},
                    {"attribute": "product_source", "eq": store["source_code"]},
                    {"attribute": "categoryPath", "eq": "beer-cider"},
                ],
                "sort": [{"attribute": "name", "direction": "ASC"}],
                "currentPage": current_page,
                "pageSize": PRODUCTS_PER_PAGE,
            },
            "query": CATALOG_QUERY,
        }
        delay = RETRY_DELAY
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.post(CATALOG_URL, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                break
            except requests.RequestException as error:
                if attempt == MAX_RETRIES:
                    raise
                log.warning(
                    f"[{store['store_code'].upper()}] Catalog page {current_page} attempt "
                    f"{attempt}/{MAX_RETRIES} failed: {error}. Retrying in {delay}s…"
                )
                time.sleep(delay)
                delay *= 2
        data = response.json()
        product_search = data["data"]["productSearch"]
        items = product_search["items"]
        total_pages = product_search["page_info"]["total_pages"]
        total_count = product_search.get("total_count")

        for item in items:
            view = item.get("productView", {})
            all_skus.append({"sku": view.get("sku"), "name": view.get("name"), "url_key": view.get("urlKey")})

        log.info(
            f"[{store['store_code'].upper()}] SKU page {current_page}/{total_pages} "
            f"- {len(items)} SKUs (total={total_count})"
        )

        if current_page >= total_pages:
            break

        current_page += 1
        time.sleep(0.5)

    seen = set()
    unique = []
    for item in all_skus:
        if item["sku"] not in seen:
            seen.add(item["sku"])
            unique.append(item)
    return unique


def fetch_product(sku: str, product_headers: dict) -> dict | None:
    payload = {
        "operationName": "GetProductDetails",
        "variables": {"filter": {"sku": {"eq": sku}}},
        "query": PRODUCT_QUERY,
    }
    delay = RETRY_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(PRODUCT_URL, headers=product_headers, json=payload, timeout=30)
            response.raise_for_status()
            items = response.json().get("data", {}).get("products", {}).get("items", [])
            return items[0] if items else None
        except (ConnectionError, Timeout, OSError):
            if attempt == MAX_RETRIES:
                raise
            time.sleep(delay)
            delay *= 2

    return None


def store_with_source_option(store: dict, source_option: dict) -> dict:
    selected = dict(store)
    selected.update(source_option)
    return selected


def get_all_skus_for_scheduled_store(store: dict) -> tuple[dict, list[dict]]:
    last_error = None
    for source_option in store.get("source_options", []):
        candidate = store_with_source_option(store, source_option)
        log.info(
            f"[{candidate['store_code'].upper()}] Trying {candidate['delivery_type']} delivery "
            f"location={candidate['location_name']} source={candidate['source_code']} "
            f"stock={candidate['stock_attribute']}"
        )
        try:
            sku_entries = get_all_skus(candidate)
        except requests.RequestException as error:
            last_error = error
            log.warning(
                f"[{candidate['store_code'].upper()}] Source {candidate['source_code']} failed: {error}"
            )
            continue

        if sku_entries:
            return candidate, sku_entries

        log.warning(
            f"[{candidate['store_code'].upper()}] Source {candidate['source_code']} returned 0 SKUs"
        )

    if last_error:
        raise last_error
    return store, []


def manifest_entry(store: dict, sku_entry: dict, raw: dict, position: int, date: str) -> dict:
    url_key = sku_entry.get("url_key") or sku_entry["sku"]
    key = f"{store['s3_prefix']}/product-source-json/{date}/{sku_entry['sku']}.json"
    gallery = raw.get("media_gallery", [])

    return {
        "link": f"https://www.africaneasternonline.com/{url_key}.html",
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= PRODUCTS_PER_PAGE else "no",
        "platform": store["platform"],
        "region": store["region"],
        "date": date,
        "input_type": "json",
        "currency": CURRENCY,
        "image_link": gallery[0]["url"] if gallery else "NA",
        "postprocess": "africaneastern_tiers",
        "price_tax_tiers": raw.get("price_tax_tiers") or [],
        "currency_multiplier": CURRENCY_MULTIPLIER,
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
    }


def run(store_key: str, date: str):
    store = STORES[store_key]
    store, sku_entries = get_all_skus_for_scheduled_store(store)
    product_headers = make_product_headers(store)
    s3 = S3Client()
    manifest = []
    skipped = 0

    for position, sku_entry in enumerate(sku_entries, start=1):
        sku = sku_entry["sku"]

        if "draught" in (sku_entry.get("name") or "").lower():
            skipped += 1
            continue

        raw = fetch_product(sku, product_headers)
        if not raw:
            skipped += 1
            continue

        entry = manifest_entry(store, sku_entry, raw, position, date)
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], raw)
        manifest.append(entry)
        log.info(f"[{position}/{len(sku_entries)}] Uploaded source for {sku}")
        time.sleep(0.3)

    manifest_key = f"{store['s3_prefix']}/product-source-json/{date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded source manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    log.info(f"Skipped products: {skipped}")


if __name__ == "__main__":
    args = parse_args()
    run(args.store, args.date)
