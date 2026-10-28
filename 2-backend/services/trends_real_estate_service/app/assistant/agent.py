"""Retrieval and context for the assistant.

The tool-calling loop that used to live here is gone: the assistant runs as a
LangGraph agent now (see graph.py), which is the same framework the enrichment
pipeline has always used. What remains is the work done *before* the graph -
embedding the question and assembling the material it should see - plus the
payload truncation the tools share.
"""
import json
import logging

from openai import OpenAI

from services.trends_real_estate_service.app.assistant import retrieval
from services.trends_real_estate_service.app.core.config import get_settings

logger = logging.getLogger("assistant.agent")

def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=4, timeout=60)


def embed_query(text: str) -> list[float]:
    settings = get_settings()
    resp = _client().embeddings.create(
        model=settings.TREND_EMBED_MODEL, input=[text],
        dimensions=settings.TREND_EMBED_DIM)
    return resp.data[0].embedding


def _truncate_payload(result: dict, limit: int = 20000) -> str:
    """Serialize a tool result for the model, truncating by element (not by
    character) so a cut can never sever a token mid-value. If it still does
    not fit after dropping trailing elements of result["data"], the payload
    is emitted as-is (never as malformed JSON)."""
    payload = dict(result)
    serialized = json.dumps(payload, default=str)
    if len(serialized) <= limit:
        return serialized
    data = payload.get("data")
    if not isinstance(data, list):
        return serialized
    items = list(data)
    omitted = 0
    while items:
        items.pop()
        omitted += 1
        payload["data"] = items
        payload["count"] = len(items)
        payload["truncated_items"] = omitted
        serialized = json.dumps(payload, default=str)
        if len(serialized) <= limit:
            return serialized
    return serialized


MAX_CONTEXT_DISTANCE = 0.50
CONTEXT_POSTS = 5


def build_context(question: str) -> tuple[str, int]:
    """Retrieve corpus material for the question before the model plans.

    Two things go in. The trend catalogue gives the model the real vocabulary -
    exact trend_id values and quadrants - which is what stops it inventing ids
    or searching for the word "breakthrough". The nearest posts give it evidence
    it can quote without spending a tool call.

    Posts are admitted only within MAX_CONTEXT_DISTANCE. Vector search returns
    neighbours for any question at all, so an ungated pre-fetch would hand off-topic
    posts to a question about bitcoin and make an unanswerable question look
    answerable; measured, in-scope questions land near 0.22-0.36 and off-topic
    ones at 0.60 and beyond.
    """
    lines: list[str] = []
    used = 0

    # The catalogue and the post search do not depend on each other, and this
    # database is ~0.8s away per round trip. Run sequentially they cost about
    # six seconds before the model had seen anything, which is most of the wait
    # a user experiences on a streamed answer.
    from concurrent.futures import ThreadPoolExecutor

    def _catalogue():
        try:
            return retrieval.trend_catalogue()
        except Exception:
            logger.warning("trend catalogue unavailable for context", exc_info=True)
            return []

    def _nearest():
        try:
            return retrieval.search_posts_scored(
                embed_query(question), limit=CONTEXT_POSTS,
                max_distance=MAX_CONTEXT_DISTANCE)
        except Exception:
            logger.warning("context post search failed", exc_info=True)
            return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        catalogue_future = pool.submit(_catalogue)
        posts_future = pool.submit(_nearest)
        catalogue = catalogue_future.result()
        posts = posts_future.result()
    if catalogue:
        # The catalogue is the all-markets run. Saying so keeps a question about
        # one country from being answered out of it: the UAE and KSA each have
        # their own run, reached through search_trends with countries.
        lines.append("TRENDS IN THE ALL-MARKETS RUN (use these exact trend_id values). "
                     "For a question about one country, call search_trends with "
                     "countries instead - that market has its own run:")
        lines += [f"  {c['trend_id']} | {c['name']} | {c['level']} | {c['quadrant']} "
                  f"| {c['post_count']} posts" for c in catalogue]
    if posts:
        used = len(posts)
        lines.append("")
        lines.append("POSTS CLOSEST TO THIS QUESTION:")
        for p in posts:
            caption = " ".join((p.get("caption") or "").split())[:200]
            lines.append(f"  [{p['source']}/{p['platform']}] @{p['author_username']} "
                         f"({p['engagement_total']} engagement): {caption}")
    if not lines:
        return "", 0
    lines.append("")
    lines.append("This material was retrieved for this question. Verify anything you "
                 "state with a tool call; nothing here excuses answering from memory.")
    return "\n".join(lines), used
