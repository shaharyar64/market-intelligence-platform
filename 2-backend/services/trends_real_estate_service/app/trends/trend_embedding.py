"""Embed each trend so the assistant can find them by meaning, not by spelling.

search_trends matched `name ILIKE '%word%'`, so "poultry" found nothing while
31 trends were named after chicken, and "milk" ranked a pasta salad first
because the word appeared somewhere in its summary. Both are the same defect:
a substring test has no idea what a trend is about.

Usage:
    python -m ...trends.trend_embedding            embed the latest run
    python -m ...trends.trend_embedding --status
"""
import argparse
import logging

from openai import OpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.trends import embedder, store

logger = logging.getLogger("trends.trend_embedding")


def ensure_table() -> None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS realestate_intel.trend_embedding (
                run_id    text NOT NULL,
                trend_id  text NOT NULL,
                model     text NOT NULL,
                embedding vector NOT NULL,
                PRIMARY KEY (run_id, trend_id, model)
            )
        """)


def _text(name: str, summary: str | None, keywords: list | None,
          products: list | None) -> str:
    parts = [name]
    if summary:
        parts.append(summary)
    for extra in (keywords or [])[:12], (products or [])[:8]:
        if extra:
            parts.append(" ".join(str(x) for x in extra if x))
    return " ".join(parts)[:4000]


def latest_run() -> str | None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT run_id FROM realestate_intel.trends WHERE country IS NULL ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None


def pending(run_id: str, tag: str) -> list[dict]:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT t.trend_id, t.name, t.narrative->>'summary' AS summary,
                   t.narrative->'keywords' AS keywords,
                   t.narrative->'offering_entities' AS products
            FROM realestate_intel.trends t
            WHERE t.run_id = %s
              AND NOT EXISTS (SELECT 1 FROM realestate_intel.trend_embedding e
                              WHERE e.run_id = t.run_id AND e.trend_id = t.trend_id
                                AND e.model = %s)
        """, (run_id, tag))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def save(run_id: str, tag: str, rows: list[tuple[str, list[float]]]) -> int:
    if not rows:
        return 0
    with store.get_conn() as conn, conn.cursor() as cur:
        for trend_id, vec in rows:
            cur.execute("""
                INSERT INTO realestate_intel.trend_embedding (run_id, trend_id, model, embedding)
                VALUES (%s, %s, %s, %s::vector)
                ON CONFLICT (run_id, trend_id, model) DO UPDATE
                   SET embedding = EXCLUDED.embedding
            """, (run_id, trend_id, tag,
                  "[" + ",".join(f"{v:.6f}" for v in vec) + "]"))
        conn.commit()
    return len(rows)


def run(run_id: str | None = None, batch: int = 256) -> dict:
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    ensure_table()
    run_id = run_id or latest_run()
    if not run_id:
        return {"error": "no trend run found"}

    todo = pending(run_id, tag)
    if not todo:
        return {"run_id": run_id, "embedded": 0, "note": "already up to date"}

    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=6, timeout=120)
    total = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        texts = [_text(r["name"], r["summary"], r["keywords"], r["products"])
                 for r in chunk]
        vecs = embedder.embed_texts(texts, client, settings.TREND_EMBED_MODEL,
                                    settings.TREND_EMBED_DIM)
        total += save(run_id, tag, list(zip([r["trend_id"] for r in chunk], vecs, strict=True)))
        logger.info("  embedded %s / %s", total, len(todo))
    return {"run_id": run_id, "embedded": total}


def status() -> dict:
    settings = get_settings()
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    rid = latest_run()
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM realestate_intel.trends WHERE run_id = %s", (rid,))
        trends = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FROM realestate_intel.trend_embedding
                       WHERE run_id = %s AND model = %s""", (rid, tag))
        embedded = cur.fetchone()[0]
    return {"run_id": rid, "trends": trends, "embedded": embedded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.status:
        for k, v in status().items():
            print(f"  {k}: {v}")
        return
    for k, v in run(args.run_id).items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
