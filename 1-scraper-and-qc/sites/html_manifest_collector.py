import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import settings
from logger import get_logger
from s3 import S3Client
from scraper import Scraper

log = get_logger(__name__, log_file=settings.LOG_FILE)

S3_BUCKET = "raw-data-prod"
PAGE_TIMEOUT = 30000


def proxy_from_env() -> dict | None:
    """Reads PROXY_SERVER/PROXY_USERNAME/PROXY_PASSWORD for sites that need to
    route around datacenter-IP blocking. Returns None if PROXY_SERVER is unset."""
    server = os.getenv("PROXY_SERVER")
    if not server:
        return None
    proxy = {"server": server}
    username = os.getenv("PROXY_USERNAME")
    password = os.getenv("PROXY_PASSWORD")
    if username:
        proxy["username"] = username
    if password:
        proxy["password"] = password
    return proxy


@dataclass
class HtmlCollectorConfig:
    site_name: str
    base_url: str
    s3_prefix: str
    platform: str
    region: str
    detail_selector: str
    listing_selector: str
    first_page_limit: int
    extra_detail_selectors: tuple[str, ...] = ()
    remove_selectors: tuple[str, ...] = ()
    next_selector: str = ""
    next_text: str = ""
    href_prefix: str = ""
    headless: bool = True
    storage_state: str = ""
    popup_selector: str = ""
    listing_wait_until: str = "load"
    listing_selector_state: str = "visible"
    listing_selector_timeout: int = PAGE_TIMEOUT
    detail_wait_until: str = "commit"
    block_images: bool = True
    block_fonts: bool = True
    load_more_selector: str = ""
    load_more_max_clicks: int = 25
    load_more_wait_ms: int = 1500
    listing_remove_selectors: tuple[str, ...] = ()
    proxy: dict | None = None
    user_agent: str | None = None


@dataclass
class CardHtmlCollectorConfig:
    site_name: str
    base_url: str
    s3_prefix: str
    platform: str
    region: str
    card_selector: str
    first_page_limit: int
    next_selector: str = ""
    next_text: str = ""
    headless: bool = True
    storage_state: str = ""
    popup_selector: str = ""
    listing_wait_until: str = "load"
    block_images: bool = True
    block_fonts: bool = True


def html_s3_key(config: HtmlCollectorConfig, url: str, date: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] or "product"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") or "product"
    return f"{config.s3_prefix}/product-html/{date}/{slug}.html"


def card_html_s3_key(config: CardHtmlCollectorConfig, position: int, date: str) -> str:
    return f"{config.s3_prefix}/product-html/{date}/product-{position:04d}.html"


def manifest_s3_key(config: HtmlCollectorConfig, date: str) -> str:
    return f"{config.s3_prefix}/product-html/{date}/manifest.json"


def parse_args():
    parser = argparse.ArgumentParser(description="Collect product HTML and upload an S3 manifest.")
    parser.add_argument(
        "--date",
        default=datetime.now(UTC).strftime("%Y-%m-%d"),
        help="Run date used in S3 keys. Default: today UTC.",
    )
    return parser.parse_args()


def normalize_url(config: HtmlCollectorConfig, href: str, current_url: str) -> str:
    if href.startswith("http"):
        return href
    href_prefix = getattr(config, "href_prefix", "")
    if href_prefix:
        return f"{href_prefix}{href}"
    return urljoin(current_url, href)


def make_parse_listing(config: HtmlCollectorConfig):
    async def parse_listing(page):
        if config.popup_selector:
            pop_btn = await page.query_selector(config.popup_selector)
            if pop_btn:
                await pop_btn.click()

        for selector in config.listing_remove_selectors:
            for element in await page.query_selector_all(selector):
                await element.evaluate("(node) => node.remove()")

        await page.wait_for_selector(
            config.listing_selector, timeout=config.listing_selector_timeout, state=config.listing_selector_state
        )

        if config.load_more_selector:
            for click_count in range(config.load_more_max_clicks):
                for selector in config.listing_remove_selectors:
                    for element in await page.query_selector_all(selector):
                        await element.evaluate("(node) => node.remove()")

                before_count = len(await page.query_selector_all(config.listing_selector))
                load_more = await page.query_selector(config.load_more_selector)
                if not load_more:
                    break

                is_visible = await load_more.is_visible()
                is_enabled = await load_more.is_enabled()
                if not is_visible or not is_enabled:
                    break

                await load_more.scroll_into_view_if_needed()
                await load_more.click()
                await page.wait_for_timeout(config.load_more_wait_ms)

                after_count = len(await page.query_selector_all(config.listing_selector))
                log.info(
                    f"[{config.site_name}] Load more click {click_count + 1}: "
                    f"{before_count} → {after_count} products"
                )

                if after_count <= before_count:
                    break

        elements = await page.query_selector_all(config.listing_selector)
        hrefs = []

        for el in elements:
            href = await el.get_attribute("href")
            if href:
                hrefs.append(normalize_url(config, href, page.url))

        hrefs = list(dict.fromkeys(hrefs))
        log.info(f"[{config.site_name}] Found {len(hrefs)} products")

        next_url = None
        if config.next_selector:
            next_btn = await page.query_selector(config.next_selector)

            if next_btn:
                if config.next_text:
                    text = (await next_btn.inner_text()).strip()
                    if text != config.next_text:
                        return {"hrefs": hrefs, "next_url": None}

                next_href = await next_btn.get_attribute("href")
                if next_href:
                    next_url = normalize_url(config, next_href, page.url)

        return {"hrefs": hrefs, "next_url": next_url}

    return parse_listing


def make_collect_product_html(config: HtmlCollectorConfig):
    async def collect_product_html(page):
        for selector in config.remove_selectors:
            for element in await page.query_selector_all(selector):
                await element.evaluate("(node) => node.remove()")

        await page.wait_for_selector(config.detail_selector, timeout=PAGE_TIMEOUT)
        product_html = await page.query_selector(config.detail_selector)

        if not product_html:
            raise ValueError(f"Product container not found: {page.url}")

        html_parts = [await product_html.inner_html()]

        for selector in config.extra_detail_selectors:
            extra = await page.query_selector(selector)
            if extra:
                html_parts.append(await extra.inner_html())

        product_html_text = "\n".join(html_parts)
        if any(selector in config.remove_selectors for selector in (".related", ".related.products")):
            product_html_text = re.split(
                r"<(?:section|div)[^>]+class=[\"'][^\"']*\brelated\b[^\"']*[\"'][^>]*>",
                product_html_text,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]

        return {
            "link": page.url,
            "product_html": product_html_text,
        }

    return collect_product_html


async def collect_hrefs(config: HtmlCollectorConfig, scraper: Scraper) -> list[str]:
    all_hrefs = []
    current_url = config.base_url
    visited_urls = set()
    page_number = 1
    parse_listing = make_parse_listing(config)

    while current_url:
        if current_url in visited_urls:
            # Some sites' pagination doesn't disable/omit the "next" link on
            # the last page — it wraps back to an earlier page instead. Left
            # unguarded this loops forever, re-scraping the same pages.
            log.warning(
                f"[{config.site_name}] Pagination loop detected — \"next\" link "
                f"revisits {current_url!r} (page {page_number}). Stopping here."
            )
            break
        visited_urls.add(current_url)

        log.info(f"[{config.site_name}] Scraping listing page {page_number}: {current_url}")

        result = await scraper.scrape(
            current_url,
            parse_listing,
            wait_until=config.listing_wait_until,
            timeout=60000,
        )

        all_hrefs.extend(result["hrefs"])
        current_url = result.get("next_url")
        page_number += 1

    all_hrefs = list(dict.fromkeys(all_hrefs))
    log.info(f"[{config.site_name}] Total product URLs collected: {len(all_hrefs)}")
    return all_hrefs


def manifest_entry(config: HtmlCollectorConfig, url: str, position: int, date: str) -> dict:
    html_key = html_s3_key(config, url, date)

    return {
        "link": url,
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= config.first_page_limit else "no",
        "platform": config.platform,
        "region": config.region,
        "date": date,
        "input_type": "html",
        "product_html_s3_key": html_key,
        "product_html_s3_uri": f"s3://{S3_BUCKET}/{html_key}",
    }


def card_manifest_entry(config: CardHtmlCollectorConfig, position: int, date: str) -> dict:
    html_key = card_html_s3_key(config, position, date)

    return {
        "link": f"{config.base_url}#product-{position}",
        "position": position,
        "features_in_top10": "yes" if position <= 10 else "no",
        "features_on_first_page": "yes" if position <= config.first_page_limit else "no",
        "platform": config.platform,
        "region": config.region,
        "date": date,
        "input_type": "html",
        "product_html_s3_key": html_key,
        "product_html_s3_uri": f"s3://{S3_BUCKET}/{html_key}",
    }


async def collect_html(config: HtmlCollectorConfig, date: str) -> list[dict]:
    async with Scraper(
        headless=config.headless,
        storage_state=config.storage_state or None,
        block_images=config.block_images,
        block_fonts=config.block_fonts,
        proxy=config.proxy,
        user_agent=config.user_agent,
    ) as scraper:
        hrefs = await collect_hrefs(config, scraper)
        entries = [
            manifest_entry(config, href, position, date)
            for position, href in enumerate(hrefs, start=1)
        ]
        collect_product_html = make_collect_product_html(config)
        tasks = [
            {
                "url": entry["link"],
                "fn": collect_product_html,
                "opts": {"wait_until": config.detail_wait_until, "timeout": PAGE_TIMEOUT},
            }
            for entry in entries
        ]

        log.info(f"[{config.site_name}] Collecting HTML for {len(entries)} products")
        results = await scraper.scrape_many(tasks, concurrency=settings.CONCURRENCY)

    s3 = S3Client()
    entry_by_url = {entry["link"]: entry for entry in entries}
    manifest = []

    for result in results:
        if "data" not in result:
            log.warning(f"[{config.site_name}] [SKIP] HTML collection failed for {result.get('url')}: {result.get('error')}")
            continue

        data = result["data"]
        entry = entry_by_url.get(data["link"])

        if not entry:
            log.warning(f"[{config.site_name}] [SKIP] No manifest entry for {data['link']}")
            continue

        s3.s3.put_object(
            Bucket=S3_BUCKET,
            Key=entry["product_html_s3_key"],
            Body=data["product_html"].encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )

        manifest.append(entry)
        log.info(f"[{config.site_name}] [HTML] Uploaded {entry['product_html_s3_uri']}")

    manifest_key = manifest_s3_key(config, date)
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"[{config.site_name}] Uploaded HTML manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    return manifest


async def collect_card_html(config: CardHtmlCollectorConfig, date: str) -> list[dict]:
    cards = []

    async with Scraper(
        headless=config.headless,
        storage_state=config.storage_state or None,
        block_images=config.block_images,
        block_fonts=config.block_fonts,
    ) as scraper:
        page = await scraper.new_page()
        current_url = config.base_url
        page_number = 1

        while current_url:
            log.info(f"[{config.site_name}] Scraping listing page {page_number}: {current_url}")
            await page.goto(current_url, wait_until=config.listing_wait_until, timeout=60000)

            if config.popup_selector:
                pop_btn = await page.query_selector(config.popup_selector)
                if pop_btn:
                    await pop_btn.click()

            await page.wait_for_selector(config.card_selector, timeout=PAGE_TIMEOUT)
            elements = await page.query_selector_all(config.card_selector)
            log.info(f"[{config.site_name}] Found {len(elements)} product cards")

            for el in elements:
                cards.append(await el.inner_html())

            next_url = None
            if config.next_selector:
                next_btn = await page.query_selector(config.next_selector)
                if next_btn:
                    if config.next_text:
                        text = (await next_btn.inner_text()).strip()
                        if text != config.next_text:
                            break

                    next_href = await next_btn.get_attribute("href")
                    if next_href:
                        next_url = normalize_url(config, next_href, page.url)

            current_url = next_url
            page_number += 1

        await page.close()

    s3 = S3Client()
    manifest = []

    for position, product_html in enumerate(cards, start=1):
        entry = card_manifest_entry(config, position, date)
        s3.s3.put_object(
            Bucket=S3_BUCKET,
            Key=entry["product_html_s3_key"],
            Body=product_html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        manifest.append(entry)
        log.info(f"[{config.site_name}] [HTML] Uploaded {entry['product_html_s3_uri']}")

    manifest_key = manifest_s3_key(config, date)
    s3.put_json(S3_BUCKET, manifest_key, manifest)
    log.success(f"[{config.site_name}] Uploaded HTML manifest with {len(manifest)} products → s3://{S3_BUCKET}/{manifest_key}")
    return manifest
