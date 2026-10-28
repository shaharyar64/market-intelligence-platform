"""Embed community post captions with OpenAI into food_intel.post_embedding."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from openai import OpenAI

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.trends import store

logger = logging.getLogger("trends.embedder")
_MAX_CHARS = 6000
_MAX_PER_CALL = 512


@lru_cache(maxsize=1)
def _noise_tags() -> frozenset:
    """Tags that carry reach, not meaning - #fyp, #viral, #explore and their
    Arabic equivalents. Shared with the clusterer so one list governs both."""
    from services.food_intelligence_service.app.trends import clusterer
    return frozenset(clusterer._PLATFORM_NOISE) | _EXTRA_NOISE


# Seen in this corpus and missed by the shared list: a meme tag on 3,138 food
# posts, and reach tags the list did not name.
_EXTRA_NOISE = frozenset({
    "الشعب_الصيني_ماله_حل", "fpy", "instadaily", "instagood", "instafood",
    "tiktokfood", "tiktokfoodie", "tiktoktrending", "viralvideos",
    "foryourpage", "trendingnow", "explorepage",
})

# Deliberately NOT \w: that class counts katakana as a word character, so
# #fypシ survived it. Only the scripts this corpus actually writes in.
_DECORATION = re.compile(r"[^a-z0-9_؀-ۿ]+", re.UNICODE)


def _normalise_tag(tag: str) -> str:
    """Strip decoration so a dressed-up reach tag is still recognised.

    #fypシ sits on 3,229 food posts and is #fyp wearing a katakana character;
    matching the raw string misses every variant, and there is always another
    variant.
    """
    return _DECORATION.sub("", (tag or "").lower().lstrip("#")).strip("_")


def build_embed_text(caption: str, hashtags: list[str] | None) -> str:
    """The text a post is embedded from: its caption, plus the tags that say
    something about it.

    Engagement-bait tags are dropped. A post whose caption is two words and
    whose tag block is thirty entries long was being embedded almost entirely
    on #fyp #foryoupage #viral - which every other reach-seeking post also
    carries - so posts clustered by how they chase an audience rather than by
    what they are about. That is how a kitchenware retailer ended up beside a
    grape-leaves trend.
    """
    noise = _noise_tags()
    kept = [t for t in (hashtags or []) if t and _normalise_tag(t) not in noise]
    tags = " ".join(f"#{t}" for t in kept)
    text = f"{caption} {tags}".strip() if tags else (caption or "").strip()
    return text[:_MAX_CHARS]


def embed_texts(texts: list[str], client, model: str, dim: int,
                workers: int = 8) -> list[list[float]]:
    chunks = [texts[i:i + _MAX_PER_CALL] for i in range(0, len(texts), _MAX_PER_CALL)]
    if len(chunks) <= 1:
        if not chunks:
            return []
        resp = client.embeddings.create(model=model, input=chunks[0], dimensions=dim)
        return [d.embedding for d in resp.data]

    def call(chunk: list[str]) -> list[list[float]]:
        resp = client.embeddings.create(model=model, input=chunk, dimensions=dim)
        return [d.embedding for d in resp.data]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(call, chunks))
    return [vec for chunk_result in results for vec in chunk_result]


def run_embedding(cohort: str, limit: int | None = None, batch_size: int = 4096) -> dict:
    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    tag = store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
    stats = {"embedded": 0, "skipped_empty": 0}
    while True:
        rows = store.fetch_posts_missing_embeddings(cohort, tag, limit=batch_size)
        if not rows:
            break
        texts, keep = [], []
        for r in rows:
            t = build_embed_text(r["caption"], r.get("hashtags"))
            if t:
                texts.append(t)
                keep.append(r)
            else:
                stats["skipped_empty"] += 1
        if not texts:
            break
        vecs = embed_texts(texts, client, settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
        store.save_embeddings([
            (r["platform"], r["post_id"], tag, v) for r, v in zip(keep, vecs)
        ])
        stats["embedded"] += len(keep)
        logger.info("embedded %s (total %s)", len(keep), stats["embedded"])
        if limit and stats["embedded"] >= limit:
            break
    return stats
