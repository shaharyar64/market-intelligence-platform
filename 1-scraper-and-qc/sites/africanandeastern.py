import asyncio
import os
import sys
import urllib.request
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from logger import get_logger
from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args

log = get_logger(__name__)

MAX_RETRIES = 3


def _gb_proxy() -> dict | None:
    """Fetch a live GB static proxy from Webshare API.

    africanandeastern.com (Bahrain) blocks non-GB datacenter IPs. The rotating
    endpoint p.webshare.io doesn't support country pinning on this plan, so we
    fetch a GB static IP directly from the proxy list API at startup.
    """
    api_key = os.getenv("WEBSHARE_API_KEY")
    username = os.getenv("PROXY_USERNAME", "").replace("-rotate", "")
    password = os.getenv("PROXY_PASSWORD", "")

    if not api_key or not password:
        log.warning("[africanandeastern] WEBSHARE_API_KEY or PROXY_PASSWORD not set — no proxy")
        return None

    try:
        url = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=100&country_code=GB&valid=true"
        req = urllib.request.Request(url, headers={"Authorization": f"Token {api_key}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        proxies = data.get("results", [])
        if not proxies:
            log.warning("[africanandeastern] No GB proxies found in Webshare account")
            return None
        # Pick the first valid GB proxy
        p = proxies[0]
        server = f"http://{p['proxy_address']}:{p['port']}"
        log.info(f"[africanandeastern] Using GB proxy: {p['proxy_address']}:{p['port']}")
        return {"server": server, "username": username, "password": password}
    except Exception as exc:
        log.warning(f"[africanandeastern] Failed to fetch GB proxy from Webshare: {exc}")
        return None


CONFIG = HtmlCollectorConfig(
    site_name="africanandeastern",
    base_url="https://www.africanandeastern.com/beer",
    s3_prefix="beer-pricing/africanandeastern",
    platform="africanandeastern",
    region="Bahrain",
    detail_selector="#product-area",
    listing_selector="#product-list div.title > a",
    next_selector=".pagination > li:nth-last-child(2) > a",
    next_text=">",
    first_page_limit=20,
    listing_wait_until="domcontentloaded",
    # Previously "networkidle", on the theory that the "Packing:" spec (used
    # for quantity) needed the page to wait out a delayed AJAX call. That
    # theory didn't hold up — the actual cause of the quantity=NA issue was a
    # reCAPTCHA soft-block on the GB proxy IP, unrelated to wait_until timing.
    # Meanwhile "networkidle" has its own failure mode: pages with a
    # persistent background connection (chat widget/tracking beacons) never
    # go fully idle, so goto() itself times out — this is what killed the
    # 2026-08-18 run (hit the 30-minute per-scraper ceiling). "load" avoids
    # that without reopening the disproven AJAX-timing issue.
    detail_wait_until="load",
    proxy=_gb_proxy(),
)


async def collect_html_with_retry(config: HtmlCollectorConfig, date: str) -> list[dict]:
    """Retry collect_html up to MAX_RETRIES times on failure.

    Each retry spawns a new Scraper (new browser process), which opens a fresh
    connection to the proxy — giving a different exit IP. Backoff of 30s between
    attempts gives the server/proxy time to recover.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await collect_html(config, date)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                wait = 30 * attempt
                log.warning(
                    f"[{config.site_name}] Attempt {attempt}/{MAX_RETRIES} failed: {exc}. "
                    f"Waiting {wait}s then retrying with new browser (new proxy IP)…"
                )
                await asyncio.sleep(wait)
            else:
                log.error(
                    f"[{config.site_name}] All {MAX_RETRIES} attempts failed. Last error: {exc}"
                )
    raise last_exc


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html_with_retry(CONFIG, args.date))
