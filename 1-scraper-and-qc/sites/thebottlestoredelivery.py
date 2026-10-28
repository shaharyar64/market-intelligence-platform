import asyncio

from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args


CONFIG = HtmlCollectorConfig(
    site_name="thebottlestore",
    base_url="https://thebottlestoredelivery.com/beer-and-cider",
    s3_prefix="beer-pricing/thebottlestore",
    platform="thebottlestore",
    region="Abu Dhabi",
    detail_selector="#product-top-area",
    extra_detail_selectors=("#info-section",),
    listing_selector="#products-listing-row a.featured-link",
    next_selector=".pagination a[rel='next']",
    first_page_limit=15,
    load_more_selector="text=/load more/i",
    load_more_max_clicks=10,
    load_more_wait_ms=2000,
    listing_remove_selectors=("#age-overlay", ".cookie-bar"),
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(CONFIG, args.date))
