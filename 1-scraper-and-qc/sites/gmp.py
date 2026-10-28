import asyncio

from html_manifest_collector import HtmlCollectorConfig, collect_html, parse_args


CONFIG = HtmlCollectorConfig(
    site_name="gmp",
    # Site migrated off WooCommerce to a custom Next.js storefront between
    # 2026-09-08 and 2026-09-15 — old /product-category/beer-rtd/ URL now
    # 404s. New site has no pagination (53 products server-rendered on one
    # page, matching recent history) and every page shows an interactive
    # 21+ age-gate that must be dismissed before the content is reachable.
    base_url="https://gmp.ae/beer",
    s3_prefix="beer-pricing/gmp",
    platform="gmp",
    region="Abu Dhabi",
    # New theme has no stable semantic classes (Tailwind utility classes
    # only) — anchor on the href pattern and the <main> landmark instead,
    # which survive a utility-class rebuild.
    detail_selector="main",
    remove_selectors=("section:has-text('You May Also Like')",),
    listing_selector="a[href^='/products/']",
    href_prefix="https://gmp.ae",
    popup_selector="button:has-text('Yes')",
    first_page_limit=20,
    listing_wait_until="load",
    # 2026-10-27: listing now renders 24 cards + a "Load more" button
    # (was all ~54 on one page until 10-20).
    load_more_selector="button:has-text('Load more')",
)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect_html(CONFIG, args.date))
