"""Enforce the no-verdict rule on an answer before it reaches the reader.

The system prompt and the persona message both forbid verdicts ("an attractive
option", "a promising area") and statements about a developer's standing
("Emaar, a prominent developer"). Instructions lower how often those appear;
they do not stop them. Measured on the same 24 persona questions, rewording
the instructions - including removing every quoted example of a banned phrase
- moved the rate from 3 to 4 descriptor answers and from 6 to 4 verdict
answers: noise. The phrases came from the model's own knowledge (none of them
was in any tool result) or were marketing copy restated in its own voice.

So the rule is checked in code, after the answer is written:

  find_violations   deterministic patterns, run on the text outside quotation
                    marks - a post's own words, quoted and attributed, are the
                    correct way to report a marketing claim
  enforce           one targeted rewrite of just the flagged phrases, checked
                    again; a rewrite that invents a link or guts the answer is
                    refused; if flagged phrasing survives the rewrites, the
                    sentences carrying it are removed. Nothing flagged ships.
"""
import difflib
import json
import logging
import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("assistant.guard")


class AnswerVerificationError(RuntimeError):
    """A persona answer could not be proven safe to release."""

MAX_REWRITES = 2
# A rewrite shorter than this share of the original has dropped content, not
# just the flagged phrases, and is refused.
MIN_KEPT = 0.6

_STANDING = (r"prominent|reputable|well[- ]known|renowned|leading|major|established|"
             r"top|trusted|respected|premier|biggest|largest")
_ACTOR = r"(?:(?:real[- ]estate|property)\s+)?(?:developers?|players?|brand|name)"

# (kind, why, pattern). The reason is what the rewrite is told, so it says
# what the data can and cannot support rather than naming a style rule.
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("descriptor", "describes a developer's standing, which the data does not hold",
     re.compile(rf"\b(?:an?|the)\s+(?:{_STANDING})\s+{_ACTOR}\b", re.I)),
    ("descriptor", "describes a developer's standing, which the data does not hold",
     re.compile(r"\b(?:strong|proven|established)\s+track\s+record\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\battractive\s+(?:option|opportunit(?:y|ies)|choice|investment|"
                r"destination|proposition|prospect|location|area|place)\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\bmak(?:es|ing)\s+(?:it|this|them|the\s+area)\s+(?:an?\s+)?(?:attractive|"
                r"appealing|ideal|compelling|strong|good|great|smart|solid)\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\b(?:compelling|promising|sought[- ]after|stands?\s+out\s+as)\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\bhigh[- ]value\s+(?:investment|opportunit(?:y|ies)|asset|destination)\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\b(?:a\s+)?(?:good|great|smart|sound|safe|solid|wise|excellent)\s+"
                r"(?:investment|buy|bet|purchase)\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\bworth\s+(?:considering|a\s+look|exploring|investing)\b", re.I)),
    ("verdict", "judges the place or investment instead of reporting what posts say",
     re.compile(r"\b(?:has|have|with|offers?|shows?)\s+(?:strong|significant|great|high|"
                r"good|real)\s+(?:investment\s+)?potential\b", re.I)),
    ("verdict", "judges an attribute as positive instead of reporting the evidence",
     re.compile(r"\b(?:a\s+)?positive\s+(?:aspect|sign|factor|feature|indicator)\b", re.I)),
    ("verdict", "uses unsupported evaluative language instead of reporting evidence",
     re.compile(r"\b(?:vibrant|appealing|significant\s+advantage)\b", re.I)),
    ("inference", "infers standing or quality from mentions rather than evidence",
     re.compile(r"\bsuggest(?:s|ing)?\s+(?:a\s+)?(?:level\s+of\s+)?(?:credibility|"
                r"experience|quality|reliability|trust)\b", re.I)),
    ("inference", "turns an observed feature into an unsupported implication",
     re.compile(r"\b(?:might|may|could|can)\b", re.I)),
    ("inference", "turns positioning language into an unsupported measurement",
     re.compile(r"\b(?:suggest(?:s|ed|ing)?|indicat(?:e|es|ed|ing))\b", re.I)),
    ("inference", "turns an observed feature into an unsupported consumer conclusion",
     re.compile(r"\b(?:might|may|could)\s+be\s+(?:of\s+interest|attractive|appealing|"
                r"beneficial|a\s+concern)\b", re.I)),
    ("verdict", "judges an attribute as beneficial instead of reporting evidence",
     re.compile(r"\bbeneficial\b", re.I)),
    ("inference", "infers consumer or market conditions not measured by the data",
     re.compile(r"\b(?:family[- ]friendly|safe\s+and\s+welcoming|well[- ]developed|"
                r"well[- ]established|strong\s+market\s+conversation|"
                r"potential\s+interest|future\s+potential|"
                r"growth\s+potential|good\s+connectivity)\b", re.I)),
    ("inference", "adds an unsupported interpretation to reported evidence",
     re.compile(r"\bhighlighting\s+(?:relevance|appeal|quality|demand|potential)\b", re.I)),
    ("verdict", "judges positioning instead of reporting the source's words",
     re.compile(r"\b(?:competitive\s+option|future\s+growth|significant\s+(?:development|"
                r"topic)|easy\s+access|premium\s+and\s+distinctive)\b", re.I)),
    ("advice", "advises the reader, which the assistant never does",
     re.compile(r"\b(?:i|we)\s+(?:would\s+)?(?:recommend|suggest|advise)\b", re.I)),
    ("advice", "advises the reader, which the assistant never does",
     re.compile(r"(?<!whether\s)\byou\s+should\s+(?:buy|invest|consider|avoid|look)\b", re.I)),
    ("advice", "advises the reader, which the assistant never does",
     re.compile(r"\b(?:buyers?|investors?|families|residents?|users?)\s+should\s+"
                r"(?:buy|invest|consider|avoid|review|check|look)\b", re.I)),
    ("advice", "advises the reader, which the assistant never does",
     re.compile(r"\b(?:consult(?:ing)?\s+(?:an?|with|your)\b|due\s+diligence)", re.I)),
    ("advice", "suggests a next step instead of naming the evidence gap",
     re.compile(r"\b(?:further\s+investigation|investigate\s+further|site\s+visits?|"
                r"visits?\s+or\s+independent\s+reviews?)\b", re.I)),
]

# Straight and curly double quotes. Single quotes are left alone: they are
# apostrophes far more often than quotation marks ("Emaar's").
_QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”')
_URL = re.compile(r"https?://[^\s)\]}>\"',]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_TREND_METRIC = re.compile(
    r"\bvolume\s+index\b|\bgrowth\s+index\b|\bquadrant\b|\bsource\s+mix\b|"
    r"\bplatform\s+mix\b", re.I)
_POST_ATTRIBUTION = re.compile(r"@\w+|'s\s+post\b|\bposted\b", re.I)


def _is_trend_only(paragraph: str) -> bool:
    return (bool(_TREND_METRIC.search(paragraph))
            and not _QUOTED.search(paragraph)
            and not _POST_ATTRIBUTION.search(paragraph))


FAKE_QUOTE = "is put in quotation marks, but no post the tools returned says it"


def bounded_evidence(context: str, payloads: list[str], limit: int = 80_000) -> str:
    """Keep complete evidence sections within a hard verifier-context limit.

    Context is considered first, followed by exact serialized tool payloads in
    execution order. A section is never cut mid-record or into malformed JSON.
    """
    marker = "[evidence truncated]"
    sections: list[str] = []
    truncated = False
    for item in [context, *payloads]:
        item = (item or "").strip()
        if not item:
            continue
        candidate = "\n\n".join([*sections, item])
        with_marker = "\n\n".join([candidate, marker])
        if len(with_marker) > limit:
            truncated = True
            break
        sections.append(item)
    if truncated:
        sections.append(marker)
    return "\n\n".join(sections)


def compose_persona_answer(persona: dict, retrieval_result: dict,
                           limit: int = 3) -> tuple[str, dict]:
    """Compose a stable persona answer from exact retrieved post records.

    This is the fail-safe path for property evaluations. It performs no model
    synthesis: record order is preserved, excerpts remain exact source text,
    and every excerpt carries the URL stored on that same record.
    """
    records = []
    seen_urls = set()
    data = retrieval_result.get("data") if isinstance(retrieval_result, dict) else None
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        caption = " ".join(str(row.get("caption") or "").split())
        url = str(row.get("post_url") or "").strip()
        if not caption or not _URL.fullmatch(url) or url in seen_urls:
            continue
        seen_urls.add(url)
        records.append(row | {"caption": caption, "post_url": url})
        if len(records) >= limit:
            break
    if not records:
        raise AnswerVerificationError("persona retrieval returned no citable records")

    article = "an" if persona["name"][0].lower() in "aeiou" else "a"
    # No filler about how the records were selected: that is an implementation
    # detail, not a finding. The opening clause hands straight to the evidence.
    sentences = [f"For {article} {persona['name']}, the posts show:"]
    record_ids = []
    for row in records:
        excerpt = row["caption"][:280]
        if len(row["caption"]) > 280 and " " in excerpt:
            excerpt = excerpt.rsplit(" ", 1)[0] + "…"
        # Keep the outer quotation unambiguous. The retained words are still an
        # exact prefix of the retrieved caption after whitespace normalization.
        for quote in ('"', "“", "”"):
            excerpt = excerpt.split(quote, 1)[0].rstrip()
        if not excerpt:
            continue
        author = str(row.get("author_username") or "source").lstrip("@")
        platform = str(row.get("platform") or "social").title()
        sentences.append(
            f'{platform} @{author} posted: "{excerpt}" ({row["post_url"]}).')
        record_ids.append(
            f'{row.get("platform", "unknown")}:{row.get("post_id", "unknown")}')

    gaps = ", ".join(persona["prioritise"][:3])
    answer = " ".join(sentences) + "\n\n" + (
        "The data does not cover independent verification or measurements for "
        f"{gaps}; the excerpts above remain claims made by their sources.")
    scaffold = sentences[0] + "\n\n" + answer.split("\n\n", 1)[1]
    if find_violations(scaffold):
        raise AnswerVerificationError("deterministic persona composition was not safe")
    return answer, {"status": "composed", "records": record_ids}


def _normalise(text: str) -> str:
    """Lower-case words only, so a quote matches its source through
    punctuation, curly apostrophes and JSON escapes."""
    text = text.replace("’", "'").replace("‘", "'")
    return " ".join(re.sub(r"[^\w\s']", " ", text.lower()).split())


def find_violations(text: str, sources: str | None = None) -> list[dict]:
    """Flagged phrases in the answer's own voice, in reading order.

    Quoted text is a post's own words and passes - but only when the post
    really said it. Measured: asked to fix "an attractive option", the rewrite
    put it in quotation marks and credited it to "posts"; no post contained
    it. With sources given (the evidence the model saw), a quotation is
    exempt only if its words are found there. Without sources every quotation
    is taken on trust, which is only safe for text that has no model in it.
    """
    text = text or ""
    known = _normalise(sources) if sources is not None else None
    plain = list(text)
    fake: list[tuple[int, int]] = []
    for m in _QUOTED.finditer(text):
        words = _normalise(m.group(0)[1:-1])
        if known is None or (words and words in known):
            plain[m.start():m.end()] = " " * (m.end() - m.start())
        else:
            fake.append((m.start(), m.end()))
    plain = "".join(plain)
    found = []
    for kind, why, pattern in PATTERNS:
        for m in pattern.finditer(plain):
            quoted = any(s <= m.start() < e for s, e in fake)
            start = text.rfind("\n", 0, m.start()) + 1
            end = text.find("\n", m.end())
            found.append({"kind": kind, "why": FAKE_QUOTE if quoted else why,
                          "phrase": text[m.start():m.end()], "at": m.start(),
                          "line": text[start:end if end != -1 else None]})
    found.sort(key=lambda v: v["at"])
    return found


def _acceptable(original: str, revised: str) -> bool:
    """A rewrite may drop or reword phrases; it may not add links or content
    the original did not have, or throw most of the answer away."""
    if not revised or not revised.strip():
        return False
    if not set(_URL.findall(revised)) <= set(_URL.findall(original)):
        return False
    return len(revised) >= MIN_KEPT * len(original)


# "Emaar, a leading developer, posts about X": the aside is the leak, the rest
# is a finding. Cut to the next comma or the end of the clause.
_DESCRIPTOR_ASIDE = re.compile(
    rf",\s*(?:an?|the)\s+(?:{_STANDING})\s+{_ACTOR}\b[^,.;\n]*,?", re.I)


def _trim(text: str, sources: str | None = None) -> str:
    """Remove flagged phrasing that survived the rewrites.

    A descriptor set off by commas is cut on its own. Anything else takes its
    sentence with it. Worked line by line so markdown structure - headings,
    bullets, links - survives; a line left empty by the removal goes with it.
    """
    text = _DESCRIPTOR_ASIDE.sub(
        lambda m: m.group(0) if _QUOTED.search(m.group(0)) else "", text)
    lines = []
    for line in text.split("\n"):
        if not find_violations(line, sources):
            lines.append(line)
            continue
        bullet = re.match(r"^(\s*(?:[-*+]|\d+[.)])\s+)", line)
        prefix = bullet.group(1) if bullet else ""
        kept = [s for s in _SENTENCE.split(line[len(prefix):])
                if not find_violations(s, sources)]
        body = " ".join(kept).strip()
        if body:
            lines.append(prefix + body)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def enforce(answer: str, rewrite: Callable[[str, list[dict]], str],
            sources: str | None = None) -> tuple[str, dict]:
    """The answer with no flagged phrasing left, and what was done to it.

    sources is the evidence the model was given; see find_violations.
    """
    violations = find_violations(answer, sources)
    report = {"flagged": [v["phrase"] for v in violations], "action": None, "attempts": 0}
    if not violations:
        return answer, report
    current = answer
    for attempt in range(1, MAX_REWRITES + 1):
        report["attempts"] = attempt
        try:
            revised = rewrite(current, violations)
        except Exception:
            logger.exception("answer rewrite failed")
            break
        if not _acceptable(answer, revised):
            logger.warning("rewrite refused (added links or dropped content)")
            continue
        current = revised
        violations = find_violations(current, sources)
        if not violations:
            report["action"] = "rewritten"
            return current, report
    report["action"] = "trimmed"
    report["trimmed"] = [v["phrase"] for v in find_violations(current, sources)]
    return _trim(current, sources), report


REWRITE_INSTRUCTION = """\
You edit an answer written by a property-market assistant. The answer must \
report what social posts say; it must never judge a place, project or \
investment, describe a developer's standing, or advise the reader.

Change only the flagged phrases listed by the user. For each one, remove the \
judgement, rewording the sentence as little as possible so it still reads \
naturally. Name a developer by its name alone. Do not move a flagged phrase \
into quotation marks or credit it to "posts": you cannot see the posts, and a \
quotation no post contains is checked and rejected.

Keep every other sentence, figure, trend name, handle, link and all markdown \
exactly as it is. Add nothing. Return only the edited answer."""


def rewrite_with_model(answer: str, violations: list[dict]) -> str:
    """One targeted edit by the assistant's own model, no tools."""
    from services.trends_real_estate_service.app.assistant.agent import _client
    from services.trends_real_estate_service.app.core.config import get_settings
    flagged = "\n".join(f'- "{v["phrase"]}" - {v["why"]}' for v in violations)
    resp = _client().chat.completions.create(
        model=get_settings().ASSISTANT_MODEL, temperature=get_settings().ASSISTANT_TEMPERATURE,
        messages=[{"role": "system", "content": REWRITE_INSTRUCTION},
                  {"role": "user", "content": f"Flagged phrases:\n{flagged}\n\n"
                                              f"Answer:\n<<<\n{answer}\n>>>"}])
    text = (resp.choices[0].message.content or "").strip()
    if text.startswith("<<<"):
        text = text[3:]
    if text.endswith(">>>"):
        text = text[:-3]
    return text.strip()


SOURCE_REVIEW_INSTRUCTION = """\
You are the final source verifier for a property-market assistant. Return one
JSON object only with keys: status ("pass" or "revised"), answer (the complete
answer safe to show), and violations (a list of objects with category, claim,
and reason).

Check every claim against only the supplied evidence. Do not use memory or
general knowledge. A claim derived from a social post must name its author or
source and include one of that evidence's URLs in the same paragraph. Prices,
yields, returns, payment plans, distances, timelines, amenities, legal rights,
visa eligibility and similar claims must stay explicitly attributed to their
source unless the evidence identifies them as independently measured data.

Developer mentions do not prove reputation, credibility, trust, quality, scale
or track record. Amenities, parks, wildlife, location and marketing sentiment
do not prove safety, suitability, convenience, demand or investment quality.
Do not make a recommendation, verdict, forecast, unsupported inference,
professional-referral suggestion or invented next step. Trend metrics may be
reported as platform measurements, but conversation volume and source mix are
not market demand.

Before returning JSON, scan the proposed answer and remove every developer
standing label, including prominent, reputable, well-known, renowned, leading,
major, established, top, trusted, respected, premier, biggest or largest
developer/player/brand/name, and every "strong/proven/established track
record" claim. Also remove verdict language such as attractive option,
compelling, promising, worth considering, good investment, strong potential,
or advice to consult, conduct due diligence, buy, invest or avoid. Attribution
does not make these inferences acceptable; report only what the evidence
literally establishes.

If format_required is true: return exactly two concise plain paragraphs with
no headings or bulleted/numbered list. Start the first paragraph by copying
the supplied required_opening string verbatim, then continue the sentence.
Put every evidence-backed finding in this first paragraph and include exact
URLs from allowed_source_urls beside the claims they support; do not replace
a URL with an author handle. Delete a claim rather than keep it uncited or
infer what it means for the buyer. The second and final paragraph must begin
"The data does not cover", name the material gaps, and have nothing after it.
A priority without evidence belongs only in that final gap. If the draft
already meets this exact format and all rules, return status "pass" and the
draft unchanged. Otherwise return status "revised" and rewrite it into this
format.

If format_required is false: the persona brief tells the model to answer this
question exactly as it would with no persona, so there is no required_opening
and no closing coverage-gap paragraph to enforce. Keep the draft's own
structure and wording. Apply every rule above - remove standing labels,
verdicts, advice and unsupported inference - but do not add a persona
opening, reshape it into two paragraphs, or add a coverage-gap paragraph that
was not already there.

Use only URLs appearing verbatim in the supplied evidence in either case.
Missing evidence means remove the claim or name the gap; it never permits
inference."""


def review_with_sources(*, answer: str, question: str, persona: dict,
                        sources: str, require_persona_format: bool = True) -> dict:
    """Ask the configured model for one evidence-bound structured review."""
    from services.trends_real_estate_service.app.assistant.agent import _client
    from services.trends_real_estate_service.app.core.config import get_settings

    article = "an" if persona["name"][0].lower() in "aeiou" else "a"
    payload = {
        "question": question,
        "persona": {
            "persona_id": persona.get("persona_id"),
            "name": persona.get("name"),
            "mindset": persona.get("mindset"),
            "prioritise": persona.get("prioritise"),
            "response_behaviour": persona.get("response_behaviour"),
        },
        "draft_answer": answer,
        "format_required": require_persona_format,
        "required_opening": (f"For {article} {persona['name']}, the posts show"
                             if require_persona_format else None),
        "allowed_source_urls": sorted(set(_URL.findall(sources or ""))),
        "evidence": sources,
    }
    response = _client().chat.completions.create(
        model=get_settings().ASSISTANT_MODEL,
        temperature=get_settings().ASSISTANT_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SOURCE_REVIEW_INSTRUCTION},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("review response is not an object")
    return result


def verify_persona_answer(answer: str, *, question: str, persona: dict,
                          sources: str,
                          require_persona_format: bool = True,
                          reviewer: Callable[..., dict] = review_with_sources,
                          rewriter: Callable[[str, list[dict]], str] = rewrite_with_model,
                          ) -> tuple[str, dict]:
    """Release only a well-shaped, locally validated source review."""
    revised = answer
    result = None
    # The second pass reviews the verifier's own revision. Live evaluation
    # showed that a single pass could correctly identify one unsupported claim
    # while leaving a different inference in its rewritten answer.
    for _ in range(2):
        try:
            result = reviewer(answer=revised, question=question, persona=persona,
                              sources=sources, require_persona_format=require_persona_format)
        except Exception as exc:
            raise AnswerVerificationError("persona answer review failed") from exc
        if not isinstance(result, dict):
            raise AnswerVerificationError("reviewer returned invalid JSON")
        if result.get("status") not in {"pass", "revised"}:
            raise AnswerVerificationError("invalid reviewer status")
        candidate = result.get("answer")
        if not isinstance(candidate, str) or not candidate.strip():
            raise AnswerVerificationError("reviewer returned no answer")
        revised = candidate.strip()
    source_urls = set(_URL.findall(sources or ""))
    answer_urls = set(_URL.findall(revised))
    if not answer_urls <= source_urls:
        raise AnswerVerificationError("reviewer introduced a source URL")
    deterministic = find_violations(revised, sources)
    flagged = [v["phrase"] for v in deterministic]
    cleanup = None
    if deterministic:
        revised, cleanup = enforce(revised, rewriter, sources)
        if not revised or find_violations(revised, sources):
            raise AnswerVerificationError(
                "reviewer left a deterministic violation that could not be removed")
    if require_persona_format:
        article = "an" if persona["name"][0].lower() in "aeiou" else "a"
        opening = re.compile(
            rf"^For {article} {re.escape(persona['name'])}, the posts show")
        if not opening.match(revised):
            raise AnswerVerificationError("reviewer omitted the persona opening")
        if "does not cover" not in revised.lower()[-600:]:
            raise AnswerVerificationError("reviewer omitted the coverage gap")
        if source_urls and not answer_urls and not _is_trend_only(revised):
            raise AnswerVerificationError("reviewer returned no source URL")
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", revised) if p.strip()]
        if not paragraphs or not paragraphs[-1].lower().startswith("the data does not cover"):
            raise AnswerVerificationError("reviewer omitted the final coverage gap")
        if source_urls and any(not _URL.search(paragraph) and not _is_trend_only(paragraph)
                               for paragraph in paragraphs[:-1]):
            raise AnswerVerificationError("reviewer returned an uncited evidence paragraph")
    violations = result.get("violations") or []
    if not isinstance(violations, list):
        raise AnswerVerificationError("reviewer returned invalid violations")
    report = {"status": "revised" if flagged else result["status"],
              "violations": violations}
    if flagged:
        report["deterministic_trimmed"] = flagged
        report["deterministic_action"] = cleanup["action"]
    return revised, report


GENERAL_REVIEW_INSTRUCTION = """\
You verify an answer written by a GCC property-market intelligence assistant
against the evidence it was given (tool results and retrieved context). Return
one JSON object only: {"status": "pass" or "revised", "answer": the complete
answer safe to show, "removed": [{"claim": ..., "reason": ...}]}.

Rules:
- Every developer, partner brand, project, trend name, number, percentage and
  date stated as fact must appear in the evidence. Remove a claim or sentence
  the evidence does not support. Never replace it with something from memory.
- A figure must belong to the trend or developer it is attached to in the
  evidence. Figures moved between trends are wrong: fix them from the evidence
  or remove them.
- "Developer X partners with brand Y" needs evidence text that names both.
- A developer, project or trend must not be placed in a country the evidence
  does not give it (developer_country, country, trend_market). A trend whose
  market is "all markets" is not a UAE or Saudi trend; developers from another
  country must not be described as being in the country the user asked about.
- Every claim you list in "removed" must be gone from the answer you return.
- Remove list items, trends, developers and example posts that are not about
  the topic of the question (given as [topic: ...] when known), even if they
  appear in the evidence or a tool returned them: a store
  opening under flexible workspaces, furniture under branded residences,
  construction progress under sustainability, a developer listed with no
  partner under "which brands do they partner with".
- Text under the heading "Background:" may explain a
  concept from general knowledge, but must not state market facts, figures or
  claims about specific developers, projects or trends.
- Statements about what the assistant searched, tried or looked for must match
  TOOL CALLS MADE THIS TURN at the top of the evidence. Remove any that do not.
- If a tool result says WEAK MATCH and the answer presents those trends as
  being about the topic, revise it to say no trend in the data closely covers
  the topic and describe them only as loosely related, or drop them.
- Keep everything else - structure, markdown, wording, links - unchanged. Add no
  new facts. Use only URLs that appear verbatim in the evidence.
- If everything is supported, return status "pass" and the answer unchanged."""


class RemovedClaim(BaseModel):
    claim: str = ""
    reason: str = ""


class GeneralReview(BaseModel):
    """The answer checker's verdict on one general answer."""

    status: Literal["pass", "revised"]
    answer: str = Field(min_length=1)
    removed: list[RemovedClaim] = Field(default_factory=list)


def review_general(*, answer: str, question: str, sources: str) -> dict:
    from services.trends_real_estate_service.app.assistant.agent import _client
    from services.trends_real_estate_service.app.core.config import get_settings
    response = _client().chat.completions.create(
        model=get_settings().ASSISTANT_MODEL,
        temperature=get_settings().ASSISTANT_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": GENERAL_REVIEW_INSTRUCTION},
            {"role": "user", "content": json.dumps(
                {"question": question, "draft_answer": answer, "evidence": sources},
                ensure_ascii=False)},
        ],
    )
    result = json.loads((response.choices[0].message.content or "").strip())
    if not isinstance(result, dict):
        raise ValueError("review response is not an object")
    return result


def verify_general_answer(answer: str, *, question: str, sources: str,
                          topic: str | None = None,
                          reviewer: Callable[..., dict] | None = None) -> tuple[str, dict]:
    """The answer with unsupported claims removed, and what was removed.

    Fails open: if the review cannot run or returns something unusable, the
    draft is released and the report says so.
    """
    reviewer = reviewer or review_general
    if topic:
        question = f"{question} [topic: {topic}]"
    try:
        review = GeneralReview.model_validate(
            reviewer(answer=answer, question=question, sources=sources))
        if review.removed and review.answer.strip() == answer.strip():
            listed = "\n".join(f"- {r.claim}" for r in review.removed)
            review = GeneralReview.model_validate(reviewer(
                answer=answer, question=question,
                sources=sources + "\n\nYOU FLAGGED THESE CLAIMS AS UNSUPPORTED BUT LEFT "
                                  "THEM IN. Remove or correct each one:\n" + listed))
    except ValidationError:
        logger.warning("general answer review did not validate; draft kept", exc_info=True)
        return answer, {"status": "unchecked", "removed": []}
    except Exception:
        logger.exception("general answer review failed")
        return answer, {"status": "unchecked", "removed": []}
    revised = review.answer
    removed = [r.model_dump() for r in review.removed]
    if not set(_URL.findall(revised)) <= set(_URL.findall(sources or "")) | set(_URL.findall(answer)):
        logger.warning("general review introduced a URL; draft kept")
        return answer, {"status": "unchecked", "removed": []}
    if revised.strip() == answer.strip():
        return answer, {"status": "pass", "removed": []}
    return revised.strip(), {"status": "revised", "removed": removed}


REPEAT_RATIO = 0.8


def is_repeat(answer: str, previous: str) -> bool:
    if not answer.strip() or not previous.strip():
        return False
    return difflib.SequenceMatcher(None, answer.strip(), previous.strip()).ratio() >= REPEAT_RATIO


NO_REPEAT_INSTRUCTION = """\
You edit a reply from a property-market assistant to its user. The reply below
repeats the assistant's previous answer almost word for word, which reads as
ignoring the user. Rewrite it so it directly answers the user's latest
question, briefly and in the assistant's own voice:
- Open with the direct answer to exactly what was asked now. For "which X?",
  give a short list of the X with nothing else around each item.
- Do not restate the previous answer; refer to it in one short clause at most.
- Keep only facts, names, figures and links that are in the reply. Add nothing.
- Never mention a draft, a rewrite, instructions or "the reply above".
Return only the rewritten reply."""


def answer_without_repeating(answer: str, *, question: str, previous: str) -> str:
    from services.trends_real_estate_service.app.assistant.agent import _client
    from services.trends_real_estate_service.app.core.config import get_settings
    try:
        resp = _client().chat.completions.create(
            model=get_settings().ASSISTANT_MODEL, temperature=get_settings().ASSISTANT_TEMPERATURE,
            messages=[{"role": "system", "content": NO_REPEAT_INSTRUCTION},
                      {"role": "user", "content": f"Latest question: {question}\n\n"
                                                  f"Previous answer:\n<<<\n{previous}\n>>>\n\n"
                                                  f"Draft:\n<<<\n{answer}\n>>>"}])
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("repeat rewrite failed; draft kept")
        return answer
    if not text or not set(_URL.findall(text)) <= set(_URL.findall(answer)):
        return answer
    return text
