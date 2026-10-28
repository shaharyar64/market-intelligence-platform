"""
Collector for dubaidutyfree.com — an Oracle Commerce Cloud (OCC) storefront.
OCC exposes the same public JSON APIs the storefront itself calls, so this
reads them directly instead of scraping the client-rendered (Knockout.js)
pages with Playwright (whose detail-page render wait timed out on ~5 of the
~19 products every week):

- `/ccstoreui/v1/search` (Endeca) — the exact call the beer listing page makes:
  the visible, in-stock, priced products in the site's own ranking order. Out
  of stock items and AED-0 free gifts are not part of it, same as the site.
- `/ccstore/v1/products` — full product records (name, brand, prices, image).
- `/ccstore/v1/stockStatus` — per-product stock.
"""

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from urllib.parse import quote

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/dubaidutyfree"
BASE_URL = "https://www.dubaidutyfree.com"
API_URL = f"{BASE_URL}/ccstore/v1"
SEARCH_URL = f"{BASE_URL}/ccstoreui/v1/search"
CATEGORY_ID = "10786"
# Endeca dimension id of the Beer category, as sent by the listing page itself.
# If the catalog is re-indexed this goes stale and search returns 0 records,
# which main() treats as a hard failure rather than silently storing nothing.
SEARCH_DIMENSION_ID = "1201824698"
REGION = "Dubai"
PAGE_SIZE = 100
STOCK_BATCH = 20
FIRST_PAGE_LIMIT = 20  # matches FIRST_PAGE_LIMITS["dubaidutyfree"] in the extractor
# ~60-75% of requests 403 depending on which rotating-proxy exit IP is hit
# (every endpoint, random); 4 attempts failed a whole call on 2026-10-27.
MAX_RETRIES = 8
RETRY_DELAY = 5
MAX_RETRY_DELAY = 30  # worst case per call ~155s of sleeping
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def proxies_from_env() -> dict | None:
    """Fargate's datacenter IP gets a 403 from the API (the Playwright version also
    ran through the proxy), so route through the same PROXY_* settings."""
    server = os.getenv("PROXY_SERVER")
    if not server:
        return None
    host = server.split("://", 1)[-1]
    user, password = os.getenv("PROXY_USERNAME"), os.getenv("PROXY_PASSWORD")
    auth = f"{quote(user, safe='')}:{quote(password or '', safe='')}@" if user else ""
    url = f"http://{auth}{host}"
    return {"http": url, "https": url}


PROXIES = proxies_from_env()


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Dubai Duty Free beer/cider product JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def api_get(path: str, params: dict, base_url: str = API_URL) -> dict:
    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(f"{base_url}/{path}", params=params, headers=HEADERS, proxies=PROXIES, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == MAX_RETRIES:
                raise
            log.warning(f"[dubaidutyfree] {path} attempt {attempt}/{MAX_RETRIES} failed: {e}; retrying in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY)


def fetch_listing_ids() -> list[str]:
    """Product ids exactly as the beer listing page shows them, in site order."""
    data = api_get(
        "",
        {
            "N": SEARCH_DIMENSION_ID,
            "searchType": "simple",
            "No": 0,
            "Nrpp": 200,
            "Nf": "sku.activePrice|GT+0",
            "Nr": "product.x_availableInCatalog:online",
        },
        base_url=SEARCH_URL,
    )
    records = data.get("resultsList", {}).get("records", [])
    return [r["attributes"]["product.repositoryId"][0] for r in records]


def fetch_category_products() -> dict[str, dict]:
    products = {}
    offset = 0
    while True:
        data = api_get(
            "products",
            {
                "categoryId": CATEGORY_ID,
                "includeChildren": "true",
                "totalResults": "true",
                "limit": PAGE_SIZE,
                "offset": offset,
            },
        )
        batch = data.get("items", [])
        products.update({p["id"]: p for p in batch})
        offset += len(batch)
        if not batch or offset >= data.get("totalResults", 0):
            return products


def fetch_stock(product_ids: list[str]) -> dict[str, dict]:
    stock = {}
    for i in range(0, len(product_ids), STOCK_BATCH):
        chunk = product_ids[i : i + STOCK_BATCH]
        data = api_get("stockStatus", {"products": ",".join(chunk)})
        for item in data.get("items", []):
            pid = next(iter(item.get("productSkuInventoryStatus", {})), None)
            if pid:
                stock[pid] = {
                    "stockStatus": item.get("stockStatus"),
                    "stockLevel": item["productSkuInventoryStatus"][pid],
                }
    return stock


def source_key(product_id: str, date: str) -> str:
    return f"{S3_PREFIX}/product-source-json/{date}/{product_id}.json"


def manifest_entry(product: dict, position: int, date: str) -> dict:
    key = source_key(product["id"], date)
    return {
        "link": f"{BASE_URL}{product['route']}",
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= FIRST_PAGE_LIMIT else "no",
        "platform": "dubaidutyfree",
        "region": REGION,
        "date": date,
        "input_type": "json",
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
    }


def main() -> None:
    args = parse_args()
    listing_ids = fetch_listing_ids()
    if not listing_ids:
        raise RuntimeError("[dubaidutyfree] listing search returned 0 products (stale SEARCH_DIMENSION_ID?)")
    by_id = fetch_category_products()
    # a listed id missing from the category call would be dropped silently — fetch it directly
    products = [by_id.get(pid) or api_get(f"products/{pid}", {}) for pid in listing_ids]
    log.info(f"[dubaidutyfree] Listing has {len(products)} products ({len(by_id)} in category API)")

    stock = fetch_stock([p["id"] for p in products])
    log.info(f"[dubaidutyfree] Stock status for {len(stock)}/{len(products)} products")

    s3 = S3Client()
    manifest = []
    for position, product in enumerate(products, start=1):
        entry = manifest_entry(product, position, args.date)
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], {**product, **stock.get(product["id"], {})})
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-source-json/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(
        f"[dubaidutyfree] Uploaded source manifest with {len(manifest)} products → "
        f"s3://{S3_BUCKET}/{manifest_key}"
    )


if __name__ == "__main__":
    main()
