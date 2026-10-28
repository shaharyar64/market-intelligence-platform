import asyncio

from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args


CONFIG = HtmlCollectorConfig(
    site_name="highspiritsuae",
    # The site migrated from WordPress/WooCommerce to Magento (Hyva theme)
    # between 2026-08-04 and 2026-08-11 — old URL/selectors 404/redirect.
    base_url="https://highspiritsuae.com/beers.html",
    s3_prefix="beer-pricing/highspiritsuae",
    platform="highspiritsuae",
    region="Abu Dhabi",
    detail_selector="div.product-info-main",
    listing_selector="a.product-item-link",
    next_selector="a.pages-item-next",
    first_page_limit=12,
    # Price is filled in client-side via Alpine.js (x-html binding), not
    # present in the initial server-rendered HTML — wait for it to settle.
    detail_wait_until="networkidle",
    # 2026-10-20: the site 403s Playwright's default "HeadlessChrome" UA.
    # 2026-10-27: it then started 403ing the (stale) Chrome/124 Windows UA
    # too; a current Linux Chrome UA gets 200.
    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(CONFIG, args.date))
