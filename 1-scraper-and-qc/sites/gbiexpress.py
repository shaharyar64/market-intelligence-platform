import asyncio

from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args, proxy_from_env


CONFIG = HtmlCollectorConfig(
    site_name="gbiexpress",
    base_url="https://www.gbiexpress.com/beer-cider",
    s3_prefix="beer-pricing/gbiexpress",
    platform="gbiexpress",
    region="Bahrain",
    detail_selector="#product-area",
    listing_selector="#product-list div.title > a",
    next_selector=".pagination > li:nth-last-child(2) > a",
    next_text=">",
    first_page_limit=16,
    headless=True,
    proxy=proxy_from_env(),
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(CONFIG, args.date))
