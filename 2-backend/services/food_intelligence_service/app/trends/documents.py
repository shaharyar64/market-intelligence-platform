"""Semantic documents for trend clustering.

Clustering raw captions makes a post join a trend only when its wording
resembles its neighbours', which marketing language often does not. Embedding a
document built from the post's analysis instead, what it shows and says rather
than how it is worded, raises both how many posts reach a trend and how tight
those trends are.

Food's analysis carries product_focus where real estate carries offering_focus;
every other field is the same.
"""
import json
import logging

import tiktoken
from openai import OpenAI

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.trends import store

logger = logging.getLogger("trends.documents")

VERSION = "analysis-v1"
VISUAL_MIN = 0.7
# Set well below OpenAI's stated 300,000-token batch limit. Measured against this
# corpus (heavily Arabic), the API's own token accounting ran ~1.24x higher than
# both cl100k_base and o200k_base local counts (309,310 charged vs. 249,940 /
# 239,982 counted for the same batch). 100,000 keeps ~2.5x headroom against that
# observed overshoot; do not raise this back toward 250,000 without re-measuring.
TOKEN_BUDGET = 100_000

_ENCODING = None


def _encoding():
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def _token_count(text: str) -> int:
    return len(_encoding().encode(text))


def _batch_by_tokens(rows: list[dict], token_budget: int, batch_size: int) -> list[list[dict]]:
    batches: list[list[dict]] = []
    batch: list[dict] = []
    batch_tokens = 0
    for row in rows:
        tokens = _token_count(row["document"][:8000])
        if batch and (batch_tokens + tokens > token_budget or len(batch) >= batch_size):
            batches.append(batch)
            batch, batch_tokens = [], 0
        batch.append(row)
        batch_tokens += tokens
    if batch:
        batches.append(batch)
    return batches


def document_tag() -> str:
    settings = get_settings()
    return store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM, variant=VERSION)


def _texts(items, key: str) -> list[str]:
    out = []
    for item in items or []:
        value = item.get(key) if isinstance(item, dict) else None
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
    return out


def semantic_document(analysis: dict | str | None) -> str:
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except json.JSONDecodeError:
            return ""
    if not isinstance(analysis, dict):
        return ""
    sections = []
    description = analysis.get("description")
    if isinstance(description, str) and description.strip():
        sections.append("Description:\n" + description.strip())
    themes = _texts(analysis.get("themes"), "label")
    if themes:
        sections.append("Themes:\n" + "; ".join(themes) + ".")
    products = _texts(analysis.get("product_focus"), "product")
    if products:
        sections.append("Offering:\n" + "; ".join(products) + ".")
    raw_semiotic = analysis.get("semiotic")
    semiotic: dict = raw_semiotic if isinstance(raw_semiotic, dict) else {}
    context = semiotic.get("text")
    if isinstance(context, str) and context.strip():
        sections.append("Semantic Context:\n" + context.strip())
    raw_scores = semiotic.get("visual")
    scores: dict = raw_scores if isinstance(raw_scores, dict) else {}
    strong = [name for name, score in sorted(scores.items(), key=lambda kv: -(kv[1] or 0))
              if isinstance(score, (int, float)) and score >= VISUAL_MIN]
    visuals = analysis.get("functional_visual")
    evidence = _texts(visuals if isinstance(visuals, list) else [], "visual_evidence")
    if strong or evidence:
        lead = ", ".join(strong) + ". " if strong else ""
        sections.append("Visual Context:\n" + lead + " ".join(evidence))
    return "\n\n".join(sections)


def attach(posts: list[dict]) -> list[dict]:
    analyses = store.fetch_analyses()
    for p in posts:
        p["document"] = semantic_document(analyses.get((p["platform"], p["post_id"])))
    return posts


def run_embedding(limit: int | None = None, batch_size: int = 2048) -> dict:
    """Embed each analysed post's semantic document under the analysis-v1 tag."""
    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    tag = document_tag()
    pending = store.posts_missing_embedding(tag, limit=limit)
    if not pending:
        return {"embedded": 0, "tag": tag}
    analyses = store.fetch_analyses()
    rows, written = [], 0
    for post in pending:
        doc = semantic_document(analyses.get((post["platform"], post["post_id"])))
        if len(doc.strip()) < 30:
            continue
        rows.append({**post, "document": doc})
    for batch in _batch_by_tokens(rows, TOKEN_BUDGET, batch_size):
        batch_tokens = sum(_token_count(r["document"][:8000]) for r in batch)
        logger.info("embedding batch: %s documents, %s tokens (local count)", len(batch), batch_tokens)
        resp = client.embeddings.create(
            model=settings.TREND_EMBED_MODEL,
            input=[r["document"][:8000] for r in batch],
            dimensions=settings.TREND_EMBED_DIM,
        )
        vectors = [e.embedding for e in resp.data]
        written += store.upsert_post_embeddings(
            [(r["platform"], r["post_id"], tag, v) for r, v in zip(batch, vectors, strict=True)])
        logger.info("embedded %s/%s analysis documents", written, len(rows))
    return {"embedded": written, "tag": tag}
