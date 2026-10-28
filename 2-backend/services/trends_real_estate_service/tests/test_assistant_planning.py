import asyncio
import json

from services.trends_real_estate_service.app.assistant import graph, guard, intent, session, tools

PRIOR_CALL = {"name": "search_trends", "ok": True, "count": 2,
              "args": {"query": "sustainability", "countries": ["AE"]},
              "top": ["Long-Term Developer Commitment", "Inclusive Environments"]}
TRANSCRIPT = [
    {"role": "user", "text": "Sustainability trends in the UAE?"},
    {"role": "assistant", "text": "Long-Term Developer Commitment leads.",
     "tool_calls": [PRIOR_CALL]},
]


class _FakeAgent:
    def __init__(self):
        self.messages = None

    async def astream_events(self, payload, config=None, version=None):
        self.messages = payload["messages"]
        return
        yield


def _run(monkeypatch, plan, question="these are not sustainability"):
    fake = _FakeAgent()
    built = {}

    def build_agent(*args, **kwargs):
        built["refused"] = args[6] if len(args) > 6 else kwargs.get("refused")
        return fake
    monkeypatch.setattr(graph, "build_agent", build_agent)
    monkeypatch.setattr(intent, "classify", lambda *a, **k: plan)

    async def collect():
        return [e async for e in graph.astream(question, "CTX", TRANSCRIPT,
                                               embed_query=None)]
    events = asyncio.run(collect())
    return fake.messages, built["refused"], events[-1]


def test_history_replays_the_tool_calls_behind_each_answer():
    messages = graph._history_messages(TRANSCRIPT)
    trace = messages[-1].content
    assert trace.startswith("Tool calls behind the answer above:")
    assert '"query": "sustainability"' in trace
    assert "Long-Term Developer Commitment" in trace


def test_a_correction_refuses_the_previous_turns_exact_calls(monkeypatch):
    plan = intent.QueryPlan(intent="trend_discovery", is_correction=True,
                            rejected_items=["Inclusive Environments"],
                            expanded_terms=["solar", "LEED", "Estidama"])
    messages, refused, done = _run(monkeypatch, plan)
    assert graph._call_key("search_trends", PRIOR_CALL["args"]) in refused
    planned = [m.content for m in messages if m.content.startswith("QUERY PLAN")]
    assert planned and "REJECTED THE PREVIOUS ANSWER" in planned[0]
    assert "Estidama" in planned[0]
    assert messages[-1].content == "these are not sustainability"
    assert done["plan"] == plan.model_dump()


def test_no_refusals_without_a_correction(monkeypatch):
    _, refused, _ = _run(monkeypatch, intent.QueryPlan(intent="trend_discovery"))
    assert not refused


def test_a_refused_call_never_reaches_the_tools(monkeypatch):
    dispatched = []
    monkeypatch.setattr(graph.tool_impl, "dispatch",
                        lambda *a, **k: dispatched.append(a) or {"ok": True, "count": 0})
    refused = {graph._call_key("search_trends", PRIOR_CALL["args"])}
    tool = next(t for t in graph.build_tools(None, None, {}, [], refused=refused)
                if t.name == "search_trends")
    out = json.loads(tool.func(query="sustainability", countries=["AE"]))
    assert out["refused"] and not dispatched


def test_tool_calls_record_args_and_top_results(monkeypatch):
    calls = []
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *a, **k: {
        "ok": True, "count": 2, "message": "",
        "data": [{"trend_id": "a", "name": "Green Villa Communities"},
                 {"trend_id": "b", "name": "Green and Nature-Inspired Living"}]})
    tool = next(t for t in graph.build_tools(None, None, {}, calls)
                if t.name == "search_trends")
    tool.func(query="green building")
    assert calls[0]["args"] == {"query": "green building"}
    assert calls[0]["top"] == ["Green Villa Communities", "Green and Nature-Inspired Living"]


def test_saved_turns_keep_the_tool_trace(monkeypatch):
    written = {}
    monkeypatch.setattr(session, "get_state", lambda *a: {"transcript": [], "title": "x"})

    class _Cur:
        rowcount = 1

        def execute(self, sql, params):
            written["transcript"] = json.loads(params[0])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn(_Cur):
        def cursor(self):
            return _Cur()
    monkeypatch.setattr(session.store, "get_conn", lambda: _Conn())
    session.save_turn("c", "u", "q", "a", True, [], [dict(PRIOR_CALL, weak_match=True)])
    saved = written["transcript"][-1]["tool_calls"][0]
    assert saved["args"] == PRIOR_CALL["args"]
    assert saved["top"] == PRIOR_CALL["top"] and saved["weak_match"] is True


def test_search_trends_applies_no_level_filter(monkeypatch):
    seen = {}

    def fake_search(**kwargs):
        seen.update(kwargs)
        return [{"trend_id": "t", "name": "Green and Nature-Inspired Living",
                 "level": "umbrella", "distance": 0.3}]
    monkeypatch.setattr(tools.retrieval, "search_trends", fake_search)
    out = tools.dispatch("search_trends", {"query": "green living"}, embed_query=None)
    assert "level" not in seen
    assert out["ok"] and not out.get("weak_match")


def test_a_distant_trend_match_is_flagged_weak(monkeypatch):
    monkeypatch.setattr(tools.retrieval, "search_trends", lambda **k: [
        {"trend_id": "t", "name": "Inclusive Environments", "distance": 0.68}])
    out = tools.dispatch("search_trends", {"query": "sustainability"}, embed_query=None)
    assert out["ok"] and out["weak_match"] and out["message"].startswith("WEAK MATCH")


def test_developers_by_topic_drops_an_emptying_country(monkeypatch):
    seen = []

    def fake(vector, countries=None, limit=10):
        seen.append(countries)
        return [] if countries else [{"developer": "DAMAC Properties", "matching_posts": 4}]
    monkeypatch.setattr(tools.retrieval, "developers_by_topic", fake)
    out = tools.dispatch("developers_by_topic",
                         {"query": "branded residences", "countries": ["AE"]},
                         embed_query=lambda q: [0.0])
    assert seen == [["AE"], None]
    assert out["ok"] and out["relaxed_filters"] == ["countries=['AE']"]


def test_developers_in_trend_passes_the_country_and_warns_about_it(monkeypatch):
    seen = {}

    def fake(trend_id, limit=15, countries=None):
        seen["countries"] = countries
        return [{"developer": "Aldar", "developer_country": "AE"}]
    monkeypatch.setattr(tools.retrieval, "developers_in_trend", fake)
    out = tools.dispatch("developers_in_trend", {"trend_id": "flex--1", "countries": ["AE"]},
                         embed_query=None)
    assert seen["countries"] == ["AE"]
    assert out["ok"] and out["data"][0]["developer"] == "Aldar"
    assert "developer_country" in out["message"]


def test_a_correction_marks_trends_the_user_already_saw(monkeypatch):
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *a, **k: {
        "ok": True, "count": 2, "message": "",
        "data": [{"trend_id": "a", "name": "Inclusive Environments"},
                 {"trend_id": "b", "name": "Green Villa Communities"}]})
    shown = graph._previous_names(TRANSCRIPT, intent.QueryPlan())
    tool = next(t for t in graph.build_tools(None, None, {}, [], shown=shown)
                if t.name == "search_trends")
    out = json.loads(tool.func(query="green building"))
    assert out["data"][0]["previously_shown"] is True
    assert "previously_shown" not in out["data"][1]
    assert "Do not lead with them" in out["message"]


def test_the_general_review_retries_when_it_flags_but_keeps_a_claim():
    replies = [
        {"status": "pass", "answer": "Saudi firms in the UAE.",
         "removed": [{"claim": "in the UAE", "reason": "developer_country is SA"}]},
        {"status": "revised", "answer": "Saudi firms.", "removed": []},
    ]
    seen = []

    def reviewer(**kwargs):
        seen.append(kwargs["sources"])
        return replies[len(seen) - 1]
    out, report = guard.verify_general_answer("Saudi firms in the UAE.", question="q",
                                              sources="evidence", reviewer=reviewer)
    assert out == "Saudi firms." and report["status"] == "revised"
    assert "YOU FLAGGED THESE CLAIMS" in seen[1]


def test_a_property_question_with_another_intent_skips_the_composer(monkeypatch):
    composed = []
    monkeypatch.setattr(graph.guard, "compose_persona_answer",
                        lambda *a, **k: composed.append(1) or ("x", {"status": "composed"}))
    monkeypatch.setattr(graph.guard, "verify_persona_answer",
                        lambda answer, **k: (answer, {"status": "pass", "violations": []}))
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: _FakeAgent())
    monkeypatch.setattr(intent, "classify",
                        lambda *a, **k: intent.QueryPlan(intent="post_examples"))
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *a, **k: {
        "ok": True, "count": 1, "message": "", "data": [{
            "platform": "x", "post_id": "1", "caption": "c",
            "post_url": "https://source.test/p/1"}]})

    async def collect():
        return [e async for e in graph.astream(
            "tell me about sharia compliant home loans", "", [],
            embed_query=lambda t: [0.0], persona="first-time-buyer")]
    asyncio.run(collect())
    assert not composed


def test_plan_message_is_empty_without_a_plan():
    assert intent.plan_message(None) is None


def test_planner_returns_none_on_failure(monkeypatch):
    def boom(*a):
        raise RuntimeError("no network")
    monkeypatch.setattr(intent, "_complete", boom)
    assert intent.classify("q", []) is None


def test_an_unknown_intent_keeps_the_plan_as_other(monkeypatch):
    monkeypatch.setattr(intent, "_complete",
                        lambda *a: '{"intent": "correction", "is_correction": true}')
    plan = intent.classify("q", [])
    assert plan.intent == "other" and plan.is_correction is True


def test_a_weak_country_match_widens_to_all_markets(monkeypatch):
    seen = []

    def fake_search(**kwargs):
        seen.append(kwargs["countries"])
        if kwargs["countries"]:
            return [{"trend_id": "a", "name": "Inclusive Environments", "distance": 0.66}]
        return [{"trend_id": "b", "name": "Flexible Commercial Workspaces", "distance": 0.3}]
    monkeypatch.setattr(tools.retrieval, "search_trends", fake_search)
    out = tools.dispatch("search_trends", {"query": "flexible workspaces", "countries": ["AE"]},
                         embed_query=None)
    assert seen == [["AE"], None]
    assert out["data"][0]["name"] == "Flexible Commercial Workspaces"
    assert out["relaxed_filters"] == ["countries=['AE']"] and not out.get("weak_match")


def test_planner_sees_the_previous_tool_trace(monkeypatch):
    seen = {}

    def complete(system, user):
        seen["user"] = user
        return '{"intent": "trend_discovery", "is_correction": true}'
    monkeypatch.setattr(intent, "_complete", complete)
    plan = intent.classify("these are not sustainability", TRANSCRIPT)
    assert plan.is_correction is True
    assert "ASSISTANT TOOL CALLS: search_trends" in seen["user"]


def test_create_trend_reuses_a_close_chat_trend(monkeypatch):
    built = []
    monkeypatch.setattr(tools.adhoc, "existing_chat_trend", lambda q, e: {
        "trend_id": "c-sustainability--1", "name": "sustainability", "distance": 0.13})
    monkeypatch.setattr(tools.retrieval, "get_trend", lambda tid: {
        "trend_id": tid, "name": "sustainability in residential real estate",
        "quadrant": "slow-burner", "post_count": 425, "unique_authors": 72,
        "volume_index": 69.6, "growth_index": 69.2, "growth_pct": 61.1,
        "source_mix": {"brand": 215}})
    monkeypatch.setattr(tools.adhoc, "build", lambda *a, **k: built.append(1))
    out = tools.dispatch("create_trend", {"query": "sustainability trends"},
                         embed_query=lambda q: [0.0])
    assert not built
    assert out["ok"] and out["reused"] and out["data"]["trend_id"] == "c-sustainability--1"
    assert "reused instead of creating a duplicate" in out["message"]


def test_create_trend_builds_when_nothing_close_exists(monkeypatch):
    monkeypatch.setattr(tools.adhoc, "existing_chat_trend", lambda q, e: None)
    monkeypatch.setattr(tools.adhoc, "similar_existing", lambda q, e: [])
    monkeypatch.setattr(tools.adhoc, "build", lambda *a, **k: {
        "trend_id": "c-new--1", "name": "new", "quadrant": "watchlist", "post_count": 20,
        "unique_authors": 5, "volume_index": 10, "growth_index": 10,
        "metrics": {"growth_pct": 1.0, "source_mix": {}}})
    out = tools.dispatch("create_trend", {"query": "rooftop gardens"}, embed_query=lambda q: [0.0])
    assert out["ok"] and out["data"]["created"] is True


def test_the_plan_model_normalises_what_the_planner_returns():
    plan = intent.QueryPlan.model_validate({
        "intent": "sustainability", "countries": ["UAE", "KSA", "Kuwait", "AE"],
        "expanded_terms": "solar", "rejected_items": None, "plan": ["a", "", None],
        "is_correction": "true", "unexpected": 1})
    assert plan.intent == "other"
    assert plan.countries == ["AE", "SA"]
    assert plan.expanded_terms == ["solar"] and plan.rejected_items == []
    assert plan.plan == ["a"] and plan.is_correction is True


def test_a_plan_that_fails_validation_is_dropped(monkeypatch):
    monkeypatch.setattr(intent, "_complete", lambda *a: '{"is_correction": {"bad": 1}}')
    assert intent.classify("q", []) is None


def test_a_review_that_fails_validation_keeps_the_draft():
    out, report = guard.verify_general_answer(
        "draft", question="q", sources="",
        reviewer=lambda **k: {"status": "maybe", "answer": ""})
    assert out == "draft" and report["status"] == "unchecked"


def test_a_correction_is_never_out_of_scope():
    plan = intent.QueryPlan(intent="out_of_scope", is_correction=True, needs_definition=True)
    assert plan.intent == "definition"
    assert intent.QueryPlan(intent="out_of_scope").intent == "out_of_scope"


def test_already_shown_covers_the_last_three_answers():
    transcript = [
        {"role": "user", "text": "q1"},
        {"role": "assistant", "text": "a1", "trends": [{"name": "Green and Nature-Inspired Living"}]},
        {"role": "user", "text": "q2"},
        {"role": "assistant", "text": "a2", "tool_calls": [{"name": "search_posts", "top": ["aldar"]}]},
        {"role": "user", "text": "q3"},
        {"role": "assistant", "text": "a3", "tool_calls": [PRIOR_CALL]},
    ]
    names = graph._previous_names(transcript, intent.QueryPlan())
    assert {"green and nature-inspired living", "aldar", "inclusive environments"} <= names


def test_a_near_identical_answer_is_rewritten(monkeypatch):
    previous = "BNW partners with Lamborghini. RAK partners with Armani. Taraf with W."
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: _Streaming(previous))
    rewrites = []
    monkeypatch.setattr(graph.guard, "answer_without_repeating",
                        lambda a, **k: rewrites.append(k) or "Lamborghini, Armani and W.")
    transcript = [{"role": "user", "text": "partners?"},
                  {"role": "assistant", "text": previous}]

    async def collect():
        return [e async for e in graph.astream("which brands?", "", transcript,
                                               embed_query=None)]
    done = asyncio.run(collect())[-1]
    assert rewrites and rewrites[0]["question"] == "which brands?"
    assert done["answer"] == "Lamborghini, Armani and W."


def test_a_different_answer_is_not_rewritten(monkeypatch):
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: _Streaming("Something new."))
    monkeypatch.setattr(graph.guard, "answer_without_repeating",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("not used")))
    transcript = [{"role": "user", "text": "q"},
                  {"role": "assistant", "text": "A completely different earlier answer."}]

    async def collect():
        return [e async for e in graph.astream("q2", "", transcript, embed_query=None)]
    assert asyncio.run(collect())[-1]["answer"] == "Something new."


def test_repeat_rewrite_keeps_the_draft_if_it_invents_a_link(monkeypatch):
    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": "see https://x.test/1"})})]
    from services.trends_real_estate_service.app.assistant import agent
    monkeypatch.setattr(agent, "_client", lambda: type("Cl", (), {"chat": type("Ch", (), {
        "completions": type("Co", (), {"create": staticmethod(lambda **k: _Resp)})})})())
    assert guard.answer_without_repeating("draft", question="q", previous="p") == "draft"


class _Chunk:
    def __init__(self, text):
        self.content = text


class _Streaming:
    def __init__(self, text):
        self.text = text

    async def astream_events(self, payload, config=None, version=None):
        yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(self.text)}}


class _Scripted:
    def __init__(self, texts):
        self.texts = list(texts)
        self.runs = []

    async def astream_events(self, payload, config=None, version=None):
        self.runs.append(list(payload["messages"]))
        yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(self.texts.pop(0))}}


def test_a_correction_that_repeats_an_earlier_answer_searches_again(monkeypatch):
    earlier = "Green and Nature-Inspired Living leads, with 789 posts from 60 authors."
    agent = _Scripted([earlier, "New: Sobha's solar and rainwater posts."])
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: agent)
    monkeypatch.setattr(intent, "classify",
                        lambda *a, **k: intent.QueryPlan(intent="other", is_correction=True))
    monkeypatch.setattr(graph.guard, "answer_without_repeating",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("not used")))
    transcript = [{"role": "user", "text": "q1"}, {"role": "assistant", "text": earlier},
                  {"role": "user", "text": "q2"}, {"role": "assistant", "text": "Something else."}]

    async def collect():
        return [e async for e in graph.astream("you again gave me the same points", "",
                                               transcript, embed_query=None)]
    done = asyncio.run(collect())[-1]
    assert len(agent.runs) == 2
    assert graph.RETRY_AFTER_REPEAT in [m.content for m in agent.runs[1]]
    assert done["answer"] == "New: Sobha's solar and rainwater posts."


def test_a_correction_citing_only_old_posts_searches_again(monkeypatch):
    old = "Sobha posted about solar https://www.instagram.com/p/OLD1"
    agent = _Scripted(["Inclusive Environments matters. Sobha https://www.instagram.com/p/OLD1",
                       "LEED: Majid Al Futtaim https://www.instagram.com/p/NEW1"])
    monkeypatch.setattr(graph, "build_agent", lambda *a, **k: agent)
    monkeypatch.setattr(intent, "classify",
                        lambda *a, **k: intent.QueryPlan(is_correction=True, topic="sustainability"))
    seen = {}
    monkeypatch.setattr(graph.guard, "verify_general_answer",
                        lambda a, **k: seen.update(k) or (a, {"status": "pass", "removed": []}))
    transcript = [{"role": "user", "text": "q"}, {"role": "assistant", "text": old}]

    async def collect():
        return [e async for e in graph.astream("you again gave me the same points", "",
                                               transcript, embed_query=None)]
    done = asyncio.run(collect())[-1]
    assert len(agent.runs) == 2 and "NEW1" in done["answer"]
    assert seen["topic"] == "sustainability"


def test_posts_already_shown_are_marked(monkeypatch):
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *a, **k: {
        "ok": True, "count": 2, "message": "",
        "data": [{"post_url": "https://www.instagram.com/p/OLD1", "caption": "solar"},
                 {"post_url": "https://www.instagram.com/p/NEW1", "caption": "LEED"}]})
    shown = graph._previous_names(
        [{"role": "assistant", "text": "see https://www.instagram.com/p/OLD1"}], None)
    tool = next(t for t in graph.build_tools(None, None, {}, [], shown=shown)
                if t.name == "search_posts")
    out = json.loads(tool.func(query="solar"))
    assert out["data"][0]["previously_shown"] is True
    assert "previously_shown" not in out["data"][1]


def test_the_topic_reaches_the_reviewer():
    seen = {}
    guard.verify_general_answer("a", question="q", sources="", topic="sustainability",
                                reviewer=lambda **k: seen.update(k) or {"status": "pass",
                                                                        "answer": "a"})
    assert seen["question"] == "q [topic: sustainability]"


def test_the_trace_carries_real_trend_ids_for_follow_ups(monkeypatch):
    calls = []
    monkeypatch.setattr(graph.tool_impl, "dispatch", lambda *a, **k: {
        "ok": True, "count": 1, "message": "",
        "data": [{"trend_id": "flexible-commercial-workspaces--4669fec9",
                  "name": "Flexible Commercial Workspaces"}]})
    tool = next(t for t in graph.build_tools(None, None, {}, calls) if t.name == "search_trends")
    tool.func(query="flexible workspaces")
    assert calls[0]["ids"] == {"Flexible Commercial Workspaces":
                               "flexible-commercial-workspaces--4669fec9"}
    trace = intent.trace_text(calls)
    assert "Flexible Commercial Workspaces [trend_id=flexible-commercial-workspaces--4669fec9]" in trace
