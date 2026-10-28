"""
Scraper for mmihomedelivery.ae
"""

import argparse
import asyncio
import html
import sys
import os
import re
import time
from datetime import datetime, UTC
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, Timeout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from scraper import Scraper
from s3 import S3Client
from logger import get_logger

log = get_logger(__name__, log_file=settings.LOG_FILE)

BASE_URL = "https://www.mmihomedelivery.ae/shop/beer-cider"
S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/mmihomedelivery-dubai"
SITE_BASE = "https://www.mmihomedelivery.ae"
API_URL = "https://api.mmiprod.retter.io/o9pki8qf/CALL/ProductManager/searchProducts/default"
PRODUCT_SELECTOR = "body div.w-full.mx-auto > div.w-full > div.mx-auto"
PAGE_TIMEOUT = 30000
PAGE_SIZE = 100
MAX_RETRIES = 5
RETRY_DELAY = 10
PRODUCT_CONTEXT_BY_URL = {}

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en;q=0.5",
    "channel-id": "mmiDubai",
    "content-type": "application/json",
    "origin": SITE_BASE,
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

PARAMS = {"__culture": "en-us"}


def html_s3_key(url: str, date: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] or "product"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") or "product"
    return f"{S3_PREFIX}/product-html/{date}/{slug}.html"


def manifest_s3_key(date: str) -> str:
    return f"{S3_PREFIX}/product-html/{date}/manifest.json"


def product_context_html(url: str) -> str:
    context = PRODUCT_CONTEXT_BY_URL.get(url, {})

    if not context:
        return ""

    rows = []
    for label, value in context.items():
        if value:
            rows.append(f"<p><strong>{html.escape(label)}:</strong> {html.escape(str(value))}</p>")

    if not rows:
        return ""

    return "<section data-source-context='api-category-context'>" + "".join(rows) + "</section>"


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


def fetch_product_page(from_offset: int) -> dict:
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


def fetch_product_entries(date: str) -> list[dict]:
    first_page = fetch_product_page(0)
    total = first_page.get("total", 0)
    products = first_page.get("result", [])

    log.info(f"API reported {total} beer/cider products")

    for offset in range(PAGE_SIZE, total, PAGE_SIZE):
        page = fetch_product_page(offset)
        products.extend(page.get("result", []))

    entries = []
    skipped_draught = 0
    for item in products:
        product = item.get("product", {})
        slug = product.get("slug", {}).get("value")
        if slug:
            title = localized_value(product.get("title"))
            url = f"{SITE_BASE}/product/{slug}"
            if is_draught_product(slug, title):
                skipped_draught += 1
                log.warning(f"[SKIP] Draught product: {slug}")
                continue

            categories = product.get("categories", [])
            context = {
                "category": "Beer & Cider",
                "type_hint": product_type_from_categories(categories),
            }
            PRODUCT_CONTEXT_BY_URL[url] = context
            entries.append({
                "link": url,
                "position": len(entries) + 1,
                "features_in_top10": "yes" if len(entries) < 10 else "no",
                "features_on_first_page": "yes" if len(entries) < 25 else "no",
                "platform": "mmihomedelivery",
                "region": "Dubai",
                "date": date,
                "product_html_s3_key": html_s3_key(url, date),
                "product_html_s3_uri": f"s3://{S3_BUCKET}/{html_s3_key(url, date)}",
                "context": context,
            })

    seen = set()
    deduped_entries = []
    for entry in entries:
        if entry["link"] in seen:
            continue
        seen.add(entry["link"])
        deduped_entries.append(entry)

    log.info(f"Collected {len(deduped_entries)} product URLs from API")
    log.info(f"Skipped {skipped_draught} draught products")
    return deduped_entries



# ------------------------------------------------
# detail page parser
# ------------------------------------------------

async def collect_product_html(page):
    if is_draught_product(page.url):
        log.warning(f"[SKIP] Draught product: {page.url}")
        return {"_skip": True, "link": page.url}

    await page.wait_for_selector(
        PRODUCT_SELECTOR,
        timeout=PAGE_TIMEOUT
    )

    product_html = await page.query_selector(
        PRODUCT_SELECTOR
    )

    if not product_html:
        raise ValueError(f"Product container not found: {page.url}")

    html_content = product_context_html(page.url) + await product_html.inner_html()
    return {
        "link": page.url,
        "product_html": html_content,
    }


# ------------------------------------------------
# main
# ------------------------------------------------

async def collect_html(date: str) -> list[dict]:
    entries = fetch_product_entries(date)

    async with Scraper(headless=True, block_images=True, block_fonts=True) as scraper:
        log.info(f"Collecting HTML for {len(entries)} products")

        tasks = [
            {
                "url": entry["link"],
                "fn": collect_product_html,
                "opts": {"wait_until": "commit", "timeout": PAGE_TIMEOUT},
            }
            for entry in entries
        ]

        results = await scraper.scrape_many(tasks, concurrency=settings.CONCURRENCY)

    s3 = S3Client()
    entry_by_url = {entry["link"]: entry for entry in entries}
    manifest = []

    for result in results:
        if "data" not in result:
            log.warning(f"[SKIP] HTML collection failed for {result.get('url')}: {result.get('error')}")
            continue

        data = result["data"]
        if data.get("_skip"):
            continue

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


async def main(date: str):
    await collect_html(date)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect MMI Dubai product HTML and upload an S3 manifest."
    )
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.date))
