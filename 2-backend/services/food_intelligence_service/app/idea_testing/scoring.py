"""Step D of the brief's evaluation flow: score all six 6C factors in one
structured LLM call over the evidence Task 6 already retrieved. The overall
score is NOT read from this call -- app.idea_testing.confidence.overall_score
computes it deterministically from the six factor scores (spec D2).
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry
from services.food_intelligence_service.app.idea_testing.schema import (
    FACTOR_CRITERIA,
    ConceptExtraction,
    CriterionScore,
    FactorScore,
    RatedScoringResult,
    ScoringResult,
)

_FACTOR_CUES = {
    "clutter": "Look for genuine novelty of the core message vs. what the category already "
              "says. Penalise generic category claims. Reward messages not already common in "
              "the retrieved brand/influencer evidence.",
    "connect": "Look for a clear emotional payoff and personal relevance to the target, tied "
              "to a real need or tension visible in the retrieved community evidence.",
    "clarity": "Look for a single, instantly-understood message. Penalise jargon or a benefit "
              "the consumer must work to decode.",
    "competitive": "Look for a defensible point of difference vs. what the retrieved brand "
                  "evidence and related trends show is already being claimed.",
    "credibility": "Look for proof, mechanism, specificity and reason-to-believe. Penalise "
                   "vague or unsupported claims the retrieved evidence does not back up.",
    "conversion": "Look for a clear behaviour-change trigger: relevance + motivation + low "
                  "friction to act, grounded in the retrieved intent/switching language.",
}

_SYSTEM_PROMPT = f"""You are the evaluation engine for InsightFactor, a proprietary concept-testing
framework used by food brand and insight teams. Rate the concept below against the six 6C
factors, using ONLY the retrieved evidence provided for each factor.

## Factors and their criteria
{chr(10).join(
    f"- {fid}: {cue}" + "".join(f"{chr(10)}    - {cid}: {text}" for cid, text in FACTOR_CRITERIA[fid])
    for fid, cue in _FACTOR_CUES.items())}

## How to rate
For each factor, first write the finding: your reasoning from the evidence. Then rate every one
of that factor's criteria, by its criterion_id, on this scale:
0 = absent, or contradicted by the evidence
1 = weak: present but generic, vague or unsupported
2 = solid: clearly present and consistent with the evidence
3 = outstanding: clearly present, specific, and backed by the evidence
Rate each criterion on its own merits. Do not decide a factor's overall level first and then
rate every criterion to match it. Ratings of 0 and 3 are expected whenever they are deserved.
The factor score is computed from these ratings; do not return one.

Each post, trend and document carries a "match" label: how closely it relates to this
concept. Strong matches are direct evidence. Weak matches are only loosely related: do not
treat them as proof that the market wants, already offers, or talks about this exact concept.
When a market is selected, each trend also carries country_posts, country_share_pct (the share
of its posts with a known country that come from that market) and country_coverage_pct (how
many of its posts have a known country). A trend with little presence in the selected market
is weaker evidence for that market; say so when it matters.

## Evidence discipline
Citations must reference ONLY the post_id/trend_id/document_id values present in the evidence given
below for that factor. A document citation uses evidence_type "document", sets document_id to the
document_id field on the chunk you are citing, and leaves platform/post_id/trend_id empty. NEVER
invent, assume, or import evidence not shown to you. If a factor's evidence is empty, say so plainly
in the finding.

Every factor whose evidence is not empty MUST cite 1 to 3 items from that factor's evidence: the
items its finding actually rests on, preferring strong and moderate matches. The finding must say
what those items show; a finding that only mentions "posts" or "trends" in general is not grounded.

Documents are proprietary research the team uploaded. Posts show what the market talks about,
documents show what the market measures or what researchers found. When a document carries a
figure, benchmark, price, share or other measured fact that bears on the factor you are scoring,
use it and cite it rather than resting the point on social posts alone, and quote the figure itself
in the citation quote. Qualitative research counts too: consumer perceptions, barriers, triggers,
unmet needs and verbatim consumer quotes from a study are direct evidence about buyers. When a
document is a strong or moderate match for a factor, use what it says in that factor's finding and
cite it.

## Output rules
Recommendations must target the lowest-scoring factors with concrete, evidence-grounded advice --
not generic best practice. Do not compute or return any score.

## Style
Never use an em dash (--) or en dash in headline, summary, verdict, finding, or recommendations.
Use a period, comma, or "and" instead. This does not apply to citations[].quote: quotes must stay
verbatim from the source, dashes included, even if the source itself uses one."""


def _structured_llm():
    settings = get_settings()
    return ChatOpenAI(
        model=settings.IDEA_SCORING_MODEL, temperature=0.0, api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(RatedScoringResult)


_POST_MATCH = ((0.40, "strong"), (0.48, "moderate"))
_TREND_MATCH = ((0.50, "strong"), (0.58, "moderate"))


def _match(distance: float | None, bands: tuple) -> str:
    if distance is None:
        return "unknown"
    for limit, label in bands:
        if distance <= limit:
            return label
    return "weak"


def _labelled(items: list[dict], bands: tuple) -> list[dict]:
    return [{**item, "match": _match(item.get("distance"), bands)} for item in items]


def _factor_score(ratings: list[int]) -> int:
    return int(round(100 * sum(ratings) / (3 * len(ratings))))


def _to_scoring_result(rated: RatedScoringResult) -> ScoringResult:
    factors = []
    for f in rated.factors:
        labels = dict(FACTOR_CRITERIA[f.factor_id])
        order = [cid for cid, _ in FACTOR_CRITERIA[f.factor_id]]
        by_id = {r.criterion_id: r.rating for r in f.ratings}
        criteria = [CriterionScore(criterion_id=cid, label=labels[cid], rating=by_id[cid])
                    for cid in order]
        score = _factor_score([c.rating for c in criteria])
        factors.append(FactorScore(factor_id=f.factor_id, score=score, verdict=f.verdict,
                                   finding=f.finding, citations=f.citations,
                                   criteria=criteria))
    return ScoringResult(headline=rated.headline, summary=rated.summary, factors=factors,
                         recommendations=rated.recommendations)


def _evidence_block(evidence_by_factor: dict[str, dict]) -> str:
    lines = []
    rendered_chunks: set[str] = set()
    for factor_id, bundle in evidence_by_factor.items():
        lines.append(f"--- Evidence for {factor_id} ---")
        posts = bundle.get("posts") or {}
        if posts.get("ok"):
            lines.append(f"Posts ({posts['count']}):")
            lines.append(json.dumps(_labelled(posts["data"], _POST_MATCH), default=str, ensure_ascii=False))
        else:
            lines.append(f"Posts: {posts.get('message', 'none')}")
        trends = bundle.get("trends")
        if trends is not None:
            if trends.get("ok"):
                lines.append(f"Trends ({trends['count']}):")
                lines.append(json.dumps(_labelled(trends["data"], _TREND_MATCH), default=str, ensure_ascii=False))
            else:
                lines.append(f"Trends: {trends.get('message', 'none')}")
        documents = bundle.get("documents")
        if documents is not None:
            if documents.get("ok"):
                lines.append(f"Documents ({documents['count']}):")
                # A chunk relevant to several factors is listed for each of them, but its
                # text is spelled out only the first time so the prompt does not carry the
                # same passage six times over.
                fresh, repeats = [], []
                for chunk in documents["data"]:
                    if chunk.get("chunk_id") in rendered_chunks:
                        repeats.append(chunk)
                    else:
                        fresh.append(chunk)
                        rendered_chunks.add(chunk.get("chunk_id"))
                if fresh:
                    lines.append(json.dumps(_labelled(fresh, _POST_MATCH), default=str, ensure_ascii=False))
                for chunk in repeats:
                    match = _match(chunk.get("distance"), _POST_MATCH)
                    lines.append(
                        f"(also relevant here, {match} match for this factor, quoted above: "
                        f"chunk_id {chunk.get('chunk_id')}, document_id {chunk.get('document_id')})")
            else:
                lines.append("Documents: none")
    return "\n".join(lines)


def score_concept(concept: ConceptExtraction, evidence_by_factor: dict[str, dict]) -> ScoringResult:
    user_content = (
        f"CONCEPT:\n{concept.model_dump_json(indent=2)}\n\n"
        f"{_evidence_block(evidence_by_factor)}"
    )
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_content)]

    def call():
        return _structured_llm().invoke(messages)

    rated = invoke_with_retry(call, "idea_testing_scoring", max_attempts=3)
    return _to_scoring_result(rated)
