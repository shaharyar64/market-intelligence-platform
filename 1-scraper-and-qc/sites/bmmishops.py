import argparse
import asyncio
import json
import os
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
S3_PREFIX = "beer-pricing/bmmishops"
URL = "https://www.bmmishops.com/plp"
PAGE_SIZE = 12
PLATFORM = "bmmishops"
CURRENCY = "BHD"
CURRENCY_MULTIPLIER = 2.648

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-GB,en;q=0.5",
    "authorization": "",
    "content-type": "application/json",
    "referer": "https://www.bmmishops.com/beers-ciders.html",
    "user-agent": "Mozilla/5.0",
}

COOKIES = {
    "PHPSESSID": "9e86d98aa2d141b5cf4cad3d9ee95232",
    "private_content_version": "8015d1dda55244954b39f6aa136fe46d",
}

PARAMS = {
    "website_id": 9,
    "source_code": "BWO",
    "delivery_type": "Standard Mode",
    "category_id": 32,
    "page_size": PAGE_SIZE,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Collect BMMI Shops product source JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def slim_product(product: dict) -> dict:
    url_key = product.get("url_key", "")
    link = f"https://www.bmmishops.com/{url_key}.html"

    original = None
    try:
        original = product["price_range"]["minimum_price"]["regular_price"]["value"]
    except (KeyError, TypeError):
        pass

    discounted = product.get("special_price")
    image_url = product.get("small_image", {}).get("url", "") or product.get("thumbnail", {}).get("url", "")

    return {
        "name": product.get("name", ""),
        "url": link,
        "price": round(float(original), 3) if original is not None else None,
        "special_price": round(float(discounted), 3) if discounted is not None else None,
        "image_url": image_url,
    }


async def fetch_page(session: aiohttp.ClientSession, page: int, ssl_context) -> dict:
    params = PARAMS.copy()
    params["page"] = page

    async with session.get(URL, headers=HEADERS, params=params, cookies=COOKIES, ssl=ssl_context) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_products() -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=30)
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with aiohttp.ClientSession(timeout=timeout) as session:
        first_page = await fetch_page(session, 1, ssl_context)
        total_pages = first_page["data"]["products"]["page_info"]["total_pages"]
        products = first_page["data"]["products"]["items"]
        log.info(f"Page 1/{total_pages}: Got {len(products)} products")

        for page in range(2, total_pages + 1):
            data = await fetch_page(session, page, ssl_context)
            items = data["data"]["products"]["items"]
            products.extend(items)
            log.info(f"Page {page}/{total_pages}: Got {len(items)} products")
            await asyncio.sleep(1)

    log.info(f"Total fetched: {len(products)} products")
    return products


def source_key(product: dict, position: int, date: str) -> str:
    slug = product.get("url_key") or f"product-{position:04d}"
    return f"{S3_PREFIX}/product-source-json/{date}/{slug}.json"


def manifest_entry(product: dict, position: int, date: str) -> dict:
    slim = slim_product(product)
    original = slim.get("price")
    discounted = slim.get("special_price") or original
    key = source_key(product, position, date)

    return {
        "link": slim["url"],
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= PAGE_SIZE else "no",
        "platform": PLATFORM,
        "region": "Bahrain",
        "date": date,
        "input_type": "json",
        "currency": CURRENCY,
        "image_link": slim["image_url"],
        "postprocess": "price_override",
        "original_price_local": original,
        "discounted_price_local": discounted,
        "currency_multiplier": CURRENCY_MULTIPLIER,
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
        "extraction_payload": slim,
    }


async def main():
    args = parse_args()
    raw_products = await fetch_products()
    s3 = S3Client()
    manifest = []

    for position, product in enumerate(raw_products, start=1):
        entry = manifest_entry(product, position, args.date)
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], product)
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-source-json/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded source manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")


if __name__ == "__main__":
    asyncio.run(main())
