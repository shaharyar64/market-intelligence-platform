"""Trend naming (micro) and umbrella grouping — the only places an LLM authors words."""
import json
import logging
import re

from pydantic import BaseModel, Field, ValidationError

from services.food_intelligence_service.app.trends import prompts

logger = logging.getLogger("trends.namer")


class ClusterName(BaseModel):
    name: str = Field(description="2-4 word English trend name")
    summary: str = Field(description="1-2 sentence neutral description")
    related_themes: list[str] = Field(default_factory=list)
    product_entities: list[str] = Field(default_factory=list)
    is_coherent: bool
    confidence: float = Field(ge=0.0, le=1.0)


def name_cluster(captions: list[str], hashtags: list[str], keywords: list[str],
                 client, model: str) -> ClusterName:
    user = (
        "DISTINCTIVE KEYWORDS: " + ", ".join(keywords or []) + "\n"
        "TOP HASHTAGS: " + ", ".join(hashtags or []) + "\n\n"
        "SAMPLE CAPTIONS (most representative first):\n"
        + "\n---\n".join(c[:300] for c in captions[:25])
    )
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompts.NAME_CLUSTER_SYSTEM},
                      {"role": "user", "content": user}],
        )
        return ClusterName.model_validate(json.loads(resp.choices[0].message.content))
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning("naming failed: %s", exc)
        return ClusterName(name="Unnamed Cluster", summary="", related_themes=[],
                           product_entities=[], is_coherent=False, confidence=0.0)


def slugify(name: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


class Umbrella(BaseModel):
    name: str
    summary: str
    members: list[str]


class UmbrellaSet(BaseModel):
    umbrellas: list[Umbrella]


def group_umbrellas(micro_summaries: list[dict], client, model: str) -> list[Umbrella]:
    """micro_summaries: [{trend_id, name, summary, keywords, post_count}]"""
    listing = "\n".join(
        f"- id={m['trend_id']} | {m['name']} | {m['summary'][:150]} | "
        f"keywords: {', '.join(m.get('keywords', [])[:6])} | posts: {m['post_count']}"
        for m in micro_summaries
    )
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompts.GROUP_UMBRELLAS_SYSTEM},
                      {"role": "user", "content": listing}],
        )
        umbrellas = UmbrellaSet.model_validate(
            json.loads(resp.choices[0].message.content)).umbrellas
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning("grouping failed: %s", exc)
        umbrellas = []
    return repair_partition(umbrellas, [m["trend_id"] for m in micro_summaries])


def repair_partition(umbrellas: list[Umbrella], all_ids: list[str]) -> list[Umbrella]:
    """Enforce: every id in exactly one umbrella. Strays -> flagged Misc bucket;
    duplicates keep first appearance only; unknown ids are dropped."""
    known = set(all_ids)
    seen: set[str] = set()
    repaired: list[Umbrella] = []
    for u in umbrellas:
        members = [m for m in u.members if m in known and m not in seen]
        seen.update(members)
        if members:
            repaired.append(Umbrella(name=u.name, summary=u.summary, members=members))
    strays = [i for i in all_ids if i not in seen]
    if strays:
        repaired.append(Umbrella(
            name="Misc (needs review)",
            summary="Micro-trends the grouping model failed to place; review manually.",
            members=strays,
        ))
    return repaired
