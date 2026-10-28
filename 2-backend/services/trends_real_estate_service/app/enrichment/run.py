"""CLI entrypoint for the enrichment pipeline (phase-1 trigger = manual run).

Usage (from repo root, with the service .env in place):

    python -m services.trends_real_estate_service.app.enrichment.run
    python -m services.trends_real_estate_service.app.enrichment.run --platforms instagram --limit 20
    python -m services.trends_real_estate_service.app.enrichment.run --force

Later this same run_enrichment() call can be wrapped by a scheduled job for the
monthly refresh — no code change to the pipeline itself.
"""
import argparse
import logging

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.pipeline import run_enrichment

settings = get_settings()


def main():
    parser = argparse.ArgumentParser(description="Run Real Estate Intelligence post enrichment.")
    parser.add_argument("--platforms", nargs="*", default=None,
                        help=f"Platforms to process (default: {settings.ENRICH_PLATFORMS})")
    parser.add_argument("--projects", nargs="*", default=None,
                        help=f"profile.project values to include (default: {settings.ENRICH_PROJECTS})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max posts per platform (handy for a cheap test run)")
    parser.add_argument("--force", action="store_true",
                        help="Re-analyze posts even if already enriched with the current prompt version")
    parser.add_argument("--workers", type=int, default=6,
                        help="Posts processed concurrently (each fans out to 7 LLM nodes)")
    parser.add_argument("--since", default=None,
                        help="Only posts published on or after this ISO date, e.g. 2026-03-01")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not settings.OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is not set — enrichment needs it. Add it to the service .env.")

    totals = run_enrichment(
        platforms=args.platforms,
        projects=args.projects,
        limit=args.limit,
        force=args.force,
        workers=args.workers,
        since=args.since,
    )
    print("\nEnrichment summary:")
    for platform, stats in totals.items():
        print(f"  {platform}: {stats}")


if __name__ == "__main__":
    main()
