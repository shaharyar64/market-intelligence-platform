import json
import logging

from openai import OpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.trends import embedder, store

logger = logging.getLogger("trends.documents")

VERSION = "analysis-v1"
VISUAL_MIN = 0.7


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
        analysis = json.loads(analysis)
    if not isinstance(analysis, dict):
        return ""
    sections = []
    description = analysis.get("description")
    if isinstance(description, str) and description.strip():
        sections.append("Description:\n" + description.strip())
    themes = _texts(analysis.get("themes"), "label")
    if themes:
        sections.append("Themes:\n" + "; ".join(themes) + ".")
    offerings = _texts(analysis.get("offering_focus"), "offering")
    if offerings:
        sections.append("Offering:\n" + "; ".join(offerings) + ".")
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
    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    tag = document_tag()
    embedded = 0
    while True:
        rows = store.fetch_documents_to_embed(tag, limit=batch_size)
        pairs = [(r, semantic_document(r["analysis"])) for r in rows]
        pairs = [(r, text) for r, text in pairs if text]
        if not pairs:
            break
        vectors = embedder.embed_texts([text for _, text in pairs], client,
                                       settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
        store.save_embeddings([(r["platform"], r["post_id"], tag, v)
                               for (r, _), v in zip(pairs, vectors, strict=True)], replace=True)
        embedded += len(pairs)
        logger.info("embedded %s analysis documents (total %s)", len(pairs), embedded)
        if limit and embedded >= limit:
            break
    return {"embedded": embedded, "tag": tag}
