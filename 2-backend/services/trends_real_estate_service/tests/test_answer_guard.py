"""The answer guard: verdicts and developer descriptors never reach the reader.

Every phrase in the "leaks" list below came out of a real persona answer. Prompt
rules alone let them through in roughly a quarter of persona answers, however
they were worded - measured by A/B on the same questions - because the model
reaches for them from its own knowledge. So the rule is enforced in code.
"""
import asyncio

import pytest

from services.trends_real_estate_service.app.assistant import graph, guard
from services.trends_real_estate_service.app.personas import definitions

LEAKS = [
    ("Emaar, a prominent developer, is frequently mentioned.", "descriptor"),
    ("The area is developed by Emaar, a major player in Dubai's real estate market.", "descriptor"),
    ("The posts frequently mention Emaar, a well-known developer in Dubai.", "descriptor"),
    ("This makes it an attractive option for investors looking for yields.", "verdict"),
    ("For a Luxury Buyer, Dubai Creek Harbour presents a compelling proposition.", "verdict"),
    ("The posts show that it is positioned as a high-value investment opportunity.", "verdict"),
    ("The area is seen as a promising location for growth.", "verdict"),
    ("For investment advice, I recommend consulting a financial advisor.", "advice"),
    ("Emaar's mentions suggest a level of credibility and experience.", "inference"),
    ("The waterfront setting might appeal to first-time buyers.", "inference"),
    ("Ongoing development could imply construction timeline risks.", "inference"),
    ("This is a positive aspect for residents.", "verdict"),
    ("The post makes this a vibrant and appealing community.", "verdict"),
    ("First-time buyers should consider construction timelines.", "advice"),
    ("The positioning indicates higher price points.", "inference"),
    ("This suggests good connectivity.", "inference"),
    ("The setting could be attractive to families.", "inference"),
    ("That would be beneficial for commuting.", "verdict"),
    ("This is indicating good connectivity.", "inference"),
    ("The volume is suggesting premium amenities.", "inference"),
    ("This would require further investigation through visits.", "advice"),
    ("This could enhance its appeal to investors.", "inference"),
    ("The parks create a family-friendly environment.", "inference"),
    ("It is a competitive option with potential for future growth.", "verdict"),
    ("The volume proves a strong market conversation and rental demand.", "inference"),
    ("The posts suggest a safe and welcoming, well-developed area.", "inference"),
    ("It is a significant development with easy access.", "verdict"),
    ("The watchlist shows potential interest and future growth potential.", "inference"),
    ("The distances highlight good connectivity and relevance.", "inference"),
]

CLEAN = [
    "The development is 10 minutes from major landmarks such as Burj Khalifa.",
    "Waterfront Luxury Residences is a mainstream trend with a volume index of 100.",
    "royaloasisrealestate's post says it has 700,000 sqm of parks, leading to the creek.",
    "The data does not cover school ratings, service charges or safety statistics.",
    "**Investment Potential**: posts describe payment plans and handover dates.",
    "It is unclear whether you should buy; the data speaks to what people post.",
]


@pytest.mark.parametrize("text,kind", LEAKS)
def test_every_measured_leak_is_caught(text, kind):
    found = guard.find_violations(text)
    assert found, f"missed: {text}"
    assert found[0]["kind"] == kind


@pytest.mark.parametrize("text", CLEAN)
def test_ordinary_analysis_is_not_flagged(text):
    assert guard.find_violations(text) == []


def test_a_posts_own_words_in_quotes_are_allowed():
    """Attributing a claim is the fix, so a quoted claim must pass."""
    text = ('@azcorealestatebrokersllc calls it "a high-value, future-forward investment '
            'opportunity" and “an attractive option for investors”.')
    assert guard.find_violations(text) == []


SOURCES = ('{"caption": "Creek Harbour stands out as a high-value, future-forward investment '
           'opportunity in Dubai\\u2019s evolving market"}')


def test_a_quote_counts_only_if_a_post_actually_says_it():
    """Measured: the rewrite turned "an attractive option" into '"an attractive
    option" according to posts' - no post says it. Quotation marks exempt a
    phrase only when the quoted words are in what the tools returned."""
    real = 'Posts call it "a high-value, future-forward investment opportunity".'
    fake = 'Posts describe it as "an attractive option" for investors.'
    assert guard.find_violations(real, sources=SOURCES) == []
    found = guard.find_violations(fake, sources=SOURCES)
    assert found and found[0]["kind"] == "verdict"
    assert "no post" in found[0]["why"]


def test_a_rewrite_that_launders_a_verdict_into_a_fake_quote_is_not_accepted():
    text = "This makes it an attractive option for investors. Parks cover 700,000 sqm."
    out, report = guard.enforce(
        text, rewrite=lambda a, v: 'Posts call it "an attractive option" for investors. '
                                   "Parks cover 700,000 sqm.",
        sources=SOURCES)
    assert "attractive" not in out
    assert "700,000 sqm" in out and report["action"] == "trimmed"


def test_a_clean_answer_is_returned_untouched_without_a_rewrite():
    calls = []
    text = "For a Family Home Seeker, the posts show 700,000 sqm of parks."
    out, report = guard.enforce(text, rewrite=lambda a, v: calls.append(a) or a)
    assert out == text and calls == [] and report["action"] is None


def test_a_leak_is_rewritten_and_the_rewrite_is_rechecked():
    text = "Emaar, a prominent developer, builds here. Parks cover 700,000 sqm."
    seen = []

    def rewrite(answer, violations):
        seen.append([v["phrase"] for v in violations])
        return "Emaar builds here. Parks cover 700,000 sqm."
    out, report = guard.enforce(text, rewrite=rewrite)
    assert out == "Emaar builds here. Parks cover 700,000 sqm."
    assert report["action"] == "rewritten" and report["attempts"] == 1
    assert any("prominent developer" in p for p in seen[0]), "the model is told what to fix"


def test_when_rewrites_keep_leaking_the_offending_sentence_is_removed():
    """The guarantee: nothing flagged ships, whatever the model does."""
    text = ("For a Resident Investor, the posts show payment plans.\n\n"
            "- This makes it an attractive option for investors.\n"
            "- The data does not cover yields.")
    out, report = guard.enforce(text, rewrite=lambda a, v: a)
    assert guard.find_violations(out) == []
    assert "payment plans" in out and "does not cover yields" in out
    assert report["action"] == "trimmed"


def test_a_rewrite_that_invents_a_link_is_rejected():
    text = "Emaar, a leading developer, posts about Dubai Hills (https://instagram.com/p/A)."

    def rewrite(answer, violations):
        return "Emaar posts about Dubai Hills (https://instagram.com/p/A, https://example.com/x)."
    out, report = guard.enforce(text, rewrite=rewrite)
    assert "example.com" not in out
    assert guard.find_violations(out) == []


def test_a_descriptor_aside_is_cut_without_losing_the_sentence():
    """"Emaar, a leading developer, posts about X" carries a real finding; only
    the aside is the leak."""
    out, report = guard.enforce(
        "Emaar, a leading developer, posts about Dubai Hills (https://instagram.com/p/A).",
        rewrite=lambda a, v: a)
    assert out == "Emaar posts about Dubai Hills (https://instagram.com/p/A)."
    assert report["action"] == "trimmed"


def test_a_failing_rewrite_never_breaks_the_answer():
    def rewrite(answer, violations):
        raise RuntimeError("model unavailable")
    out, report = guard.enforce("Posts show parks. It is a promising area.", rewrite=rewrite)
    assert out == "Posts show parks."
    assert report["action"] == "trimmed"


def test_bounded_evidence_keeps_context_and_whole_payloads():
    out = guard.bounded_evidence("CTX", ["A" * 10, "B" * 10], limit=45)
    assert out.startswith("CTX")
    assert "A" * 10 in out
    assert "B" * 10 not in out
    assert "[evidence truncated]" in out


@pytest.mark.parametrize("claim", [
    "Golden Visa eligibility is likely part of the broader conversation.",
    "Emaar's involvement is reassuring regarding quality and reliability.",
    "The parks indicate that this is a safe environment for families.",
    "The area offers strong rental yields and capital appreciation.",
])
def test_source_aware_review_removes_live_unsupported_claims(claim):
    revised = ("For an International Investor, the posts show only a reference to parks "
               "(https://example.test/p/1).\n\n"
               "The data does not cover the unsupported claim.")
    out, report = guard.verify_persona_answer(
        claim,
        question="What do posts show about Creek Harbour?",
        persona=definitions.get("international-investor"),
        sources='{"author":"a","post_url":"https://example.test/p/1","caption":"parks"}',
        reviewer=lambda **kwargs: {
            "status": "revised",
            "answer": revised,
            "violations": [{"category": "unsupported", "claim": claim,
                            "reason": "absent"}],
        },
    )
    assert out == revised
    assert report["status"] == "revised"


PERSONA = definitions.get("international-investor")


def _verify_with(result, sources="https://source.test/p/1"):
    return guard.verify_persona_answer(
        "Draft", question="Question", persona=PERSONA, sources=sources,
        reviewer=lambda **kwargs: result,
        rewriter=lambda answer, violations: answer,
    )


@pytest.mark.parametrize("result", [
    "not an object",
    {"status": "unknown", "answer": "Answer"},
    {"status": "revised", "answer": ""},
])
def test_invalid_reviewer_shapes_fail_closed(result):
    with pytest.raises(guard.AnswerVerificationError):
        _verify_with(result)


def test_reviewer_cannot_introduce_a_url():
    result = {"status": "revised",
              "answer": "For an International Investor, the posts show a claim "
                        "(https://invented.test/x). Data does not cover prices.",
              "violations": []}
    with pytest.raises(guard.AnswerVerificationError, match="source URL"):
        _verify_with(result, sources="https://source.test/p/1")


def test_reviewer_must_include_a_retrieved_source_url():
    result = {"status": "revised",
              "answer": "For an International Investor, the posts show parks. "
                        "The data does not cover safety statistics.",
              "violations": []}
    with pytest.raises(guard.AnswerVerificationError, match="no source URL"):
        _verify_with(result)


def test_each_evidence_paragraph_must_include_a_retrieved_source_url():
    answer = ("For an International Investor, the posts show parks "
              "(https://source.test/p/1).\n\n"
              "Another paragraph makes an uncited post claim.\n\n"
              "The data does not cover safety statistics.")
    result = {"status": "revised", "answer": answer, "violations": []}
    with pytest.raises(guard.AnswerVerificationError, match="uncited evidence paragraph"):
        _verify_with(result)


def test_reviewer_must_use_the_persona_opening():
    result = {"status": "pass",
              "answer": "A grounded paragraph. The data does not cover prices.",
              "violations": []}
    with pytest.raises(guard.AnswerVerificationError, match="persona opening"):
        _verify_with(result)


def test_reviewer_must_end_with_a_coverage_gap():
    result = {"status": "pass",
              "answer": "For an International Investor, the posts show a grounded paragraph.",
              "violations": []}
    with pytest.raises(guard.AnswerVerificationError, match="coverage gap"):
        _verify_with(result)


def test_reviewer_deterministically_removes_a_residual_violation():
    result = {"status": "pass",
              "answer": "For an International Investor, the posts show parks "
                        "(https://source.test/p/1). It is a promising area.\n\n"
                        "The data does not cover prices.",
              "violations": []}
    out, report = _verify_with(result)
    assert "promising" not in out
    assert out.startswith("For an International Investor")
    assert out.endswith("The data does not cover prices.")
    assert report["status"] == "revised"
    assert report["deterministic_trimmed"] == ["promising"]


def test_a_clean_source_review_passes_unchanged():
    answer = ("For an International Investor, the posts show parks "
              "(https://source.test/p/1).\n\n"
              "The data does not cover safety statistics.")
    out, report = _verify_with(
        {"status": "pass", "answer": answer, "violations": []})
    assert out == answer
    assert report == {"status": "pass", "violations": []}


def test_relaxed_format_accepts_a_plain_answer_with_no_persona_opening():
    result = {"status": "pass", "answer": "Three trends are breaking out this month.",
              "violations": []}
    out, report = guard.verify_persona_answer(
        "Draft", question="Which trends are breaking out?", persona=PERSONA,
        sources="https://source.test/p/1", require_persona_format=False,
        reviewer=lambda **kwargs: result, rewriter=lambda answer, violations: answer)
    assert out == "Three trends are breaking out this month."
    assert report["status"] == "pass"


def test_relaxed_format_still_removes_a_deterministic_violation():
    result = {"status": "pass",
              "answer": "Three trends are breaking out. It is a promising area.",
              "violations": []}
    out, _ = guard.verify_persona_answer(
        "Draft", question="Which trends are breaking out?", persona=PERSONA,
        sources="", require_persona_format=False,
        reviewer=lambda **kwargs: result, rewriter=lambda answer, violations: answer)
    assert "promising" not in out
    assert "Three trends are breaking out" in out


def test_relaxed_format_still_rejects_an_invented_url():
    result = {"status": "pass",
              "answer": "Three trends are breaking out (https://invented.test/x).",
              "violations": []}
    with pytest.raises(guard.AnswerVerificationError, match="source URL"):
        guard.verify_persona_answer(
            "Draft", question="Which trends are breaking out?", persona=PERSONA,
            sources="https://source.test/p/1", require_persona_format=False,
            reviewer=lambda **kwargs: result, rewriter=lambda answer, violations: answer)


def test_relaxed_format_is_passed_through_to_the_reviewer():
    seen = {}

    def reviewer(**kwargs):
        seen.update(kwargs)
        return {"status": "pass", "answer": "Plain answer.", "violations": []}
    guard.verify_persona_answer(
        "Draft", question="Which trends are breaking out?", persona=PERSONA,
        sources="", require_persona_format=False, reviewer=reviewer,
        rewriter=lambda answer, violations: answer)
    assert seen["require_persona_format"] is False


def test_trend_only_claims_do_not_require_a_source_url():
    answer = ("For an International Investor, the posts show that the UAE "
              "trend has a volume index of 80 and a growth index of 40, "
              "while the Saudi trend has a source mix dominated by brand "
              "posts.\n\n"
              "The data does not cover yield indicators.")
    result = {"status": "pass", "answer": answer, "violations": []}
    out, report = _verify_with(result, sources="https://source.test/p/1")
    assert out == answer
    assert report["status"] == "pass"


def test_source_review_checks_its_own_revision_before_release():
    unsafe = ("For an International Investor, the posts show parks establish family "
              "suitability (https://source.test/p/1).\n\n"
              "The data does not cover safety statistics.")
    safe = ("For an International Investor, the posts show a post about parks "
            "(https://source.test/p/1).\n\n"
            "The data does not cover family suitability or safety statistics.")
    results = iter([
        {"status": "revised", "answer": unsafe, "violations": []},
        {"status": "revised", "answer": safe,
         "violations": [{"category": "unsupported", "claim": "family suitability",
                         "reason": "not established"}]},
    ])
    calls = []

    def reviewer(**kwargs):
        calls.append(kwargs["answer"])
        return next(results)

    out, _ = guard.verify_persona_answer(
        "Draft", question="Question", persona=PERSONA,
        sources="https://source.test/p/1", reviewer=reviewer,
        rewriter=lambda answer, violations: answer)
    assert out == safe
    assert calls == ["Draft", unsafe]


def test_deterministic_composer_uses_only_exact_persona_records():
    result = {"ok": True, "data": [
        {"platform": "instagram", "post_id": "p1", "author_username": "familyhomes",
         "caption": "Creek Harbour includes parks and open spaces for residents.",
         "post_url": "https://source.test/p/1"},
        {"platform": "tiktok", "post_id": "p2", "author_username": "cityhomes",
         "caption": "The post describes waterfront apartments near the creek.",
         "post_url": "https://source.test/p/2"},
    ]}
    persona = definitions.get("family-home-seeker")
    first, report = guard.compose_persona_answer(persona, result)
    second, _ = guard.compose_persona_answer(persona, result)
    assert first == second
    assert first.startswith("For a Family Home Seeker, the posts show")
    assert "parks and open spaces" in first
    assert "https://source.test/p/1" in first
    assert first.split("\n\n")[-1].startswith("The data does not cover")
    assert guard.find_violations(first, sources=str(result)) == []
    assert report == {"status": "composed", "records": ["instagram:p1", "tiktok:p2"]}


def test_deterministic_composer_fails_without_citable_records():
    with pytest.raises(guard.AnswerVerificationError, match="citable"):
        guard.compose_persona_answer(
            definitions.get("luxury-buyer"),
            {"ok": True, "data": [{"caption": "No URL"}]})


class _Chunk:
    def __init__(self, text):
        self.content = text


class _StreamingAgent:
    def __init__(self, text):
        self.text = text

    async def astream_events(self, payload, config=None, version=None):
        for word in self.text.split(" "):
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(word + " ")}}


QUESTION = "What about Dubai Creek Harbour?"


def _events(monkeypatch, persona, text):
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: _StreamingAgent(text))

    async def collect():
        return [e async for e in graph.astream(QUESTION, "", [], embed_query=None,
                                               persona=persona)]
    return asyncio.run(collect())


def test_a_persona_answer_is_held_until_it_has_been_checked(monkeypatch):
    """Streamed token by token, a leak would be on screen before it could be
    removed. Persona answers arrive once, already checked."""
    safe = ("For a Luxury Buyer, the posts show villas.\n\n"
            "The data does not cover independent quality assessments.")
    monkeypatch.setattr(
        graph.guard, "verify_persona_answer",
        lambda *args, **kwargs: (safe, {"status": "revised", "violations": [
            {"category": "unsupported", "claim": "promising", "reason": "absent"}]})
    )
    events = _events(monkeypatch, "luxury-buyer", "Posts show villas. It is a promising area.")
    deltas = [e for e in events if e["type"] == "delta"]
    done = events[-1]
    assert len(deltas) == 1 and deltas[0]["text"] == done["answer"]
    assert "promising" not in done["answer"]
    assert done["guard"]["status"] == "revised"
    assert {"type": "status", "stage": "checking"} in events


def test_the_guard_checks_quotes_against_what_the_tools_returned(monkeypatch):
    """The evidence the model saw - context and every tool result - is what a
    quotation is checked against."""
    seen = {}

    def spy(answer, **kwargs):
        seen["sources"] = kwargs["sources"]
        return answer, {"status": "pass", "violations": []}
    monkeypatch.setattr(graph.guard, "verify_persona_answer", spy)
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: _StreamingAgent("ok"))

    async def collect():
        return [e async for e in graph.astream(QUESTION, "CONTEXT POSTS: villas by the creek", [],
                                               embed_query=None, persona="luxury-buyer")]
    asyncio.run(collect())
    assert "villas by the creek" in seen["sources"]


def test_tool_results_are_kept_as_evidence(monkeypatch):
    evidence: list[str] = []
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *a, **k: {
        "ok": True, "count": 1, "message": "",
        "data": [{"caption": "a promising investment opportunity ’s"}]})
    tools = graph.build_tools(None, None, {}, [], evidence=evidence)
    next(t for t in tools if t.name == "search_posts").func(query="x")
    assert "a promising investment opportunity" in " ".join(evidence)


def test_the_general_view_is_held_and_grounded(monkeypatch):
    seen = {}

    def verify(answer, **kwargs):
        seen.update(kwargs)
        return "Posts show villas.", {"status": "revised", "removed": [
            {"claim": "parks", "reason": "absent"}]}
    monkeypatch.setattr(graph.guard, "verify_general_answer", verify)
    events = _events(monkeypatch, None, "Posts show villas and parks.")
    deltas = [e for e in events if e["type"] == "delta"]
    assert len(deltas) == 1 and deltas[0]["text"] == "Posts show villas."
    assert {"type": "status", "stage": "checking"} in events
    assert seen["question"] == QUESTION and "sources" in seen
    assert events[-1]["answer"] == "Posts show villas."
    assert events[-1]["guard"]["status"] == "revised"


def test_general_review_removes_unsupported_claims():
    out, report = guard.verify_general_answer(
        "DAMAC partners with Chelsea and Versace.", question="q",
        sources='{"caption": "Chelsea Residences by DAMAC"}',
        reviewer=lambda **k: {"status": "revised",
                              "answer": "DAMAC partners with Chelsea.",
                              "removed": [{"claim": "Versace", "reason": "absent"}]})
    assert out == "DAMAC partners with Chelsea."
    assert report["status"] == "revised" and report["removed"][0]["claim"] == "Versace"


def test_general_review_fails_open_and_refuses_new_urls():
    def boom(**k):
        raise RuntimeError("down")
    out, report = guard.verify_general_answer("draft", question="q", sources="", reviewer=boom)
    assert out == "draft" and report["status"] == "unchecked"
    out, report = guard.verify_general_answer(
        "draft", question="q", sources="",
        reviewer=lambda **k: {"status": "revised", "answer": "see https://evil.test/x"})
    assert out == "draft" and report["status"] == "unchecked"


GROUNDED_ANSWER = ("For a Luxury Buyer, the posts show waterfront homes "
                   "(https://source.test/p/1).\n\n"
                   "The data does not cover independent quality assessments.")


def test_persona_graph_passes_exact_question_persona_and_evidence_to_verifier(monkeypatch):
    seen = {}

    def verify(answer, **kwargs):
        seen.update(kwargs)
        return answer, {"status": "pass", "violations": []}

    monkeypatch.setattr(graph.guard, "verify_persona_answer", verify)
    events = _events(monkeypatch, "luxury-buyer", GROUNDED_ANSWER)
    assert seen["question"] == QUESTION
    assert seen["persona"]["persona_id"] == "luxury-buyer"
    assert "sources" in seen
    assert seen["require_persona_format"] is True
    assert events[-1]["type"] == "done"


def test_persona_graph_emits_no_answer_when_verification_fails(monkeypatch):
    def fail(*args, **kwargs):
        raise guard.AnswerVerificationError("unsafe")

    monkeypatch.setattr(graph.guard, "verify_persona_answer", fail)
    with pytest.raises(guard.AnswerVerificationError):
        _events(monkeypatch, "luxury-buyer", "unsupported")


def test_property_persona_graph_uses_deterministic_prefetch_composer(monkeypatch):
    result = {"ok": True, "count": 1, "message": "", "data": [{
        "platform": "instagram", "post_id": "p1", "author_username": "homes",
        "caption": "Waterfront homes beside the creek.",
        "post_url": "https://source.test/p/1",
    }]}
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *args, **kwargs: result)
    monkeypatch.setattr(
        graph, "build_agent",
        lambda *args, **kwargs: _StreamingAgent(
            "For a Luxury Buyer, the posts show an unsafe draft."))
    monkeypatch.setattr(
        graph.guard, "verify_persona_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("not used")))

    async def collect():
        return [event async for event in graph.astream(
            "What about Creek Harbour?", "CTX", [],
            embed_query=lambda text: [0.0], persona="luxury-buyer")]

    events = asyncio.run(collect())
    done = events[-1]
    assert done["guard"]["status"] == "composed"
    assert "Waterfront homes beside the creek" in done["answer"]
    assert "unsafe draft" not in done["answer"]
