"""Consumer personas: a lens on the answer, never a filter on the data.

The brief is explicit that a persona must not restrict what the assistant can
read - a Family Home Seeker can still hear about investment momentum, an
investor can still use lifestyle evidence. Most of what is worth testing is
that the persona reaches the model as context and reaches nothing else.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.api.v1 import assistant as assistant_api
from services.trends_real_estate_service.app.assistant import graph, session, toolargs
from services.trends_real_estate_service.app.main import app
from services.trends_real_estate_service.app.personas import definitions

TEAM_NAMES = ["First-Time Buyer", "Resident Investor", "International Investor",
              "Family Home Seeker", "Young Professional / Couple", "Luxury Buyer"]

EXPECTED_PERSONAS = [
    {
        "persona_id": "first-time-buyer",
        "name": "First-Time Buyer",
        "mindset": "I am buying property for the first time. Is this a sensible, safe and affordable decision?",
        "prioritise": ["affordability", "value for money", "developer credibility",
                       "project/community maturity", "payment considerations",
                       "service charges where available", "connectivity",
                       "essential amenities", "potential risks"],
        "response_behaviour": "Explain unfamiliar real-estate terminology where necessary. Highlight both positives and potential concerns. Avoid assuming deep knowledge of the market.",
    },
    {
        "persona_id": "resident-investor",
        "name": "Resident Investor",
        "mindset": "I already live in or understand this market. Where is the better investment opportunity?",
        "prioritise": ["investment attractiveness", "rental demand",
                       "yield indicators where available", "price positioning",
                       "supply/pipeline", "area momentum", "tenant appeal",
                       "resale potential", "competitive developments"],
        "response_behaviour": "Can be more analytical and comparative. Focus on what differentiates the location/project from alternatives and what could drive or constrain returns.",
    },
    {
        "persona_id": "international-investor",
        "name": "International Investor",
        "mindset": "I am considering investing from outside the country and may not understand the market, locations or developers.",
        "prioritise": ["market and location context", "developer credibility",
                       "investment potential", "ownership/regulatory considerations where available",
                       "area maturity", "demand", "supply", "accessibility",
                       "major development plans", "investment risks"],
        "response_behaviour": "Provide additional context that a local resident may already know. Explain why an area, developer or project matters rather than simply reporting metrics.",
    },
    {
        "persona_id": "family-home-seeker",
        "name": "Family Home Seeker",
        "mindset": "Would my family actually enjoy living here?",
        "prioritise": ["schools", "healthcare", "parks", "supermarkets",
                       "family amenities", "community environment", "space",
                       "accessibility", "commute", "traffic/parking where available",
                       "safety-related indicators where available", "resident sentiment"],
        "response_behaviour": "Evaluate the location primarily as a place to live rather than as a financial asset. Surface practical strengths and weaknesses affecting everyday family life.",
    },
    {
        "persona_id": "young-professional",
        "name": "Young Professional / Couple",
        "mindset": "Does this location fit the lifestyle I want?",
        "prioritise": ["connectivity", "commute", "restaurants", "cafés", "retail",
                       "entertainment", "fitness", "walkability", "lifestyle amenities",
                       "vibrancy", "convenience", "community maturity",
                       "suitable housing options"],
        "response_behaviour": "Focus more heavily on lifestyle and convenience. Distinguish between locations that are already active and established versus those whose proposition depends on future development.",
    },
    {
        "persona_id": "luxury-buyer",
        "name": "Luxury Buyer",
        "mindset": "Is this genuinely premium and distinctive enough for me?",
        "prioritise": ["location prestige", "exclusivity", "developer/project reputation",
                       "waterfront/views where relevant", "architecture/design",
                       "premium amenities", "privacy", "scarcity",
                       "surrounding environment", "premium positioning"],
        "response_behaviour": "Do not equate expensive with luxury. Assess whether there is evidence supporting the premium proposition and identify factors that strengthen or weaken exclusivity.",
    },
]


def test_the_six_personas_are_the_teams():
    assert [p["name"] for p in definitions.PERSONAS] == TEAM_NAMES
    ids = [p["persona_id"] for p in definitions.PERSONAS]
    assert len(set(ids)) == len(ids)


def test_all_personas_match_the_product_brief_exactly():
    keys = EXPECTED_PERSONAS[0].keys()
    actual = [{key: persona[key] for key in keys} for persona in definitions.PERSONAS]
    assert actual == EXPECTED_PERSONAS
    assert all("search_terms" not in persona for persona in definitions.PERSONAS)


def test_the_instruction_carries_the_whole_brief():
    text = definitions.instruction("international-investor")
    persona = definitions.get("international-investor")
    assert persona["mindset"] in text
    assert persona["response_behaviour"] in text
    for priority in persona["prioritise"]:
        assert priority in text


def test_the_instruction_says_lens_not_filter():
    text = definitions.instruction("family-home-seeker")
    assert "lens, not a filter" in text
    assert "Do not drop evidence because it sits outside these priorities" in text


def test_the_persona_does_not_lift_the_no_advice_rule():
    """The personas ask a buyer's questions. The data is marketing posts, and
    the assistant gives no advice - the persona changes emphasis, not that."""
    text = definitions.instruction("resident-investor")
    assert "does not make you an adviser" in text
    assert "no recommendation to buy" in text
    assert "not in this data" in text, "uncovered priorities must be named, not estimated"


def test_verdicts_and_next_steps_are_named_as_off_limits():
    """Measured: without this the persona answers closed with "a compelling
    option for luxury buyers" and "consult a real estate professional"."""
    text = definitions.instruction("luxury-buyer")
    assert '"compelling"' in text and "consulting a professional" in text


def test_persona_search_is_relevant_not_a_fixed_bundle():
    text = definitions.instruction("international-investor")
    assert "as an International Investor" in text
    assert 'opens "For an International Investor, the posts show"' in text
    assert "only the priorities relevant to the user's question" in text
    assert "golden visa" not in text.lower()
    assert "freehold" not in text.lower()


def test_trend_evidence_may_be_reordered_but_not_hidden():
    text = definitions.instruction("luxury-buyer")
    assert "reorder or emphasise" in text
    assert "Do not hide otherwise material trends" in text


def test_persona_priority_query_is_stable_distinct_and_uses_only_brief_terms():
    question = "  What do posts show about   Dubai Creek Harbour?  "
    family = definitions.priority_query("family-home-seeker", question)
    family_again = definitions.priority_query(
        "family-home-seeker", "What do posts show about Dubai Creek Harbour?")
    investor = definitions.priority_query("international-investor", question)
    assert family == family_again
    assert family != investor
    assert family.endswith("schools healthcare parks")
    assert investor.endswith(
        "market and location context developer credibility investment potential")
    assert "golden visa" not in investor.lower()
    assert "freehold" not in investor.lower()


@pytest.mark.parametrize("question", [
    "What do posts show about Dubai Creek Harbour?",
    "Would this community fit a family?",
])
def test_property_evaluations_use_the_record_composer(question):
    assert graph._is_property_record_question(question)


@pytest.mark.parametrize("question", [
    "How many trends are in the data?",
    "Which trends are breaking out?",
    "Hello",
])
def test_catalogue_and_non_property_questions_stay_with_the_agent(question):
    assert not graph._is_property_record_question(question)


@pytest.mark.parametrize("question", [
    "Compare this developer and project for an investor",
    "Between Dubai Creek Harbour and Palm Jumeirah, which reads more exclusive?",
    "Riyadh vs Jeddah for a first investment - what do the posts say?",
    "Compare investment momentum between the UAE and Saudi property markets.",
])
def test_comparison_questions_never_use_the_single_shot_composer(question):
    assert not graph._is_property_record_question(question)


def test_background_must_come_from_the_tools():
    """The International Investor brief asks for context a local would know;
    that context is sourced from the data and attributed, not recalled."""
    text = definitions.instruction("international-investor")
    assert "Do not supply background from your own knowledge" in text


def test_no_persona_is_no_instruction():
    assert definitions.instruction(None) is None
    assert definitions.instruction("") is None
    assert definitions.instruction("gone-persona") is None


def test_no_tool_takes_a_persona():
    """The persona must never narrow a lookup. With no tool argument for it,
    no query can change with it."""
    for name, (model, _) in toolargs.TOOL_ARGS.items():
        assert "persona" not in model.model_fields, f"{name} accepts a persona"


def test_search_posts_drops_an_emptying_country_filter_and_says_so(monkeypatch):
    """Persona searches name a place, the model adds its country, and country
    is unknown on community posts - so the nearest matches filtered to a
    country came back empty for a place with plenty of posts."""
    from services.trends_real_estate_service.app.assistant import tools
    seen = []

    def fake_search(vector, filters, limit=10):
        seen.append(filters.countries)
        return [] if filters.countries else [{"post_id": "1"}]
    monkeypatch.setattr(tools.retrieval, "search_posts", fake_search)
    out = tools.dispatch("search_posts", {"query": "creek harbour schools",
                                          "countries": ["AE"]}, embed_query=lambda q: [0.0])
    assert seen == [["AE"], None]
    assert out["ok"] and out["relaxed_filters"] == ["countries=['AE']"]


def test_an_empty_quadrant_falls_back_to_the_fastest_growing(monkeypatch):
    """The UAE and KSA runs have no breakthrough trends. "Which trends are
    breaking out in KSA" answered "no data", and once "the lookup failed"."""
    from services.trends_real_estate_service.app.assistant import tools
    seen = []

    def fake_search(query=None, quadrant=None, level="micro", limit=10, countries=None,
                    embed_query=None):
        seen.append((quadrant, countries))
        return [] if quadrant else [{"trend_id": "t1", "name": "Riyadh Villas", "country": "SA"}]
    monkeypatch.setattr(tools.retrieval, "search_trends", fake_search)
    out = tools.dispatch("search_trends", {"quadrant": "breakthrough", "countries": ["SA"]},
                         embed_query=lambda q: [0.0])
    assert seen == [("breakthrough", ["SA"]), (None, ["SA"])], "the market must be kept"
    assert out["ok"] and out["relaxed_filters"] == ["quadrant='breakthrough'"]
    assert "none is breakthrough" in out["message"]


class _FakeAgent:
    def __init__(self):
        self.messages = None

    async def astream_events(self, payload, config=None, version=None):
        self.messages = payload["messages"]
        return
        yield  # an async generator that emits nothing


HISTORY = [{"role": "user", "text": "Which trends are growing?"},
           {"role": "assistant", "text": "Waterfront Luxury Residences leads."}]


def _run(monkeypatch, persona):
    fake = _FakeAgent()
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: fake)
    monkeypatch.setattr(
        graph.guard, "verify_persona_answer",
        lambda answer, **kwargs: (answer, {"status": "pass", "violations": []}))

    async def collect():
        return [e async for e in graph.astream("What about Dubai Creek Harbour?", "CTX",
                                               HISTORY, embed_query=None, persona=persona)]
    events = asyncio.run(collect())
    return fake.messages, events[-1]


def test_the_persona_sits_directly_before_the_question(monkeypatch):
    """After the replayed history, not before it: ahead of a long history its
    closing rules were the first thing the model let go of."""
    messages, done = _run(monkeypatch, "luxury-buyer")
    texts = [m.content for m in messages]
    assert texts[0] == "CTX"
    assert texts[-2].startswith("PERSONA: Luxury Buyer")
    assert texts[-1] == "What about Dubai Creek Harbour?"
    assert "Waterfront Luxury Residences leads." in texts[:-2]
    assert done["persona"] == "luxury-buyer"


def test_persona_prefetches_its_stable_priority_records(monkeypatch):
    seen = []
    fake = _FakeAgent()
    monkeypatch.setattr(graph, "build_agent", lambda *args, **kwargs: fake)

    def dispatch(name, args, embed_query, **kwargs):
        seen.append((name, args))
        return {"ok": True, "count": 1, "message": "", "data": [{
            "platform": "instagram", "post_id": "p1", "caption": "parks",
            "post_url": "https://source.test/p/1"}]}

    monkeypatch.setattr(graph.tool_impl, "dispatch", dispatch)
    monkeypatch.setattr(
        graph.guard, "verify_persona_answer",
        lambda answer, **kwargs: (answer, {"status": "pass", "violations": []}))

    async def collect():
        return [event async for event in graph.astream(
            "What about Dubai Creek Harbour?", "CTX", [],
            embed_query=lambda text: [0.0], persona="family-home-seeker")]

    events = asyncio.run(collect())
    assert seen == [("search_posts", {
        "query": "What about Dubai Creek Harbour? schools healthcare parks",
        "limit": 10,
    })]
    assert events[-1]["tool_calls"][0]["name"] == "search_posts"
    assert events[-1]["from_data"] is True


@pytest.mark.parametrize("persona", [None, "gone-persona"])
def test_general_view_adds_nothing(monkeypatch, persona):
    messages, done = _run(monkeypatch, persona)
    assert not any(m.content.startswith("PERSONA:") for m in messages)
    assert done["persona"] is None, "an unknown persona was never applied"


class _Chunk:
    def __init__(self, text):
        self.content = text


class _StreamingFakeAgent:
    """Emits one chat-model-stream event, unlike _FakeAgent which emits none."""

    def __init__(self, text):
        self.text = text

    async def astream_events(self, payload, config=None, version=None):
        yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(self.text)}}


@pytest.mark.parametrize("question", [
    "How many trends are in the data?",
    "Which trends are breaking out?",
])
def test_catalogue_questions_are_held_and_verified_without_persona_format(monkeypatch, question):
    monkeypatch.setattr(graph, "build_agent",
                        lambda *a, **k: _StreamingFakeAgent("Three trends are breaking out."))
    seen = {}

    def verify(answer, **kwargs):
        seen.update(kwargs)
        return answer, {"status": "pass", "violations": []}
    monkeypatch.setattr(graph.guard, "verify_persona_answer", verify)

    async def collect():
        return [e async for e in graph.astream(
            question, "CTX", [], embed_query=None, persona="family-home-seeker")]

    events = asyncio.run(collect())
    assert seen["require_persona_format"] is False
    assert {"type": "status", "stage": "checking"} in events
    assert events[-1]["answer"] == "Three trends are breaking out."


def test_comparison_questions_reach_the_full_agent_not_the_composer(monkeypatch):
    composed = []
    monkeypatch.setattr(
        graph.guard, "compose_persona_answer",
        lambda *a, **k: composed.append(1) or ("x", {"status": "composed"}))
    monkeypatch.setattr(
        graph.guard, "verify_persona_answer",
        lambda answer, **kwargs: (answer, {"status": "pass", "violations": []}))
    monkeypatch.setattr(
        graph, "build_agent",
        lambda *a, **k: _StreamingFakeAgent(
            "For a Luxury Buyer, the posts show a comparison.\n\n"
            "The data does not cover independent verification."))

    def dispatch(name, args, embed_query, **kwargs):
        return {"ok": True, "count": 1, "message": "", "data": [{
            "platform": "instagram", "post_id": "p1", "caption": "parks",
            "post_url": "https://source.test/p/1"}]}
    monkeypatch.setattr(graph.tool_impl, "dispatch", dispatch)

    async def collect():
        return [e async for e in graph.astream(
            "Between Dubai Creek Harbour and Palm Jumeirah, which reads more exclusive?",
            "CTX", [], embed_query=lambda t: [0.0], persona="luxury-buyer")]

    asyncio.run(collect())
    assert not composed, "a comparison must not use the single-shot composer"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test"}
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_the_picker_lists_the_six(client):
    body = client.get("/api/v1/personas").json()
    assert [p["name"] for p in body["personas"]] == TEAM_NAMES
    assert all(p["mindset"] for p in body["personas"])


def test_a_stale_stored_persona_is_not_exposed_by_conversation_reads(client, monkeypatch):
    """A removed persona returned to the browser is echoed with its next
    message and rejected as an unknown selection, bricking an old chat."""
    monkeypatch.setattr(
        session,
        "get_state",
        lambda cid, sub: {
            "transcript": [],
            "title": "An old chat",
            "persona": "renamed-persona",
        },
    )

    response = client.get("/api/v1/assistant/conversations/old-chat")

    assert response.status_code == 200
    assert response.json()["persona"] is None


def test_a_stale_stored_persona_is_not_exposed_in_the_sidebar(client, monkeypatch):
    monkeypatch.setattr(
        session,
        "list_for_user",
        lambda sub: [{
            "conversation_id": "old-chat",
            "title": "An old chat",
            "persona": "renamed-persona",
            "updated_at": None,
            "messages": 2,
        }],
    )

    response = client.get("/api/v1/assistant/conversations")

    assert response.status_code == 200
    assert response.json()["conversations"][0]["persona"] is None


def test_an_unknown_persona_is_refused_not_stored(client, monkeypatch):
    stored = []
    monkeypatch.setattr(session, "set_persona", lambda *a: stored.append(a) or True)
    response = client.put("/api/v1/assistant/conversations/abc/persona",
                          json={"persona": "gen-z-renter"})
    assert response.status_code == 422
    assert not stored
    response = client.post("/api/v1/assistant/chat/stream",
                           json={"message": "hi", "persona": "gen-z-renter"})
    assert response.status_code == 422


def test_a_persona_sent_with_a_message_is_remembered_and_applied(monkeypatch):
    calls = {}
    monkeypatch.setattr(session, "get_state",
                        lambda cid, sub: {"transcript": [], "title": "t", "persona": None})
    monkeypatch.setattr(session, "set_persona",
                        lambda cid, sub, p: calls.setdefault("stored", p) or True)
    monkeypatch.setattr(session, "save_turn",
                        lambda *a: calls.setdefault("saved_persona", a[-1]))
    monkeypatch.setattr(assistant_api.agent, "build_context", lambda q: ("", 0))

    async def fake_astream(*a, persona=None, **k):
        calls["graph_persona"] = persona
        yield {"type": "done", "answer": "x", "from_data": True, "tool_calls": [],
               "trends": [], "persona": persona}
    monkeypatch.setattr(assistant_api.graph, "astream", fake_astream)

    async def run(persona):
        return [e async for e in assistant_api._run_turn("u", "q", "c1", persona=persona)]
    asyncio.run(run("first-time-buyer"))
    assert calls == {"stored": "first-time-buyer", "graph_persona": "first-time-buyer",
                     "saved_persona": "first-time-buyer"}


def test_a_message_without_a_persona_uses_the_chats(monkeypatch):
    seen = {}
    monkeypatch.setattr(session, "get_state",
                        lambda cid, sub: {"transcript": [], "title": "t",
                                          "persona": "resident-investor"})
    monkeypatch.setattr(session, "set_persona", lambda *a: seen.setdefault("changed", True))
    monkeypatch.setattr(session, "save_turn", lambda *a: None)
    monkeypatch.setattr(assistant_api.agent, "build_context", lambda q: ("", 0))

    async def fake_astream(*a, persona=None, **k):
        seen["graph_persona"] = persona
        yield {"type": "done", "answer": "x", "from_data": True, "tool_calls": [],
               "trends": [], "persona": persona}
    monkeypatch.setattr(assistant_api.graph, "astream", fake_astream)

    async def run():
        return [e async for e in assistant_api._run_turn("u", "q", "c1", persona=None)]
    asyncio.run(run())
    assert seen == {"graph_persona": "resident-investor"}, "the pin must not be rewritten"


def test_a_message_without_a_persona_clears_a_stale_stored_pin(monkeypatch):
    """Non-browser callers may omit the persona field. A stale database value
    must still degrade to General view and heal instead of reaching the model."""
    seen = {}
    monkeypatch.setattr(
        session,
        "get_state",
        lambda cid, sub: {
            "transcript": [],
            "title": "t",
            "persona": "renamed-persona",
        },
    )
    monkeypatch.setattr(
        session,
        "set_persona",
        lambda cid, sub, persona: seen.setdefault("stored", persona) is None,
    )
    monkeypatch.setattr(session, "save_turn", lambda *a: None)
    monkeypatch.setattr(assistant_api.agent, "build_context", lambda q: ("", 0))

    async def fake_astream(*a, persona=None, **k):
        seen["graph_persona"] = persona
        yield {
            "type": "done",
            "answer": "x",
            "from_data": True,
            "tool_calls": [],
            "trends": [],
            "persona": persona,
        }

    monkeypatch.setattr(assistant_api.graph, "astream", fake_astream)

    async def run():
        return [
            event
            async for event in assistant_api._run_turn(
                "u", "q", "c1", persona=None
            )
        ]

    asyncio.run(run())
    assert seen == {"stored": None, "graph_persona": None}


def test_failed_persona_verification_is_never_saved(monkeypatch):
    saved = []
    monkeypatch.setattr(
        session, "get_state",
        lambda cid, sub: {"transcript": [], "title": "t", "persona": "luxury-buyer"})
    monkeypatch.setattr(session, "save_turn", lambda *args: saved.append(args))
    monkeypatch.setattr(assistant_api.agent, "build_context", lambda q: ("CTX", 1))

    async def unsafe(*args, **kwargs):
        from services.trends_real_estate_service.app.assistant import guard
        raise guard.AnswerVerificationError("unsafe")
        yield  # pragma: no cover - keeps this an async generator

    monkeypatch.setattr(assistant_api.graph, "astream", unsafe)

    async def run():
        return [event async for event in assistant_api._run_turn(
            "u", "q", "c1", persona=None)]

    with pytest.raises(Exception, match="unsafe"):
        asyncio.run(run())
    assert saved == []
