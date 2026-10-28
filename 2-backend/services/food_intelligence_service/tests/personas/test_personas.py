"""Personas as a lens over the corpus.

A persona filter is a subtractive thing: switching it on throws away 97% of the
posts. Most of what is worth testing here is about that — that it narrows only
when asked, that it fails loudly when it cannot narrow correctly, and that a
count of posts is never presented as a count of people.
"""
from unittest.mock import patch

import pytest

from services.food_intelligence_service.app.assistant import retrieval, tools
from services.food_intelligence_service.app.personas import build, seeds


def test_seed_definitions_are_prose_not_keyword_lists():
    """The definition is what gets embedded. A comma-separated list of nouns
    lands somewhere between its own words rather than near real captions."""
    for seed in seeds.SEEDS:
        assert len(seed["definition"].split()) >= 30, seed["persona_id"]
        assert seed["definition"].count(".") >= 2, seed["persona_id"]


def test_every_seed_carries_the_clients_own_fields():
    for seed in seeds.SEEDS:
        for field in ("motivations", "priorities", "behaviors"):
            assert seed[field], f"{seed['persona_id']} lost its {field}"


def test_persona_filter_is_absent_unless_asked_for():
    """The clause discards every post outside the persona, so it must never
    appear by default: a question about the whole market would silently be
    answered from one slice of it."""
    where, params = retrieval.build_post_where(retrieval.PostFilters())
    assert "persona_post" not in where
    assert "persona" not in params


def test_persona_filter_restricts_to_members():
    where, params = retrieval.build_post_where(
        retrieval.PostFilters(persona="health-conscious"))
    assert "persona_post" in where
    assert params["persona"] == "health-conscious"


def test_unknown_persona_stops_the_call_instead_of_filtering_to_nothing():
    """Filtering on a name that matches nothing returns zero rows, which reads
    as "this segment has no posts" - a claim about the market made from a typo."""
    with patch.object(tools.personas, "resolve", return_value=None), \
         patch.object(tools.personas, "list_personas",
                      return_value=[{"persona_id": "busy-family"}]), \
         patch.object(tools.retrieval, "search_trends") as search:
        out = tools.dispatch("search_trends", {"query": "protein",
                                               "persona": "gen-z-snackers"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is False
    assert "busy-family" in out["message"], "the caller needs the real names"
    search.assert_not_called(), "nothing should be looked up under a bad filter"


def test_a_persona_name_resolves_the_way_a_user_says_it():
    """The model is handed ids and users say "the busy family one"; the model
    passes that through verbatim."""
    from services.food_intelligence_service.app.personas import store as pstore
    rows = [{"persona_id": "busy-family", "name": "Busy Family"},
            {"persona_id": "health-conscious", "name": "Health Conscious Consumer"}]
    with patch.object(pstore, "list_personas", return_value=rows):
        assert pstore.resolve("busy family")["persona_id"] == "busy-family"
        assert pstore.resolve("Busy Family")["persona_id"] == "busy-family"
        assert pstore.resolve("health-conscious")["persona_id"] == "health-conscious"


def test_resolve_does_not_match_on_a_word_every_persona_shares():
    from services.food_intelligence_service.app.personas import store as pstore
    rows = [{"persona_id": "health-conscious-consumer", "name": "Health Conscious Consumer"},
            {"persona_id": "fitness-focused-consumer", "name": "Fitness Focused Consumer"}]
    with patch.object(pstore, "list_personas", return_value=rows):
        assert pstore.resolve("fitness")["persona_id"] == "fitness-focused-consumer"


def test_get_persona_keeps_belief_and_measurement_apart():
    """The client's segmentation and what the posts show are different kinds of
    claim. Merged into one object they read as equally evidenced."""
    row = {"persona_id": "busy-family", "name": "Busy Family",
           "motivations": ["Value for money"],
           "stats": {"post_count": 4200, "source_mix": {"community": 4200}}}
    with patch.object(tools.personas, "resolve", return_value=dict(row)):
        out = tools.dispatch("get_persona", {"persona_id": "busy-family"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is True
    # interpretive_context may join them, but it is a third, separately named
    # block - the two claim types still must not merge into one object.
    assert {"definition_given_to_us", "measured_from_posts"} <= set(out["data"])
    assert "motivations" in out["data"]["definition_given_to_us"]
    assert "interpretive_context" not in out["data"]["definition_given_to_us"]
    assert "interpretive_context" not in out["data"]["measured_from_posts"]
    assert out["data"]["measured_from_posts"]["post_count"] == 4200
    assert "stats" not in out["data"]["definition_given_to_us"]


def test_the_prompt_forbids_reporting_posts_as_people():
    """We hold posts, not users - no commenters, no demographics, no panel. The
    one claim this data cannot support is the one a persona invites."""
    from services.food_intelligence_service.app.assistant import prompts
    text = prompts.SYSTEM_PROMPT.lower()
    assert "posts, not users" in text
    assert "count of posts" in text


def test_trend_ranking_uses_share_not_overlap():
    """Ranked by raw overlap, every persona gets the corpus's biggest trends,
    because a big enough trend overlaps everything."""
    import inspect
    source = inspect.getsource(retrieval._trends_by_membership)
    assert "ORDER BY persona_share_pct DESC" in source
    assert retrieval.PERSONA_TREND_FLOOR >= 10


def test_membership_is_rewritten_not_merged_on_refresh():
    """A refreshed centroid moves. Posts outside the new region have to leave,
    or the persona can only ever grow."""
    import inspect
    source = inspect.getsource(build._write_members)
    assert "DELETE FROM food_intel.persona_post" in source


def test_radius_is_the_one_calibrated_on_the_corpus():
    """0.45 was read off posts sampled in bands outwards from each centre. Moving
    it silently redefines every persona, so it changes only with new evidence."""
    assert build.RADIUS == pytest.approx(0.45)


def test_listing_warns_that_personas_cannot_be_added_up():
    """Measured failure: asked for the fitness persona's share of the market, the
    assistant summed all four persona counts to 107,104 and reported 5.6%. The
    personas overlap - busy-family is 71.7% inside food-explorer - so that
    denominator counts the same post twice, and the answer was a share of posts
    dressed as a share of a market."""
    rows = [{"persona_id": "a", "name": "A", "tagline": "",
             "stats": {"post_count": 10, "unique_authors": 5,
                       "share_of_food_posts_pct": 2.4}}]
    with patch.object(tools.personas, "list_personas", return_value=rows):
        out = tools.dispatch("list_personas", {}, embed_query=lambda q: [0.0])
    assert out["ok"] is True
    assert "must never be added together" in out["message"]
    assert out["data"][0]["share_of_food_posts_pct"] == 2.4, (
        "the correct share travels with the persona so nothing has to derive it")


def test_the_prompt_refuses_headcount_and_market_share():
    from services.food_intelligence_service.app.assistant import prompts
    text = prompts.SYSTEM_PROMPT.lower()
    assert "persona post counts together" in text
    assert "share of shoppers, spend or market" in text


def test_share_is_measured_against_the_corpus_not_the_other_personas():
    import inspect
    source = inspect.getsource(build._stats)
    assert "FROM food_intel.post_food WHERE is_food" in source
    assert "share_of_food_posts_pct" in source


def test_trend_overlap_ignores_superseded_runs():
    """Old runs are still in the trends table. Without the filter the same trend
    came back once per run it appeared in - two rows reading as two findings."""
    import inspect
    source = inspect.getsource(build.top_trends)
    assert "ORDER BY created_at DESC LIMIT 1" in source


def test_pinning_a_persona_is_an_instruction_not_a_hard_filter():
    """Not every question asked while a persona is pinned is about that persona.
    Forcing the argument would answer "how many trends are there in total" with
    one segment's slice of the total."""
    from services.food_intelligence_service.app.assistant import graph
    from services.food_intelligence_service.app.personas import store as pstore
    row = {"persona_id": "busy-family", "name": "Busy Family"}
    with patch.object(pstore, "list_personas", return_value=[row]):
        built = graph._persona_instruction("busy family")
    text, persona_id = built
    assert persona_id == "busy-family"
    assert 'persona="busy-family"' in text
    assert "whole market" in text, "the escape hatch has to be stated"


def test_an_unknown_pin_adds_no_instruction_at_all():
    """A stale pin from a renamed persona must not put a name the tools cannot
    resolve into the system prompt."""
    from services.food_intelligence_service.app.assistant import graph
    from services.food_intelligence_service.app.personas import store as pstore
    with patch.object(pstore, "list_personas", return_value=[]):
        assert graph._persona_instruction("gone") is None
    assert graph._persona_instruction(None) is None
