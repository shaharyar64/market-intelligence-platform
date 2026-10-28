"""
Raw HTML collector for nhscbahrain.com.

Collects product-detail HTML into S3 and uploads a manifest.
LLM extraction is handled separately by extract_from_html_manifests.py.
"""

import argparse
import asyncio
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

BASE_URL = "https://www.nhscbahrain.com/Beers-nhsc-bahrain"
S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/nhsc"
PRODUCT_SELECTOR = "#product-area"
LISTING_SELECTOR = "div.title > a"
PAGE_TIMEOUT = 30000


def html_s3_key(url: str, date: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] or "product"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") or "product"
    return f"{S3_PREFIX}/product-html/{date}/{slug}.html"


def manifest_s3_key(date: str) -> str:
    return f"{S3_PREFIX}/product-html/{date}/manifest.json"


async def collect_product_html(page):
    await page.wait_for_selector(PRODUCT_SELECTOR, timeout=PAGE_TIMEOUT)

    product_html = await page.query_selector(PRODUCT_SELECTOR)

    if not product_html:
        raise ValueError(f"Product container not found: {page.url}")

    return {
        "link": page.url,
        "product_html": await product_html.inner_html(),
    }


async def parse_listing(page):
    pop_btn = await page.query_selector(".foot-pop > a")

    if pop_btn:
        await pop_btn.click()

    await page.wait_for_selector(LISTING_SELECTOR, timeout=PAGE_TIMEOUT)

    elements = await page.query_selector_all(LISTING_SELECTOR)
    hrefs = []

    for el in elements:
        href = await el.get_attribute("href")
        if href:
            hrefs.append(href)

    hrefs = list(dict.fromkeys(hrefs))
    log.info(f"Found {len(hrefs)} products")

    next_btn = await page.query_selector(".pagination > li:nth-last-child(2) > a")
    next_url = None

    if next_btn:
        text = (await next_btn.inner_text()).strip()

        if text == ">":
            next_url = await next_btn.get_attribute("href")

    return {"hrefs": hrefs, "next_url": next_url}


async def collect_hrefs(scraper: Scraper) -> list[str]:
    all_hrefs = []
    current_url = BASE_URL
    page_number = 1

    while current_url:
        log.info(f"Scraping listing page {page_number}: {current_url}")

        result = await scraper.scrape(
            current_url,
            parse_listing,
            wait_until="load",
            timeout=60000,
        )

        all_hrefs.extend(result["hrefs"])
        current_url = result["next_url"]
        page_number += 1

    all_hrefs = list(dict.fromkeys(all_hrefs))
    log.info(f"Total product URLs collected: {len(all_hrefs)}")
    return all_hrefs


def manifest_entry(url: str, position: int, date: str) -> dict:
    html_key = html_s3_key(url, date)

    return {
        "link": url,
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= 16 else "no",
        "platform": "nhsc",
        "region": "Bahrain",
        "date": date,
        "input_type": "html",
        "product_html_s3_key": html_key,
        "product_html_s3_uri": f"s3://{S3_BUCKET}/{html_key}",
    }


async def collect_html(date: str) -> list[dict]:
    async with Scraper(
        headless=True,
        storage_state="sessions/nhsc.json",
        block_images=True,
        block_fonts=True,
    ) as scraper:
        hrefs = await collect_hrefs(scraper)
        entries = [
            manifest_entry(href, position, date)
            for position, href in enumerate(hrefs, start=1)
        ]

        tasks = [
            {
                "url": entry["link"],
                "fn": collect_product_html,
                "opts": {"wait_until": "commit", "timeout": PAGE_TIMEOUT},
            }
            for entry in entries
        ]

        log.info(f"Collecting HTML for {len(entries)} products")
        results = await scraper.scrape_many(tasks, concurrency=settings.CONCURRENCY)

    s3 = S3Client()
    entry_by_url = {entry["link"]: entry for entry in entries}
    manifest = []

    for result in results:
        if "data" not in result:
            log.warning(f"[SKIP] HTML collection failed for {result.get('url')}: {result.get('error')}")
            continue

        data = result["data"]
        entry = entry_by_url.get(data["link"])

        if not entry:
            log.warning(f"[SKIP] No manifest entry for {data['link']}")
            continue

        s3.s3.put_object(
            Bucket=S3_BUCKET,
            Key=entry["product_html_s3_key"],
            Body=data["product_html"].encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )

        manifest.append(entry)
        log.info(f"[HTML] Uploaded {entry['product_html_s3_uri']}")

    manifest_key = manifest_s3_key(date)
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded HTML manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    return manifest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect NHSC product HTML and upload an S3 manifest."
    )
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(args.date))
