"""Trend naming (micro) and umbrella grouping — the only places an LLM authors words."""
import json
import logging
import re
from functools import lru_cache

from pydantic import BaseModel, Field, ValidationError

from services.trends_real_estate_service.app.db import store
from services.trends_real_estate_service.app.trends import prompts

logger = logging.getLogger("trends.namer")


class ClusterName(BaseModel):
    name: str = Field(description="2-4 word English trend name")
    summary: str = Field(description="1-2 sentence neutral description")
    related_themes: list[str] = Field(default_factory=list)
    offering_entities: list[str] = Field(default_factory=list)
    is_coherent: bool
    confidence: float = Field(ge=0.0, le=1.0)


# Words that appear inside company names but describe the market, not the company.
_GENERIC = {"real", "estate", "properties", "property", "group", "holding",
            "development", "developments", "developer", "developers", "company",
            "international", "investment", "investments", "realty",
            "للتطوير", "العقاري", "العقارية", "مجموعة"}


@lru_cache(maxsize=1)
def _company_tokens() -> frozenset:
    """Every tracked company's name and handle, lowercased, as single tokens.

    A cluster that is one developer's feed has that developer's name as its most
    over-represented term, so c-TF-IDF hands the namer "aldar, yas, island" and
    the hashtags hand it "#aldar". Asking the model in prose not to name a trend
    after a company loses against evidence that is mostly the company's name -
    it still produced "Aldar Developments on Yas Island" and "Reportage
    Developments". Removing the names from the evidence is what changes it.
    """
    try:
        rows = store.run_query("SELECT brand_name, username FROM realestate_intel.brand")
    except Exception:
        logger.exception("could not load company names - naming may echo them")
        return frozenset()
    out = set()
    for r in rows:
        for value in (r.get("brand_name"), r.get("username")):
            for token in re.split(r"[^\w؀-ۿ]+", (value or "").lower()):
                if len(token) > 3 and token not in _GENERIC:
                    out.add(token)
    return frozenset(out)


def _strip_companies(terms):
    """Drop terms that are only a tracked company's name."""
    banned = _company_tokens()
    if not banned:
        return list(terms or [])
    kept = []
    for t in terms or []:
        tokens = [x for x in re.split(r"[^\w؀-ۿ]+", str(t).lower()) if x]
        if tokens and all(x in banned for x in tokens):
            continue
        kept.append(t)
    return kept


def name_cluster(keywords: list[str], client, model: str) -> ClusterName:
    kept = _strip_companies(keywords)
    if not kept:
        return ClusterName(name="Unnamed Cluster", summary="", related_themes=[],
                           offering_entities=[], is_coherent=False, confidence=0.0)
    user = "DISTINCTIVE KEYWORDS: " + ", ".join(kept)
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompts.NAME_CLUSTER_SYSTEM},
                      {"role": "user", "content": user}],
        )
        return ClusterName.model_validate(json.loads(resp.choices[0].message.content))
    except (json.JSONDecodeError, ValidationError) as exc:
        # The model answered but the answer did not parse - that IS a verdict
        # about the cluster, so record it as incoherent.
        logger.warning("naming produced an unusable response: %s", exc)
        return ClusterName(name="Unnamed Cluster", summary="", related_themes=[],
                           offering_entities=[], is_coherent=False, confidence=0.0)
    except Exception:
        # A transport, auth or rate-limit failure says nothing about the
        # cluster. Swallowing it here counted outages as "skipped_incoherent",
        # so a sustained one produced a run of zero trends that looked clean
        # and then replaced the good data. Let it propagate and fail the stage.
        logger.exception("naming call failed - failing the stage rather than "
                         "recording the cluster as incoherent")
        raise


def opportunity_summary(payload: dict, client, model: str) -> str:
    resp = client.chat.completions.create(
        model=model, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": prompts.OPPORTUNITY_SYSTEM},
                  {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    return json.loads(resp.choices[0].message.content).get("opportunity_summary", "") or ""


def slugify(name: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


class Umbrella(BaseModel):
    name: str
    summary: str
    members: list[str]


class UmbrellaSet(BaseModel):
    umbrellas: list[Umbrella]


def umbrella_target(micro_count: int) -> int:
    return max(4, min(12, round(micro_count / 3.5)))


def group_umbrellas(micro_summaries: list[dict], client, model: str) -> list[Umbrella]:
    """micro_summaries: [{trend_id, name, summary, keywords, post_count}]"""
    listing = f"TARGET: {umbrella_target(len(micro_summaries))} umbrellas\n" + "\n".join(
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
