import argparse
import asyncio
import json
import os
import re
import ssl
import sys
from datetime import UTC, datetime

import aiohttp
import certifi

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/spinneysauh"
URL = "https://api.mmiprod.retter.io/o9pki8qf/CALL/ProductManager/searchProducts/default"
PAGE_SIZE = 12

HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.6",
    "channel-id": "spinneys",
    "origin": "https://www.spinneysauh.com",
    "user-agent": "Mozilla/5.0",
}

PARAMS = {"__culture": "en-us"}


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Spinneys AUH product source JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    value = value or "product"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "product"


def product_link(product: dict) -> str:
    slug = product.get("slug", {}).get("value") or product.get("slug") or slugify(product.get("name", "product"))
    return f"https://www.spinneysauh.com/product/{slug}"


def source_key(product: dict, position: int, date: str) -> str:
    slug = product.get("slug", {}).get("value") or f"product-{position:04d}"
    return f"{S3_PREFIX}/product-source-json/{date}/{slugify(slug)}.json"


def slim_product(product: dict) -> dict:
    return {
        "name": product.get("name", {}).get("value") if isinstance(product.get("name"), dict) else product.get("name", ""),
        "slug": product.get("slug", {}).get("value") if isinstance(product.get("slug"), dict) else product.get("slug", ""),
        "brand": product.get("brand", {}).get("value") if isinstance(product.get("brand"), dict) else product.get("brand", ""),
        "price": product.get("price"),
        "salePrice": product.get("salePrice"),
        "image": product.get("image"),
        "stock": product.get("stock"),
        "volume": product.get("volume"),
        "packSize": product.get("packSize"),
    }


def product_text(product: dict) -> str:
    values = [
        product.get("name"),
        product.get("title"),
        product.get("slug"),
        product.get("description"),
        product.get("webBrand"),
        product.get("erpBrandName"),
        product.get("webSize"),
        product.get("erpSize"),
    ]
    return json.dumps(values, ensure_ascii=False).lower()


def is_out_of_scope_product(product: dict) -> bool:
    text = product_text(product)
    patterns = [
        r"\bhome\s+draught\b",
        r"\bdraught\s+system\b",
        r"\bdraught\s+tap\b",
        r"\btap\s+system\b",
        r"\bblade\s+home\b",
        r"\bblade\b.*\bsystem\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


async def fetch_page(session: aiohttp.ClientSession, start: int) -> dict:
    payload = {
        "from": start,
        "pageSize": PAGE_SIZE,
        "categories": ["beerCider"],
        "sorting": "-stock",
    }

    async with session.post(URL, json=payload, headers=HEADERS, params=PARAMS) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_products() -> list[dict]:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        first_page = await fetch_page(session, 0)
        total = first_page.get("total", 0)
        tasks = [
            fetch_page(session, start)
            for start in range(PAGE_SIZE, total, PAGE_SIZE)
        ]
        pages = await asyncio.gather(*tasks)

    products = first_page.get("result", [])
    for page in pages:
        products.extend(page.get("result", []))

    log.info(f"Fetched {len(products)} products")
    return products


def manifest_entry(raw_item: dict, position: int, date: str) -> dict:
    product = raw_item.get("product", raw_item)
    key = source_key(product, position, date)

    return {
        "link": product_link(product),
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= PAGE_SIZE else "no",
        "platform": "spinneysauh",
        "region": "Abu Dhabi",
        "date": date,
        "input_type": "json",
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
        "extraction_payload": slim_product(product),
    }


async def main():
    args = parse_args()
    raw_products = await fetch_products()
    s3 = S3Client()
    manifest = []
    skipped = 0

    for raw_item in raw_products:
        product = raw_item.get("product", raw_item)
        if is_out_of_scope_product(product):
            skipped += 1
            log.warning(f"[SKIP] Out-of-scope draught system: {product_link(product)}")
            continue

        position = len(manifest) + 1
        entry = manifest_entry(raw_item, position, args.date)
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], raw_item)
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-source-json/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded source manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    log.info(f"Skipped out-of-scope products: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
