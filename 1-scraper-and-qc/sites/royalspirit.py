import argparse
import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client
from scraper import Scraper

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/royalspirit"
BASE_URL = "https://royalspirit.ae/collections/beer"


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Royal Spirit product source JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def product_slug(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or "product"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") or "product"


async def extract_product_json(page):
    scripts = await page.query_selector_all('script[type="application/ld+json"]')

    for script in scripts:
        try:
            data = json.loads(await script.inner_text())
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict) and "hasVariant" in data:
            return {"link": page.url, "product_source": data}

    raise ValueError(f"Product JSON-LD not found: {page.url}")


async def parse_listing(page):
    await page.wait_for_selector(".product-column > product-card a.product-card__media-link", timeout=10000)
    elements = await page.query_selector_all(".product-column > product-card a.product-card__media-link")
    hrefs = []

    for el in elements:
        href = await el.get_attribute("href")
        if href:
            hrefs.append(f"https://royalspirit.ae{href}")

    next_url = None
    next_btn = await page.query_selector("a.pagination__item--next")
    if next_btn:
        href = await next_btn.get_attribute("href")
        if href:
            next_url = href if href.startswith("http") else f"https://royalspirit.ae{href}"

    log.info(f"Found {len(hrefs)} products")
    return {"hrefs": hrefs, "next_url": next_url}


def manifest_entry(url: str, position: int, date: str) -> dict:
    key = f"{S3_PREFIX}/product-source-json/{date}/{product_slug(url)}.json"
    return {
        "link": url,
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= 36 else "no",
        "platform": "royalspirit",
        "region": "Abu Dhabi",
        "date": date,
        "input_type": "json",
        "product_source_s3_key": key,
        "product_source_s3_uri": f"s3://{S3_BUCKET}/{key}",
    }


async def main():
    args = parse_args()
    all_hrefs = []

    async with Scraper(headless=True, storage_state="sessions/royalspirit.json") as scraper:
        current_url = BASE_URL

        while current_url:
            result = await scraper.scrape(current_url, parse_listing, wait_until="load")
            all_hrefs.extend(result["hrefs"])
            current_url = result["next_url"]

        all_hrefs = list(dict.fromkeys(all_hrefs))
        log.info(f"Total products collected: {len(all_hrefs)}")

        tasks = [{"url": href, "fn": extract_product_json} for href in all_hrefs]
        results = await scraper.scrape_many(tasks, concurrency=settings.CONCURRENCY)

    s3 = S3Client()
    entries = {
        entry["link"]: entry
        for entry in (manifest_entry(url, position, args.date) for position, url in enumerate(all_hrefs, start=1))
    }
    manifest = []

    for result in results:
        if "data" not in result:
            log.warning(f"[SKIP] Source collection failed for {result.get('url')}: {result.get('error')}")
            continue

        entry = entries[result["data"]["link"]]
        s3.put_json(S3_BUCKET, entry["product_source_s3_key"], result["data"]["product_source"])
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-source-json/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded source manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")


if __name__ == "__main__":
    asyncio.run(main())
