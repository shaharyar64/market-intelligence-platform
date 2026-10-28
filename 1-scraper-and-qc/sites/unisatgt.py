import argparse
import asyncio
import os
import re
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client
from scraper import Scraper

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/unisatgt"
BASE_URL = "https://unisatgt.com/?route=product/product/products&category_id=76"


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Unisat product-card HTML.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def html_key(position: int, date: str) -> str:
    return f"{S3_PREFIX}/product-html/{date}/product-{position:04d}.html"


def manifest_entry(position: int, date: str) -> dict:
    key = html_key(position, date)
    return {
        "link": f"{BASE_URL}#product-{position}",
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= 45 else "no",
        "platform": "unisatgt",
        "region": "Other Emirates",
        "date": date,
        "input_type": "html",
        "product_html_s3_key": key,
        "product_html_s3_uri": f"s3://{S3_BUCKET}/{key}",
    }


def dedupe_cards(cards: list[str]) -> list[str]:
    """The site lists some products twice (a grid card + a differently laid-out
    card). Keep the first. Key = product_id from the card link; the second
    layout has no link, so fall back to its visible text minus the stock label."""
    seen, unique = set(), []
    for card in cards:
        match = re.search(r"product_id=(\d+)", card)
        if match:
            key = match.group(1)
        else:
            text = re.sub(r"<[^>]+>|&nbsp;", " ", card)
            key = re.sub(r"\s+", " ", re.sub(r"out of stock", "", text, flags=re.I)).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(card)
    return unique


async def collect_cards(page) -> list[str]:
    await page.wait_for_selector("article.hf-item", timeout=60000)
    elements = await page.query_selector_all("article.hf-item")
    log.info(f"Found {len(elements)} product cards")
    return [await element.inner_html() for element in elements]


async def main():
    args = parse_args()
    all_cards = []

    async with Scraper(headless=True, storage_state="sessions/unisatgt.json") as scraper:
        page = await scraper.new_page()
        await page.goto(BASE_URL, wait_until="load", timeout=60000)

        page_number = 1
        while True:
            log.info(f"Scraping page {page_number}")
            cards = await collect_cards(page)

            if not cards:
                break

            all_cards.extend(cards)

            next_btn = await page.query_selector("button.pagination_class:has-text('NEXT')")
            if not next_btn:
                break

            disabled = await next_btn.get_attribute("disabled")
            if disabled:
                break

            await next_btn.scroll_into_view_if_needed()
            await next_btn.click()
            await page.wait_for_timeout(2000)
            page_number += 1

        await page.close()

    log.info(f"Collected {len(all_cards)} cards")
    all_cards = dedupe_cards(all_cards)
    log.info(f"{len(all_cards)} cards after dropping repeated product_ids")

    s3 = S3Client()
    manifest = []

    for position, product_html in enumerate(all_cards, start=1):
        entry = manifest_entry(position, args.date)
        s3.s3.put_object(
            Bucket=S3_BUCKET,
            Key=entry["product_html_s3_key"],
            Body=product_html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-html/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded HTML manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")


if __name__ == "__main__":
    asyncio.run(main())
