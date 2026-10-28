import asyncio

from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args


CONFIG = HtmlCollectorConfig(
    site_name="bdutyfree",
    base_url="https://bdutyfree.com/departure/liquor/beers-rtd-237/beers-270.html",
    s3_prefix="beer-pricing/bdutyfree",
    platform="bdutyfree",
    region="Bahrain",
    detail_selector=".product-info",
    listing_selector="ol.products > li a.product-item-link",
    first_page_limit=36,
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(CONFIG, args.date))
