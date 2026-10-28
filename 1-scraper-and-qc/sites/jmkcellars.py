import asyncio

from html_manifest_collector import CardHtmlCollectorConfig, collect_card_html, parse_args


CONFIG = CardHtmlCollectorConfig(
    site_name="jmkcellars",
    headless=True,
    storage_state="sessions/jmkcellars.json",
    base_url="https://jmkcellars.com/product-category/beer/",
    s3_prefix="beer-pricing/jmkcellars",
    platform="jmkcellars",
    region="Other Emirates",
    card_selector="ul.products > li.product",
    next_selector="nav.ct-pagination a.next.page-numbers",
    popup_selector="#myModal input[name='SKIP']",
    first_page_limit=12,
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_card_html(CONFIG, args.date))
