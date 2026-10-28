"""Intent and plan for one question, decided before the agent calls any tool."""
import json
import logging
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from services.trends_real_estate_service.app.assistant.toolargs import CountryCode

logger = logging.getLogger("assistant.intent")

Intent = Literal[
    "trend_discovery", "trend_detail", "developers_by_topic", "developers_in_trend",
    "developer_profile", "developer_trends", "post_examples", "counts", "comparison",
    "property_evaluation", "definition", "out_of_scope", "other",
]
INTENTS = get_args(Intent)
_COUNTRY_ALIASES = {"SA": "SA", "KSA": "SA", "SAUDI ARABIA": "SA",
                    "AE": "AE", "UAE": "AE", "UNITED ARAB EMIRATES": "AE"}


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class QueryPlan(BaseModel):
    """What the intent step decided about one question."""

    model_config = ConfigDict(extra="ignore")

    intent: Intent = "other"
    resolved_question: str = ""
    topic: str | None = None
    expanded_terms: list[str] = Field(default_factory=list)
    countries: list[CountryCode] = Field(default_factory=list)
    developers: list[str] = Field(default_factory=list)
    trend_refs: list[str] = Field(default_factory=list)
    is_followup: bool = False
    is_correction: bool = False
    rejected_items: list[str] = Field(default_factory=list)
    needs_definition: bool = False
    plan: list[str] = Field(default_factory=list)

    @field_validator("intent", mode="before")
    @classmethod
    def _known_intent(cls, value):
        return value if value in INTENTS else "other"

    @model_validator(mode="after")
    def _corrections_are_in_scope(self):
        if self.intent == "out_of_scope" and (self.is_correction or self.needs_definition
                                               or self.is_followup):
            self.intent = "definition" if self.needs_definition else "other"
        return self

    @field_validator("countries", mode="before")
    @classmethod
    def _country_codes(cls, value):
        codes = [_COUNTRY_ALIASES.get(str(v).strip().upper()) for v in _as_list(value)]
        return list(dict.fromkeys(c for c in codes if c))

    @field_validator("expanded_terms", "developers", "trend_refs", "rejected_items", "plan",
                     mode="before")
    @classmethod
    def _string_list(cls, value):
        return [str(v) for v in _as_list(value) if v not in (None, "")]

HISTORY_MESSAGES = 6

PLANNER_INSTRUCTION = """\
You plan how a GCC real-estate social-media intelligence assistant should answer
one question. You do not answer it. Return one JSON object only:

{
  "intent": one of %(intents)s,
  "resolved_question": the question rewritten to stand alone (resolve "they",
                       "these", "this trend" from the conversation),
  "topic": the subject in a few words, or null,
  "expanded_terms": 4-10 concrete words or phrases people would actually write in
                    a property post about the topic (brand names, certifications,
                    features), not abstract labels. For "sustainability": solar,
                    net zero, LEED, Estidama, green building, energy efficient,
                    district cooling, recycled water, EV charging. Empty if no topic,
  "countries": subset of ["SA", "AE"] the question is about (a city implies its
               country), else [],
  "developers": developer names the question is about (resolved from the
                conversation), else [],
  "trend_refs": trend names or trend_ids the question refers to, else [],
  "is_followup": true if it depends on the previous turn,
  "is_correction": true if the user says the previous answer was wrong, off-topic,
                   repeated, or did not answer the question,
  "rejected_items": names from the previous answer the user rejected, else [],
  "needs_definition": true if the user asks what a concept means or whether the
                      assistant understands it,
  "plan": 1-4 short steps naming the tools to call and with what arguments
}

Tools available: search_trends(query, countries, quadrant), get_trend(trend_id),
compare_trends, get_timeline, search_posts(query, filters), aggregate_posts,
list_brands, get_brand_profile(brand), get_brand_trends(brand),
developers_by_topic(query, countries), developers_in_trend(trend_id),
create_trend(query).

Planning rules:
- A topic question ("trends around X") -> search_trends with the most concrete
  terms; if the topic is abstract, also search_posts with expanded_terms;
  create_trend if no trend fits.
- "Which developers focus on / are doing X", "which brands do they partner with"
  -> developers_by_topic with expanded_terms (partner brand names belong in the
  query). Never list_brands followed by get_brand_trends for this.
- "Which brands/partners do they work with" -> developers_by_topic with the
  developers' names plus partner brand names that appear in branded residences
  (Armani, Bvlgari, Versace, Missoni, Cavalli, Elie Saab, Bugatti, Lamborghini,
  Porsche, Aston Martin, Mercedes-Benz, W, Ritz-Carlton, Four Seasons, Waldorf
  Astoria, Nobu, Chelsea, Arsenal, Manchester City) in expanded_terms.
- "Which developers are active in this trend" -> developers_in_trend.
- A question about one named developer (its strategy, communication, analysis,
  opportunities) -> get_brand_profile(brand) for what it says and
  get_brand_trends(brand) for the trends it is in; search_trends for the market
  context. Never aggregate_posts: it cannot filter by developer, so its counts
  are never one developer's numbers. Put the name in "developers".
- A follow-up still needs tools: the conversation is never the source.
- A definition question about a market topic still plans searches with
  expanded_terms after the explanation.
- A correction -> a DIFFERENT strategy from the previous turn's tool calls (other
  terms, search_posts, developers_by_topic, create_trend), never the same call.
- property_evaluation is only for assessing one named place or project.
- out_of_scope is only for questions with nothing to do with property or real
  estate. A correction, follow-up or "do you understand X" about a property
  topic is never out_of_scope.
"""


def _history(transcript: list[dict]) -> str:
    lines = []
    for entry in (transcript or [])[-HISTORY_MESSAGES:]:
        role = entry.get("role")
        text = " ".join((entry.get("text") or "").split())
        if role == "user":
            lines.append(f"USER: {text[:500]}")
            continue
        lines.append(f"ASSISTANT: {text[:700]}")
        trace = trace_text(entry.get("tool_calls") or [])
        if trace:
            lines.append(f"ASSISTANT TOOL CALLS: {trace}")
    return "\n".join(lines)


def trace_text(calls: list[dict]) -> str:
    parts = []
    for c in calls:
        if not c.get("name"):
            continue
        args = json.dumps(c.get("args") or {}, ensure_ascii=False, sort_keys=True)
        ids = c.get("ids") or {}
        top = ", ".join(f"{n} [trend_id={ids[n]}]" if n in ids else n
                        for n in c.get("top") or [])
        parts.append(f"{c['name']}({args}) -> {c.get('count', 0)} results"
                     + (f": {top}" if top else ""))
    return "; ".join(parts)


def _complete(system: str, user: str) -> str:
    from services.trends_real_estate_service.app.assistant.agent import _client
    from services.trends_real_estate_service.app.core.config import get_settings
    resp = _client().chat.completions.create(
        model=get_settings().OPENAI_MODEL, temperature=get_settings().ASSISTANT_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return resp.choices[0].message.content or "{}"


def classify(question: str, transcript: list[dict]) -> QueryPlan | None:
    try:
        raw = json.loads(_complete(
            PLANNER_INSTRUCTION % {"intents": list(INTENTS)},
            f"CONVERSATION:\n{_history(transcript) or '(none)'}\n\nQUESTION: {question}"))
        if not isinstance(raw, dict) or not raw:
            return None
        return QueryPlan.model_validate(raw)
    except (ValidationError, ValueError):
        logger.warning("intent plan did not validate; answering without a plan", exc_info=True)
        return None
    except Exception:
        logger.warning("intent planning failed; answering without a plan", exc_info=True)
        return None


def plan_message(plan: QueryPlan | None) -> str | None:
    if not plan:
        return None
    lines = ["QUERY PLAN (from the intent step - follow it unless tool results show "
             "it is wrong):",
             f"  intent: {plan.intent}",
             f"  question: {plan.resolved_question}"]
    for key in ("topic", "expanded_terms", "countries", "developers", "trend_refs"):
        if getattr(plan, key):
            lines.append(f"  {key}: {getattr(plan, key)}")
    for step in plan.plan:
        lines.append(f"  - {step}")
    if plan.intent != "out_of_scope":
        lines.append("Call the tools the plan names before answering. Earlier answers "
                     "in the conversation are not a source, even for a follow-up.")
    if plan.is_correction:
        rejected = ", ".join(plan.rejected_items) or "the previous answer"
        lines.append(
            f"THE USER REJECTED THE PREVIOUS ANSWER ({rejected}). Do not repeat it and "
            "do not re-run the previous turn's tool calls with the same arguments - "
            "they will be refused. Use a different strategy from the plan. If the data "
            "still has nothing that fits, say so plainly, name what you searched, and "
            "do not re-present the rejected items as matching. Open with what is new "
            "this turn - a new search, new trends, new posts - never with an item the "
            "user already saw.")
    if plan.needs_definition:
        lines.append(
            "The user asks what the concept means. Open with a short explanation from "
            "general knowledge under the heading 'Background:' (one short paragraph), "
            "then call search_trends and search_posts with the expanded terms and report "
            "what the data shows. Never say you searched for something you did not.")
    return "\n".join(lines)
