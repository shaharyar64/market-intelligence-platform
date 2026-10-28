"""The interpretive context handed to the model when a persona is pinned."""
from unittest.mock import patch

import pytest

from services.food_intelligence_service.app.personas import context, seeds


def _instruction(persona_id="busy-family", name="Busy Family"):
    from services.food_intelligence_service.app.assistant import graph
    from services.food_intelligence_service.app.personas import store as pstore
    with patch.object(pstore, "resolve",
                      return_value={"persona_id": persona_id, "name": name}):
        built = graph._persona_instruction(persona_id)
        return built[0] if built else None


def test_every_seed_has_authored_context():
    """A seeded persona without context would pin with no interpretive lens."""
    missing = [s["persona_id"] for s in seeds.SEEDS
               if s["persona_id"] not in context.PERSONA_CONTEXT]
    assert not missing, f"no context authored for: {missing}"


def test_pinning_delivers_the_rich_context():
    out = _instruction()
    assert "Core orientation:" in out
    assert "School lunchbox needs" in out, "busy-family context missing"
    assert "Signals worth noticing in the data:" in out


def test_context_is_framed_as_a_lens_not_a_filter():
    """The brief is explicit that evidence outranks the profile."""
    out = _instruction()
    assert "interpretive lens, not as a rigid definition" in out
    assert "Base findings primarily on the underlying retrieved data" in out
    assert "do not suppress unexpected themes" in out


def test_model_is_told_not_to_roleplay():
    out = _instruction()
    assert "Do not pretend to be an individual consumer" in out


def test_tool_directive_survives():
    """Without this the SQL membership filter never runs and every persona
    answer is a whole-market answer wearing the segment's name."""
    out = _instruction()
    assert 'persona="busy-family"' in out
    assert "search_trends" in out and "aggregate_posts" in out


def test_selected_persona_block_is_present():
    out = _instruction()
    assert "Selected persona:" in out
    assert "Name: Busy Family" in out
    assert "ID: busy-family" in out


def test_persona_without_context_still_pins():
    """A chat-built persona has no authored context; pinning must still work."""
    out = _instruction(persona_id="chat-made-up", name="Chat Made Up")
    assert 'persona="chat-made-up"' in out
    assert "Core orientation:" not in out


@pytest.mark.parametrize("pid", ["health-conscious", "busy-family",
                                 "food-explorer", "fitness-focused"])
def test_rich_context_is_never_used_for_embedding(pid):
    """seeds.definition drives membership. If the rich text ever leaked into
    that path every persona's region of the corpus would silently move."""
    seed = next(s for s in seeds.SEEDS if s["persona_id"] == pid)
    assert context.PERSONA_CONTEXT[pid] != seed["definition"]
    assert "Core orientation:" not in seed["definition"]
    assert len(seed["definition"]) < len(context.PERSONA_CONTEXT[pid])


def _delivered():
    """The guidance as the model actually receives it: attached to the context
    in a get_persona result, not carried in SYSTEM_PROMPT on every request."""
    from unittest.mock import patch
    from services.food_intelligence_service.app.assistant import tools
    row = {"persona_id": "busy-family", "name": "Busy Family", "stats": {}}
    with patch.object(tools.personas, "resolve", return_value=dict(row)):
        out = tools.dispatch("get_persona", {"persona_id": "busy-family"},
                             embed_query=lambda q: [0.0], context_ledger=set())
    return out["data"]["how_to_use_it"]


def test_lens_rules_are_not_in_the_system_prompt():
    """Redundant there - the pinned message states all of them - and
    SYSTEM_PROMPT is paid for on every request, persona or not."""
    from services.food_intelligence_service.app.assistant import prompts
    assert "PERSONA CONTEXT IS A LENS" not in prompts.SYSTEM_PROMPT


def test_guidance_states_the_evidence_priority_ordering():
    g = _delivered().lower()
    assert "lens, not a filter" in g
    assert "retrieved evidence first" in g
    assert "inference last" in g


def test_guidance_forbids_forcing_findings_to_fit_the_profile():
    g = _delivered().lower()
    assert "do not force" in g
    assert "do not suppress" in g


def test_guidance_requires_surfacing_contradictions():
    assert "contradict" in _delivered().lower()


def test_guidance_separates_observation_from_interpretation():
    g = _delivered().lower()
    assert "observed" in g and "interpretation" in g


def test_guidance_forbids_roleplay():
    assert "do not write as the persona" in _delivered().lower()
