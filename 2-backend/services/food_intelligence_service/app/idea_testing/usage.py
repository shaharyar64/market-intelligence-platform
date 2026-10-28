"""Token usage per Idea Testing step, as the provider reported it.

Chat calls are counted from the usage OpenAI returns with every response,
collected through LangChain's usage callback. Embedding calls go through the
shared embed_query, which returns only the vector, so their input is counted
with the model's own tokenizer: that is exactly what the embeddings API bills.
"""
import tiktoken
from langchain_core.callbacks import get_usage_metadata_callback

_EMBED_ENCODING = tiktoken.get_encoding("cl100k_base")
PRICING_VERSION = "openai-list-2026-10"
PRICES_PER_1M = {
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "gpt-4o": (2.50, 1.25, 10.00),
    "text-embedding-3-large": (0.13, 0.13, 0.0),
}


def _price(model: str) -> tuple | None:
    matches = [k for k in PRICES_PER_1M if model.startswith(k)]
    return PRICES_PER_1M[max(matches, key=len)] if matches else None


def _chat_cost(model: str, u: dict) -> float | None:
    price = _price(model)
    if price is None:
        return None
    cached = u.get("cached_input_tokens", 0)
    return ((u["input_tokens"] - cached) * price[0] + cached * price[1]
            + u["output_tokens"] * price[2]) / 1e6


def _round(cost: float | None) -> float | None:
    return round(cost, 6) if cost is not None else None


def with_totals(usage: dict) -> dict:
    """Put cost_usd next to every total_tokens, and add both for the whole record.

    Parts are "llm" or "<step>": {"llm": ...} for chat calls, and "embeddings".
    A cost is None when its model has no known price, and so is any sum over it.
    """
    out, tokens, cost = {}, 0, 0.0
    for key, part in usage.items():
        if key == "embeddings":
            price = _price(part["model"])
            part_cost = None if price is None else part["input_tokens"] * price[0] / 1e6
            out[key] = {**part, "total_tokens": part["input_tokens"],
                        "cost_usd": _round(part_cost)}
            costs, tokens = [part_cost], tokens + part["input_tokens"]
        else:
            llm = part if key == "llm" else part["llm"]
            priced = {model: {**u, "cost_usd": _round(_chat_cost(model, u))}
                      for model, u in llm.items()}
            out[key] = priced if key == "llm" else {**part, "llm": priced}
            costs = [_chat_cost(model, u) for model, u in llm.items()]
            tokens += sum(u["total_tokens"] for u in llm.values())
        for c in costs:
            cost = None if cost is None or c is None else cost + c
    return {**out, "total_tokens": tokens, "cost_usd": _round(cost),
            "pricing": PRICING_VERSION}


def chat_usage(usage_metadata: dict) -> dict:
    """{model: token counts} from a LangChain usage callback's usage_metadata."""
    return {
        model: {
            "input_tokens": u.get("input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("total_tokens", 0),
            "cached_input_tokens": (u.get("input_token_details") or {}).get("cache_read", 0),
        }
        for model, u in usage_metadata.items()
    }


def run_with_usage(fn, *args, **kwargs) -> tuple:
    """Run fn and return (result, {model: token counts}) for its chat calls."""
    with get_usage_metadata_callback() as cb:
        result = fn(*args, **kwargs)
    return result, chat_usage(cb.usage_metadata)


class EmbeddingCounter:
    """Wraps an embed function and counts the calls and input tokens sent to it."""

    def __init__(self, embed, model: str):
        self._embed = embed
        self.usage = {"model": model, "calls": 0, "input_tokens": 0}

    def __call__(self, text: str):
        self.usage["calls"] += 1
        self.usage["input_tokens"] += len(_EMBED_ENCODING.encode(text))
        return self._embed(text)
