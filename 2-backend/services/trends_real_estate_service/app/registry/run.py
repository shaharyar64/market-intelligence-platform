"""Rebuild realestate_intel.brand from the profile tables.

    python -m services.trends_real_estate_service.app.registry.run
    python -m services.trends_real_estate_service.app.registry.run --status

This exists because load_registry() had no caller anywhere in the service - not
a CLI, not a route, not a job - so the table was only ever rebuilt by hand. It
drifts continuously: the scrapers keep adding accounts, and every account that
reaches brand_posts before it reaches this table has its posts counted as
skipped_unmapped by the enrichment pipeline. One rebuild was measured to be
2,613 posts stale five hours later.

Rebuilding is safe to repeat. Keys are sticky, so a group that already exists
keeps the brand_key its enriched rows are stored under.
"""
import argparse
import logging

from services.trends_real_estate_service.app.db import store
from services.trends_real_estate_service.app.registry import brands

logger = logging.getLogger("registry.run")

UNMAPPED_SQL = """
    SELECT p.platform, count(DISTINCT p.author_username) AS accounts, count(*) AS posts
      FROM realestate_intel.brand_posts p
      LEFT JOIN realestate_intel.brand b
        ON b.platform = p.platform AND b.username = lower(p.author_username)
     WHERE b.brand_key IS NULL
     GROUP BY p.platform
     ORDER BY p.platform
"""


def status() -> dict:
    """Accounts that have posts but no registry row - i.e. how stale we are."""
    rows = store.run_query(UNMAPPED_SQL)
    total_posts = sum(r["posts"] for r in rows)
    for r in rows:
        logger.info("  %-10s %2d accounts, %5d posts unmapped",
                    r["platform"], r["accounts"], r["posts"])
    if not rows:
        logger.info("  registry is current - every account with posts has a row")
    return {"platforms": rows, "unmapped_posts": total_posts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true",
                        help="report drift without rebuilding")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    before = status()
    if args.status:
        return

    report = brands.load_registry()
    logger.info("registry rebuilt - %s seeded from social_data, %s auto-resolved, "
                "%s unresolved (name has no latin characters)",
                report["seeded"], len(report["auto_resolved"]), len(report["unresolved"]))
    for row in report["unresolved"]:
        logger.info("  unresolved: %s/%s keyed as %r",
                    row["platform"], row["username"], row["brand_key"])

    after = status()
    logger.info("unmapped posts: %s -> %s", before["unmapped_posts"], after["unmapped_posts"])


if __name__ == "__main__":
    main()
