"""The rich context must reach the model exactly once per turn.

It is ~800 tokens. The agent may call get_persona several times while answering,
and a pinned persona already carries the same block in its system message, so
without a ledger one question could pay for it three or four times over.
"""
from unittest.mock import patch

from services.food_intelligence_service.app.assistant import tools
from services.food_intelligence_service.app.personas import context


ROW = {"persona_id": "busy-family", "name": "Busy Family", "tagline": "t",
       "definition": "short seed text", "stats": {"post_count": 10}}


def _call(ledger=None, persona_id="busy-family"):
    with patch.object(tools.personas, "resolve", return_value=dict(ROW, persona_id=persona_id)):
        return tools.dispatch("get_persona", {"persona_id": persona_id},
                              embed_query=lambda q: [0.0], context_ledger=ledger)


def test_first_call_carries_the_full_context():
    out = _call(ledger=set())
    assert "Core orientation:" in out["data"]["interpretive_context"]
    assert "School lunchbox needs" in out["data"]["interpretive_context"]


def test_second_call_in_the_same_turn_omits_it():
    ledger = set()
    first = _call(ledger=ledger)
    assert "interpretive_context" in first["data"]
    second = _call(ledger=ledger)
    assert "interpretive_context" not in second["data"]
    assert "already" in second["data"]["context_note"].lower()


def test_a_pinned_persona_is_not_sent_twice():
    """Pinning already puts the block in a system message for this turn."""
    ledger = {"busy-family"}
    out = _call(ledger=ledger)
    assert "interpretive_context" not in out["data"]


def test_a_different_persona_still_gets_its_context():
    ledger = {"busy-family"}
    out = _call(ledger=ledger, persona_id="food-explorer")
    assert "Core orientation:" in out["data"]["interpretive_context"]


def test_the_two_original_blocks_are_untouched():
    out = _call(ledger=set())
    assert out["data"]["definition_given_to_us"]["name"] == "Busy Family"
    assert out["data"]["measured_from_posts"] == {"post_count": 10}


def test_no_ledger_still_returns_context():
    """Any caller that does not pass a ledger gets the safe behaviour."""
    out = _call(ledger=None)
    assert "Core orientation:" in out["data"]["interpretive_context"]


def test_persona_without_authored_context_omits_the_key():
    out = _call(ledger=set(), persona_id="chat-made-up")
    assert "interpretive_context" not in out["data"]


def test_pinned_turn_seeds_the_ledger():
    """astream must mark the pinned persona as delivered before any tool runs."""
    from services.food_intelligence_service.app.assistant import graph
    from services.food_intelligence_service.app.personas import store as pstore
    with patch.object(pstore, "resolve", return_value=ROW):
        built = graph._persona_instruction("busy-family")
    assert built is not None
    text, persona_id = built
    assert persona_id == "busy-family"
    assert "Core orientation:" in text
