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

S3_BUCKET = "raw-data-prod"
S3_PREFIX = "beer-pricing/centaurusint"
BASE_URL = "https://centaurusint.net/beers/c-57.html"


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Centaurus product HTML.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def product_slug(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or "product"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") or "product"


def html_key(url: str, date: str) -> str:
    return f"{S3_PREFIX}/product-html/{date}/{product_slug(url)}.html"


def product_family_terms(url: str) -> list[str]:
    slug = urlparse(url).path.strip("/").split("/")[0]
    tokens = re.findall(r"[a-zA-Z]+", slug.lower())
    stop_words = {
        "beer",
        "beers",
        "btl",
        "bottle",
        "bottles",
        "can",
        "cans",
        "cl",
        "ml",
        "case",
        "pack",
        "promo",
        "x",
    }
    return [token for token in tokens if token not in stop_words and len(token) > 2]


async def collect_product_html(page):
    await page.wait_for_selector("div.product-detail", timeout=10000)
    try:
        await page.wait_for_selector(
            "div.product-detail > div.row.mb-50, div.product-cart-wrap",
            timeout=10000,
        )
    except Exception:
        pass
    terms = product_family_terms(page.url)

    html_content = await page.evaluate(
        """({ terms }) => {
            const cleanClone = (node) => {
                const clone = node.cloneNode(true);
                clone.querySelectorAll(
                    '.box-acc, .float-acc, .price-btn-box-acc, .related-products, .col-lg-4, script, style'
                ).forEach((el) => el.remove());
                return clone.outerHTML;
            };

            const detail = document.querySelector('div.product-detail');
            const detailRow = document.querySelector('div.product-detail > div.row.mb-50');
            if (detailRow) {
                return cleanClone(detailRow);
            }

            const titleNodes = Array.from(document.querySelectorAll('h1.title-detail, h2.title-detail'));
            const familySections = [];
            titleNodes.forEach((titleNode) => {
                const text = (titleNode.innerText || '').toLowerCase();
                const isFamily = terms.length === 0 || terms.some((term) => text.includes(term));
                if (!isFamily) return;

                const section = titleNode.closest('.col-lg-4') || titleNode.closest('.detail-info');
                if (section && !familySections.includes(section)) {
                    familySections.push(section);
                }
            });

            if (familySections.length) {
                return familySections.map(cleanClone).join('\\n\\n');
            }

            const cards = Array.from(document.querySelectorAll('div.product-cart-wrap'));
            const familyCards = cards.filter((card) => {
                const text = [
                    card.innerText || '',
                    card.querySelector('a')?.href || '',
                    card.querySelector('img')?.alt || '',
                    card.querySelector('img')?.src || '',
                ].join(' ').toLowerCase();

                return terms.length === 0 || terms.some((term) => text.includes(term));
            });

            if (familyCards.length) {
                return familyCards.map(cleanClone).join('\\n\\n');
            }

            if (!terms.length && cards.length) {
                return cards.map(cleanClone).join('\\n\\n');
            }

            return detail ? cleanClone(detail) : document.body.innerHTML;
        }""",
        {"terms": terms},
    )

    return {"link": page.url, "product_html": html_content}


async def parse_listing(page):
    await page.wait_for_selector("div.product-content-wrap > form > h2 > a", timeout=30000)
    elements = await page.query_selector_all("div.product-content-wrap > form > h2 > a")
    hrefs = [href for el in elements if (href := await el.get_attribute("href"))]

    next_url = None
    next_btn = await page.query_selector("a[rel='next']")
    if next_btn:
        next_url = await next_btn.get_attribute("href")

    log.info(f"Found {len(hrefs)} products")
    return {"hrefs": hrefs, "next_url": next_url}


def manifest_entry(url: str, position: int, date: str) -> dict:
    key = html_key(url, date)
    return {
        "link": url,
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= 20 else "no",
        "platform": "centaurusint",
        "region": "Dubai",
        "date": date,
        "input_type": "html",
        "product_html_s3_key": key,
        "product_html_s3_uri": f"s3://{S3_BUCKET}/{key}",
    }


async def main():
    args = parse_args()
    all_hrefs = []

    async with Scraper(headless=True) as scraper:
        current_url = BASE_URL
        page_number = 1

        while current_url:
            log.info(f"Scraping page {page_number}: {current_url}")
            result = await scraper.scrape(current_url, parse_listing, wait_until="load")
            all_hrefs.extend(result["hrefs"])
            current_url = result["next_url"]
            page_number += 1

        all_hrefs = list(dict.fromkeys(all_hrefs))
        log.info(f"Total products collected: {len(all_hrefs)}")

        tasks = [{"url": href, "fn": collect_product_html} for href in all_hrefs]
        results = await scraper.scrape_many(tasks, concurrency=settings.CONCURRENCY)

    s3 = S3Client()
    entries = {
        entry["link"]: entry
        for entry in (manifest_entry(url, position, args.date) for position, url in enumerate(all_hrefs, start=1))
    }
    manifest = []

    for result in results:
        if "data" not in result:
            log.warning(f"[SKIP] HTML collection failed for {result.get('url')}: {result.get('error')}")
            continue

        entry = entries[result["data"]["link"]]
        s3.s3.put_object(
            Bucket=S3_BUCKET,
            Key=entry["product_html_s3_key"],
            Body=result["data"]["product_html"].encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        manifest.append(entry)

    manifest_key = f"{S3_PREFIX}/product-html/{args.date}/manifest.json"
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"Uploaded HTML manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")


if __name__ == "__main__":
    asyncio.run(main())
