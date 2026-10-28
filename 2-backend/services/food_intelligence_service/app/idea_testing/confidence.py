"""Deterministic confidence math (spec §5). Every input here comes from
retrieved evidence or the trend corpus's own metrics -- never from an LLM's
self-report.
"""
import math
from collections.abc import Iterable
from datetime import date, datetime, timedelta

RECENCY_WINDOW_DAYS = 365

_KNOWN_SOURCES = {"community", "brand", "influencer"}

WEIGHTS = {"relevance": 0.35, "volume": 0.25, "spread": 0.20,
           "recency": 0.10, "quality": 0.10}


def relevance_score(post_distances: list[float | None],
                    trend_distances: list[float | None] = ()) -> float:
    usable = [d for d in [*post_distances, *trend_distances] if d is not None]
    if not usable:
        return 0.0
    return sum(max(0.0, 100.0 * (1.0 - d)) for d in usable) / len(usable)


def volume_score(n_posts: int, n_requested: int) -> float:
    if n_posts <= 0 or n_requested <= 0:
        return 0.0
    return 100.0 * math.log1p(n_posts) / math.log1p(n_requested)


def spread_score(source_types: set[str]) -> float:
    present = source_types & _KNOWN_SOURCES
    return 100.0 * len(present) / len(_KNOWN_SOURCES)


def count_recent(post_dates: Iterable[date | datetime | None], as_of: date | None,
                 window_days: int = RECENCY_WINDOW_DAYS) -> int:
    if as_of is None:
        return 0
    cutoff = as_of - timedelta(days=window_days)
    return sum(1 for d in post_dates
               if d is not None and (d.date() if isinstance(d, datetime) else d) > cutoff)


def recency_score(recent_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return 100.0 * recent_count / total_count


def quality_score(unique_authors: int, total_posts: int) -> float:
    if total_posts <= 0:
        return 0.0
    return 100.0 * unique_authors / total_posts


def combine(components: dict[str, float]) -> int:
    return int(round(sum(WEIGHTS[k] * components[k] for k in WEIGHTS)))


def overall_score(factor_scores: list[int]) -> int:
    return int(round(sum(factor_scores) / len(factor_scores)))


def confidence_label(score: float) -> str:
    if score <= 20:
        return "Very limited"
    if score <= 40:
        return "Low"
    if score <= 60:
        return "Moderate"
    if score <= 80:
        return "Good"
    return "High"


_STRONG = 75.0
_WEAK = 50.0

_STRENGTHS = {
    "relevance": "the evidence closely matches this concept",
    "volume": "plenty of relevant posts were found",
    "recency": "most of the evidence is from the last 12 months",
    "quality": "the evidence comes from many different accounts",
}

_WEAKNESSES = {
    "relevance": "most of the evidence only loosely matches this concept",
    "volume": "only a few relevant posts were found",
    "spread": "all of the evidence comes from one source type",
    "recency": "much of the evidence is more than a year old",
    "quality": "a handful of accounts make up much of the evidence",
}


def _strength(key: str, value: float) -> str | None:
    if key == "spread":
        if value >= 99.0:
            return "the evidence spans brands, influencers and the community"
        return "the evidence spans two of the three source types" if value >= 60.0 else None
    return _STRENGTHS[key] if value >= _STRONG else None


def _join(clauses: list[str]) -> str:
    return " and ".join(clauses)


def explain_confidence(score: float, components: dict[str, float]) -> str:
    if not components:
        return "No confidence breakdown was recorded for this assessment."
    values = {k: float(components.get(k) or 0.0) for k in WEIGHTS}
    if values["volume"] == 0.0 and values["relevance"] == 0.0:
        return ("No relevant posts or trends were found, so these scores rest on general "
                "principles rather than evidence.")

    strengths = [s for k in WEIGHTS if (s := _strength(k, values[k]))][:2]
    weak_keys = sorted((k for k in WEIGHTS if values[k] < _WEAK),
                       key=lambda k: WEIGHTS[k] * (100.0 - values[k]), reverse=True)[:2]
    weaknesses = [_WEAKNESSES[k] for k in weak_keys]

    if strengths and weaknesses:
        body = f"{_join(strengths)}, but {_join(weaknesses)}"
    elif strengths or weaknesses:
        body = _join(strengths or weaknesses)
    else:
        body = "the evidence is reasonable on every measure, with no single strength or gap"

    text = f"{body[0].upper()}{body[1:]}."
    if score <= 40:
        text += " Treat these scores as directional, not conclusive."
    return text
