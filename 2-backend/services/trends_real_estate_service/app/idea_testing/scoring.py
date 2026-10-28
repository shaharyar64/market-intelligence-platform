"""Step D of the brief's evaluation flow: score all six 6C factors in one
structured LLM call over the evidence Task 6 already retrieved. The overall
score is NOT read from this call -- app.idea_testing.confidence.overall_score
computes it deterministically from the six factor scores (spec D2).
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.retry import invoke_with_retry
from services.trends_real_estate_service.app.idea_testing.schema import (
    ConceptExtraction,
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
framework used by real-estate brand and insight teams. Score the concept below against the six 6C
factors, using ONLY the retrieved evidence provided for each factor.

## Factors (score each 0-100)
{chr(10).join(f"- {fid}: {cue}" for fid, cue in _FACTOR_CUES.items())}

## Scoring rubric
0-20 Fails. 21-40 Weak. 41-60 Mixed. 61-80 Strong. 81-100 Exceptional. Use the full range.

## Evidence discipline
Citations must reference ONLY the post_id/trend_id/document_id values present in the evidence given
below for that factor. A document citation uses evidence_type "document", sets document_id to the
document_id field on the chunk you are citing, and leaves platform/post_id/trend_id empty. NEVER
invent, assume, or import evidence not shown to you. If a factor's evidence is empty, say so plainly
in the finding and cap that factor's score at 60.

Documents are proprietary research the team uploaded. Posts show what the market talks about,
documents show what the market measures. When a document carries a figure, benchmark, price, share
or other measured fact that bears on the factor you are scoring, use it and cite it rather than
resting the point on social posts alone. Quote the figure itself in the citation quote. A claim
about pricing, demand, buyer behaviour or market structure that a document can substantiate should
cite that document.

## Output rules
Recommendations must target the lowest-scoring factors with concrete, evidence-grounded advice --
not generic best practice. Do not compute or return an overall score; only the six factor scores
matter.

## Style
Never use an em dash (--) or en dash in headline, summary, verdict, finding, or recommendations.
Use a period, comma, or "and" instead. This does not apply to citations[].quote: quotes must stay
verbatim from the source, dashes included, even if the source itself uses one."""


def _structured_llm():
    settings = get_settings()
    return ChatOpenAI(
        model=settings.OPENAI_MODEL, temperature=0.0, api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(ScoringResult)


def _evidence_block(evidence_by_factor: dict[str, dict]) -> str:
    lines = []
    rendered_chunks: set[str] = set()
    for factor_id, bundle in evidence_by_factor.items():
        lines.append(f"--- Evidence for {factor_id} ---")
        posts = bundle.get("posts") or {}
        if posts.get("ok"):
            lines.append(f"Posts ({posts['count']}):")
            lines.append(json.dumps(posts["data"], default=str))
        else:
            lines.append(f"Posts: {posts.get('message', 'none')}")
        trends = bundle.get("trends")
        if trends is not None:
            if trends.get("ok"):
                lines.append(f"Trends ({trends['count']}):")
                lines.append(json.dumps(trends["data"], default=str))
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
                    lines.append(json.dumps(fresh, default=str))
                for chunk in repeats:
                    lines.append(
                        f"(also relevant here, quoted above: chunk_id "
                        f"{chunk.get('chunk_id')}, document_id {chunk.get('document_id')})")
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

    return invoke_with_retry(call, "idea_testing_scoring", max_attempts=3)
