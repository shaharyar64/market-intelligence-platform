"""The assistant's LangGraph agent.

These cover the seams between our code and the framework — the places a
migration can look fine and behave differently: argument validation, the
default-vs-None trap, what counts as the answer when tools ran, and the event
shape the browser depends on.
"""
from unittest.mock import patch

import pydantic
import pytest

from services.food_intelligence_service.app.assistant import graph, toolargs


def _tools(calls=None, seen=None, user_sub="u1"):
    return graph.build_tools(lambda q: [0.0], user_sub,
                             seen if seen is not None else {},
                             calls if calls is not None else [])


def _by_name(user_sub="u1", calls=None, seen=None):
    return {t.name: t for t in _tools(calls, seen, user_sub)}


def test_every_tool_is_built():
    assert set(_by_name()) == set(toolargs.TOOL_ARGS)


def test_invalid_enum_is_rejected_before_the_tool_runs():
    """A raw JSON schema is advertised but never enforced, so an invalid
    quadrant reached the query. A pydantic schema rejects it and the agent gets
    the error back to correct itself."""
    with patch.object(graph.tool_impl, "dispatch") as dispatch:
        with pytest.raises(pydantic.ValidationError):
            _by_name()["search_trends"].invoke({"quadrant": "not-a-quadrant"})
    dispatch.assert_not_called()


def test_wrong_type_is_rejected_before_it_reaches_sql():
    with patch.object(graph.tool_impl, "dispatch") as dispatch:
        with pytest.raises(pydantic.ValidationError):
            _by_name()["search_trends"].invoke({"limit": "twelve"})
    dispatch.assert_not_called()


def test_unset_optional_arguments_are_not_sent_as_none():
    """dispatch reads optionals as args.get("level", "micro"). A key present and
    empty returns None and overrides that default, which made search_trends
    answer "no data" for a question with plenty of it."""
    captured = {}

    def fake_dispatch(name, args, embed_query, user_sub=None, **_):
        captured.update(args)
        return {"ok": True, "data": [], "count": 0, "message": ""}

    with patch.object(graph.tool_impl, "dispatch", fake_dispatch):
        _by_name()["search_trends"].invoke({"query": "mandi"})
    assert captured == {"query": "mandi"}, "only the argument actually supplied"


def test_the_caller_reaches_dispatch():
    """create_trend records who asked for it."""
    seen_user = {}

    def fake_dispatch(name, args, embed_query, user_sub=None, **_):
        seen_user["sub"] = user_sub
        return {"ok": True, "data": {"trend_id": "c-x", "name": "X"},
                "count": 1, "message": ""}

    with patch.object(graph.tool_impl, "dispatch", fake_dispatch):
        _by_name(user_sub="u-42")["create_trend"].invoke({"query": "matcha"})
    assert seen_user["sub"] == "u-42"


def test_results_are_recorded_for_the_ui():
    """ok and count are read off the raw result: by the time LangGraph has the
    tool output it is a string, and the chips under an answer need the numbers."""
    calls, seen = [], {}
    with patch.object(graph.tool_impl, "dispatch",
                      return_value={"ok": True, "count": 8,
                                    "data": [{"trend_id": "t1", "name": "Mandi"}],
                                    "message": ""}):
        _by_name(calls=calls, seen=seen)["search_trends"].invoke({"query": "mandi"})
    assert calls == [{"name": "search_trends", "args": {"query": "mandi"},
                      "ok": True, "count": 8}]
    assert seen == {"t1": "Mandi"}, "trend ids are harvested so the UI can link them"


def test_history_replays_both_sides_in_order():
    transcript = [{"role": "user", "text": "q1"}, {"role": "assistant", "text": "a1"},
                  {"role": "user", "text": "q2"}, {"role": "assistant", "text": "a2"}]
    messages = graph._history_messages(transcript)
    assert [m.content for m in messages] == ["q1", "a1", "q2", "a2"]
    assert [m.type for m in messages] == ["human", "ai", "human", "ai"]


def test_history_is_capped_so_a_long_chat_cannot_grow_the_prompt():
    transcript = [{"role": "user" if i % 2 == 0 else "assistant", "text": f"m{i}"}
                  for i in range(100)]
    messages = graph._history_messages(transcript)
    assert len(messages) == graph.HISTORY_TURNS * 2
    assert messages[-1].content == "m99", "the most recent turns are the ones kept"


def test_empty_messages_are_skipped():
    """A turn that failed can leave an empty string, and an empty message is
    rejected by the API rather than ignored."""
    messages = graph._history_messages(
        [{"role": "user", "text": ""}, {"role": "bot", "text": "kept"}])
    assert [m.content for m in messages] == ["kept"]


def test_tool_call_budget_leaves_room_for_the_final_answer():
    """LangGraph counts graph steps, not tool calls: each call costs a model
    turn and a tool turn, and the answer needs one more."""
    assert graph.RECURSION_LIMIT >= graph.MAX_TOOL_CALLS * 2 + 1


def test_transcripts_written_before_the_rename_still_replay():
    """The assistant's role was "bot" until recently. Those turns are still in
    the database and in browsers' local storage, and an unrecognised role must
    not silently drop a turn out of the conversation's memory."""
    messages = graph._history_messages(
        [{"role": "user", "text": "q"}, {"role": "bot", "text": "older answer"}])
    assert [m.type for m in messages] == ["human", "ai"]
    assert messages[1].content == "older answer"
