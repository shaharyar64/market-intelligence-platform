import pytest
from unittest.mock import patch


def test_every_tool_has_arguments_and_a_description():
    from services.food_intelligence_service.app.assistant.toolargs import TOOL_ARGS
    assert set(TOOL_ARGS) == {"search_trends", "get_trend", "compare_trends",
                              "get_timeline", "aggregate_posts", "search_posts",
                              "list_brands", "get_brand_profile", "create_trend",
                              "list_personas", "get_persona"}
    for name, (model, description) in TOOL_ARGS.items():
        assert description.strip(), f"{name} needs a description - it is what the "                                    "model reads to decide whether the tool applies"
        assert model.model_json_schema()["type"] == "object"


def test_arguments_are_validated_not_merely_advertised():
    """A raw JSON schema is shown to the model and enforced on nothing: an
    invalid quadrant and a limit of "twelve" both reached the tool body, and the
    second would have arrived at SQL as a string."""
    import pydantic
    from services.food_intelligence_service.app.assistant.toolargs import SearchTrendsArgs

    assert SearchTrendsArgs(quadrant="breakthrough").quadrant == "breakthrough"
    for bad in ({"quadrant": "not-a-quadrant"}, {"limit": "twelve"}):
        with pytest.raises(pydantic.ValidationError):
            SearchTrendsArgs(**bad)


def test_enum_values_match_the_quadrants_the_data_uses():
    from services.food_intelligence_service.app.assistant import tools
    from services.food_intelligence_service.app.assistant.toolargs import Quadrant
    import typing
    assert set(typing.get_args(Quadrant)) == tools._QUADRANTS


def test_empty_result_reports_not_found_rather_than_success():
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.retrieval, "search_trends", return_value=[]):
        out = tools.dispatch("search_trends", {"query": "zzz"}, embed_query=lambda q: [0.0])
    assert out["ok"] is False
    assert out["count"] == 0
    assert "no" in out["message"].lower()


def test_successful_result_carries_data_and_count():
    from services.food_intelligence_service.app.assistant import tools
    fake = [{"trend_id": "t1", "name": "Mandi"}]
    with patch.object(tools.retrieval, "search_trends", return_value=fake):
        out = tools.dispatch("search_trends", {"query": "mandi"}, embed_query=lambda q: [0.0])
    assert out["ok"] is True and out["count"] == 1
    assert out["data"] == fake


def test_unknown_tool_is_reported_not_raised():
    from services.food_intelligence_service.app.assistant import tools
    out = tools.dispatch("drop_table", {}, embed_query=lambda q: [0.0])
    assert out["ok"] is False and "unknown" in out["message"].lower()


def test_compare_trends_surfaces_ids_it_could_not_find():
    from services.food_intelligence_service.app.assistant import tools

    def fake_get_trend(trend_id):
        return {"trend_id": trend_id, "name": "Mandi"} if trend_id == "t1" else None

    with patch.object(tools.retrieval, "get_trend", side_effect=fake_get_trend):
        out = tools.dispatch("compare_trends", {"trend_ids": ["t1", "t2", "t3"]},
                              embed_query=lambda q: [0.0])
    assert out["ok"] is True
    assert [d["trend_id"] for d in out["data"]] == ["t1"]
    assert out["not_found"] == ["t2", "t3"]


def test_compare_trends_not_found_present_even_when_none_are_found():
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.retrieval, "get_trend", return_value=None):
        out = tools.dispatch("compare_trends", {"trend_ids": ["t1", "t2"]},
                              embed_query=lambda q: [0.0])
    assert out["ok"] is False
    assert out["not_found"] == ["t1", "t2"]


def test_tool_failure_message_does_not_leak_exception_detail():
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.retrieval, "search_trends",
                      side_effect=RuntimeError("column posts.secret_col does not exist")):
        out = tools.dispatch("search_trends", {"query": "mandi"}, embed_query=lambda q: [0.0])
    assert out["ok"] is False
    assert "secret_col" not in out["message"]
    assert "search_trends" in out["message"]


def test_search_posts_embeds_the_query_once():
    from services.food_intelligence_service.app.assistant import tools
    calls = []

    def fake_embed(q):
        calls.append(q)
        return [0.1] * 1024

    with patch.object(tools.retrieval, "search_posts", return_value=[]):
        tools.dispatch("search_posts", {"query": "mandi"}, embed_query=fake_embed)
    assert calls == ["mandi"]


def test_over_filtered_search_retries_without_the_guessed_filter():
    """A self-chosen quadrant once hid an existing trend and the assistant
    reported 'no data'. The search must retry without it and say it did."""
    from services.food_intelligence_service.app.assistant import tools
    hits = [[], [{"trend_id": "t1", "name": "Dubai Chocolate Desserts"}]]
    with patch.object(tools.retrieval, "search_trends", side_effect=hits):
        out = tools.dispatch("search_trends",
                             {"query": "dubai chocolate", "quadrant": "breakthrough"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is True
    assert out["relaxed_filters"] == ["quadrant='breakthrough'"]
    assert "dropped" in out["message"]


def test_relaxed_retry_still_reports_no_data_when_nothing_matches():
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.retrieval, "search_trends", side_effect=[[], []]):
        out = tools.dispatch("search_trends",
                             {"query": "zzz", "quadrant": "breakthrough"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is False
    assert "relaxed_filters" not in out


def test_unfiltered_miss_does_not_mention_filters():
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.retrieval, "search_trends", return_value=[]):
        out = tools.dispatch("search_trends", {"query": "zzz"},
                             embed_query=lambda q: [0.0])
    assert "Filters applied" not in out["message"]


def test_brand_profile_is_reachable_as_a_tool():
    """Brand enrichment lives in post_analysis, which no tool could read - the
    assistant answered 'no data on Almarai' while 225 analysed posts existed."""
    from services.food_intelligence_service.app.assistant import tools
    profile = {"brand": "Almarai", "analysed_posts": 225,
               "themes": [{"theme": "Cattle Farming", "posts": 12, "evidence": []}],
               "products": [], "keywords": [], "languages": {}, "example_posts": []}
    with patch.object(tools.retrieval, "get_brand_profile", return_value=profile):
        out = tools.dispatch("get_brand_profile", {"brand": "Almarai"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is True
    assert out["count"] == 225
    assert out["data"]["themes"][0]["theme"] == "Cattle Farming"


def test_unknown_brand_points_at_list_brands():
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.retrieval, "get_brand_profile", return_value=None):
        out = tools.dispatch("get_brand_profile", {"brand": "Nestle"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is False
    assert "list_brands" in out["message"]


def test_quadrant_name_used_as_query_is_retried_as_a_quadrant_filter():
    """The model searched query='breakthrough', which matches no trend name and
    returned nothing while 14 breakthrough trends existed."""
    from services.food_intelligence_service.app.assistant import tools
    calls = []

    def fake(query=None, quadrant=None, level="micro", limit=10, persona=None,
             countries=None, embed_query=None):
        calls.append({"query": query, "quadrant": quadrant})
        return [] if query else [{"trend_id": "t1", "name": "Pasta"}]

    with patch.object(tools.retrieval, "search_trends", side_effect=fake):
        out = tools.dispatch("search_trends", {"query": "breakthrough"},
                             embed_query=lambda q: [0.0])
    assert out["ok"] is True
    assert calls[-1] == {"query": None, "quadrant": "breakthrough"}


def test_create_trend_refuses_rather_than_inventing_one():
    """Vector search always returns neighbours, so a thin match must come back
    as a refusal. Reporting a trend that was never stored is the failure mode
    this guards."""
    from services.food_intelligence_service.app.assistant import tools
    with patch.object(tools.adhoc, "build", return_value=None),          patch.object(tools.adhoc, "similar_existing", return_value=[]):
        out = tools.dispatch("create_trend", {"query": "quantum computing"},
                             embed_query=lambda q: [0.0], user_sub="u1")
    assert out["ok"] is False
    assert out["count"] == 0
    assert "not created" in out["message"] or "no trend was" in out["message"]


def test_create_trend_needs_a_topic():
    from services.food_intelligence_service.app.assistant import tools
    out = tools.dispatch("create_trend", {"query": "   "},
                         embed_query=lambda q: [0.0], user_sub="u1")
    assert out["ok"] is False


def test_create_trend_reports_overlap_with_existing_trends():
    """A near-duplicate of a discovered trend should be surfaced, so the answer
    can point at what already covers the topic."""
    from services.food_intelligence_service.app.assistant import tools
    row = {"trend_id": "c-x--1", "name": "Matcha", "quadrant": "mainstream",
           "post_count": 40, "unique_authors": 30, "volume_index": 61.0,
           "growth_index": 40.0, "metrics": {"growth_pct": 1.2, "source_mix": {}}}
    overlaps = [{"trend_id": "t9", "name": "Matcha Cafes", "overlap_posts": 20,
                 "overlap_pct": 50.0}]
    with patch.object(tools.adhoc, "build", return_value=row),          patch.object(tools.adhoc, "similar_existing", return_value=overlaps):
        out = tools.dispatch("create_trend", {"query": "matcha"},
                             embed_query=lambda q: [0.0], user_sub="u1")
    assert out["ok"] is True
    assert out["data"]["already_covered_by"][0]["name"] == "Matcha Cafes"
    assert out["data"]["created"] is True


def test_adhoc_trend_id_is_stable_across_processes():
    """Python's hash() is salted per process; an unstable id created a duplicate
    trend on every repeat of the same question instead of updating it."""
    from services.food_intelligence_service.app.trends import adhoc
    import hashlib
    label, user = "Matcha Lattes", "u-1"
    expected = hashlib.md5(f"{label}|{user}".encode()).hexdigest()[:8]
    assert expected in f"c-{adhoc._slug(label)}--{expected}"
    assert adhoc._slug("Matcha  Lattes!!") == "matcha-lattes"


def test_relaxing_filters_never_drops_the_persona():
    """Widening after an empty result must keep the segment it was asked about.

    The retry drops quadrant and level and says so. It was also dropping
    persona, silently - so a pinned persona whose first search came back empty
    got whole-market trends presented as that persona's, with nothing in the
    envelope to say the segment had been discarded.
    """
    from unittest.mock import patch
    from services.food_intelligence_service.app.assistant import tools

    seen = []

    def fake_search(**kwargs):
        seen.append(kwargs)
        return [] if len(seen) == 1 else [{"trend_id": "t", "name": "T"}]

    with patch.object(tools.retrieval, "search_trends", side_effect=fake_search), \
         patch.object(tools.personas, "resolve",
                      return_value={"persona_id": "busy-family", "name": "Busy Family"}):
        tools.dispatch("search_trends",
                       {"query": "bakery", "quadrant": "mainstream",
                        "persona": "busy-family"},
                       embed_query=lambda q: [0.0])

    assert len(seen) == 2, "expected one widening retry"
    assert seen[1]["persona"] == "busy-family", "persona was dropped by the retry"
    assert seen[1]["quadrant"] is None, "quadrant should have been relaxed"
