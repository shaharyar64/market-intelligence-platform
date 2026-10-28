"""Re-extract products for posts analysed before product_focus carried
product_ar and kind, without re-running the other six analysis nodes.

Only analysis->'product_focus' is replaced; the row is then stamped with
product_focus_v so a re-run skips it. A post whose product node fails keeps its
old products and is picked up again next time.

Usage:
    python -m services.food_intelligence_service.app.enrichment.products_refresh --dry-run --limit 20
    python -m services.food_intelligence_service.app.enrichment.products_refresh --workers 6
"""
import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from services.food_intelligence_service.app.db.analysis_store import engine, run_query
from services.food_intelligence_service.app.enrichment.agent import PRODUCT_FOCUS_VERSION
from services.food_intelligence_service.app.enrichment.nodes.grounded_nodes import product_focus_node

logger = logging.getLogger("enrichment.products_refresh")

_PENDING = """
    SELECT platform, post_id, caption, analysis->'product_focus' AS old
    FROM food_intel.post_analysis
    WHERE COALESCE((analysis->>'product_focus_v')::int, 1) < :version
      AND btrim(COALESCE(caption, '')) <> ''
    ORDER BY posted_at DESC NULLS LAST
    LIMIT :limit
"""

_UPDATE = text("""
    UPDATE food_intel.post_analysis
    SET analysis = jsonb_set(analysis, '{product_focus}', CAST(:items AS jsonb))
                   || jsonb_build_object('product_focus_v', :version)
    WHERE platform = :platform AND post_id = :post_id
""")


def extract(caption: str) -> list[dict] | None:
    result = product_focus_node({"caption": caption})["product_focus"]
    return None if result is None else [p.model_dump() for p in result.product_focus]


def run(limit: int, workers: int, dry_run: bool) -> dict:
    rows = run_query(_PENDING, {"version": PRODUCT_FOCUS_VERSION, "limit": limit})

    def one(row: dict) -> str:
        items = extract(row["caption"])
        if items is None:
            return "failed"
        if dry_run:
            old = [p.get("product") for p in (row["old"] or [])]
            new = [f'{p["product"]} / {p["product_ar"]} ({p["kind"]})' for p in items]
            print(f"{row['platform']}:{row['post_id']}\n  old: {old}\n  new: {new}")
            return "previewed"
        with engine().begin() as conn:
            conn.execute(_UPDATE, {"items": json.dumps(items, ensure_ascii=False),
                                   "version": PRODUCT_FOCUS_VERSION,
                                   "platform": row["platform"], "post_id": row["post_id"]})
        return "updated"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(one, rows))
    return {"selected": len(rows), **{k: outcomes.count(k) for k in set(outcomes)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100_000)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true", help="print old vs new products, write nothing")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(run(args.limit, args.workers, args.dry_run))


if __name__ == "__main__":
    main()
