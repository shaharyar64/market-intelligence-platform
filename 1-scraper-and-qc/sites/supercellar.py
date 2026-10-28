import asyncio

from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args


CONFIG = HtmlCollectorConfig(
    site_name="supercellar",
    base_url="https://supercellar.ae/beer-ciders/",
    s3_prefix="beer-pricing/supercellar",
    platform="supercellar",
    region="Other Emirates",
    detail_selector="div.product-image-summary-wrap",
    listing_selector="div.wd-product a.product-image-link",
    next_selector="a.load-on-click",
    first_page_limit=50,
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(CONFIG, args.date))
