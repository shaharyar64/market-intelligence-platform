"""Marks every post as food or not, before anything downstream reads it.

The corpus was collected by hashtag scraping, so it carries a large non-food
tail: measured on random samples, 44% of community posts and 30% of brand and
influencer posts are banks, telecom, electronics, malls, or captions with no
discernible content at all. Those posts must never reach embedding, clustering
or metrics — a trend counting them is measuring the scrape, not the category.

The verdict is stored (food_intel.post_food, surfaced as is_food on the
food_intel.trend_posts view) rather than applied as a filter at read time, so it
is decided once and every reader gets the same answer. It sits in its own table
because it is this pipeline's judgement, not a property of the community dump or
of the brand crawl, and it has to cover posts from both. Runs are resumable:
only rows with is_food IS NULL are sent.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.trends import prompts, store

logger = logging.getLogger("trends.foodfilter")


def classify_batch(captions: list[str], client, model: str) -> list[bool | None]:
    """None marks a caption the model did not rule on, so it stays unclassified
    and is retried on the next run rather than being silently dropped."""
    numbered = "\n".join(f"{i + 1}. {c[:400]}" for i, c in enumerate(captions))
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompts.FOOD_FILTER_SYSTEM},
                      {"role": "user", "content": numbered}],
        )
        labels = json.loads(resp.choices[0].message.content).get("labels", [])
    except Exception as exc:
        logger.warning("food filter batch failed: %s", exc)
        labels = []
    out: list[bool | None] = []
    for i in range(len(captions)):
        label = labels[i] if i < len(labels) else None
        out.append(bool(label) if isinstance(label, bool) else None)
    return out


def run_food_filter(limit: int | None = None, batch_size: int = 20,
                    workers: int = 24, model: str | None = None) -> dict:
    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    model = model or settings.OPENAI_MODEL
    store.ensure_food_column()
    posts = store.fetch_unclassified_captions(limit=limit)
    stats = {"checked": 0, "food": 0, "not_food": 0, "unresolved": 0}
    if not posts:
        return stats

    batches = [posts[i:i + batch_size] for i in range(0, len(posts), batch_size)]
    logger.info("food filter: %s posts in %s batches, %s workers",
                len(posts), len(batches), workers)
    lock = threading.Lock()
    pending: list[tuple[str, str, bool]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(classify_batch, [p["caption"] for p in b], client, model): b
                   for b in batches}
        for done, future in enumerate(as_completed(futures), 1):
            batch = futures[future]
            try:
                labels = future.result()
            except Exception as exc:
                logger.warning("food filter batch failed: %s", exc)
                labels = [None] * len(batch)
            with lock:
                for p, label in zip(batch, labels):
                    if label is None:
                        stats["unresolved"] += 1
                        continue
                    pending.append((p["platform"], p["post_id"], label))
                    stats["checked"] += 1
                    stats["food" if label else "not_food"] += 1
                if done % 100 == 0:
                    store.save_food_flags(pending)
                    pending = []
                    logger.info("classified %s / %s (%s food, %s not food)",
                                stats["checked"], len(posts), stats["food"], stats["not_food"])
    store.save_food_flags(pending)
    return stats


def train_and_apply(label_fraction: float = 0.008, teacher: str = "gpt-4o",
                    batch_size: int = 20, workers: int = 16,
                    min_precision: float = 0.90) -> dict:
    """Teach a linear classifier from LLM labels, then score the whole corpus.

    Asking an LLM about every post costs either accuracy or money: gpt-4o-mini
    agrees with gpt-4o on only 88.5% of captions, and gpt-4o over the full corpus
    runs to roughly $120 and several hours. Labelling a few thousand posts with
    gpt-4o and fitting a logistic regression on the embeddings we already have
    beat both, at 92.8% held-out accuracy for about $1.50.

    Refuses to apply a model whose held-out precision misses `min_precision` —
    precision is the leakage number, the share of admitted posts that really are
    food, and a weak model must not be allowed to quietly relabel the corpus.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    from sklearn.model_selection import train_test_split

    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    store.ensure_food_column()

    junk = store.mark_junk_captions()
    logger.info("ruled out %s posts with unreadable captions", junk)

    rows = store.fetch_labeling_set(label_fraction, tag)
    logger.info("labelling %s posts with %s", len(rows), teacher)
    batches = [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]
    labels: list[bool | None] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for out in pool.map(lambda b: classify_batch([r["caption"] for r in b], client, teacher),
                            batches):
            labels.extend(out)

    keep = [i for i, l in enumerate(labels) if l is not None]
    X = np.array([rows[i]["vec"] for i in keep])
    y = np.array([labels[i] for i in keep], dtype=int)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    clf = LogisticRegression(max_iter=2000).fit(Xtr, ytr)
    pred = clf.predict(Xte)
    quality = {
        "labeled": int(len(y)),
        "teacher_food_rate": round(float(y.mean()), 4),
        "accuracy": round(float(accuracy_score(yte, pred)), 4),
        "precision": round(float(precision_score(yte, pred)), 4),
        "recall": round(float(recall_score(yte, pred)), 4),
    }
    logger.info("classifier quality: %s", quality)
    if quality["precision"] < min_precision:
        raise SystemExit(
            f"precision {quality['precision']} below required {min_precision} — "
            "not applying; the corpus keeps its current labels")

    clf_full = LogisticRegression(max_iter=2000).fit(X, y)
    scored = store.apply_food_model(clf_full.coef_[0].tolist(),
                                    float(clf_full.intercept_[0]), tag)
    return {"junk_ruled_out": junk, "scored": scored, **quality,
            "status": store.food_filter_status()}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Flag posts as food / not food.")
    parser.add_argument("--mode", choices=["model", "llm"], default="model",
                        help="model: label a sample with a strong LLM, fit a classifier on "
                             "embeddings, score everything. llm: ask the LLM about every post.")
    parser.add_argument("--label-fraction", type=float, default=0.008)
    parser.add_argument("--teacher", default="gpt-4o")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--model", default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.mode == "model":
        result = train_and_apply(label_fraction=args.label_fraction, teacher=args.teacher,
                                 batch_size=args.batch_size, workers=min(args.workers, 16))
    else:
        result = run_food_filter(limit=args.limit, batch_size=args.batch_size,
                                 workers=args.workers, model=args.model)
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
