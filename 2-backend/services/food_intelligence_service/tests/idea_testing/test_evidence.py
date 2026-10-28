from unittest.mock import MagicMock, call

import pytest

from services.food_intelligence_service.app.idea_testing import evidence
from services.food_intelligence_service.app.idea_testing.schema import ConceptExtraction

_CONCEPT = ConceptExtraction(
    subject="s", food_relation="food", input_kind="concept", related_dashboard="food", classification_reason="r", need="Buyers fear handover delays",
    proposition="Milestone-linked payment plan",
    claims=["Payments tied to verified construction milestones"],
    category="off-plan payment plans",
    audience="first-time off-plan buyers",
    cues=["reassuring, transparent tone"],
)


@pytest.fixture(autouse=True)
def _no_real_knowledge_search(monkeypatch):
    monkeypatch.setattr(evidence, "_search_knowledge_chunks", lambda vector, model, limit=3: [])


@pytest.fixture(autouse=True)
def _no_real_trend_search(monkeypatch):
    monkeypatch.setattr(evidence, "nearest_trends", lambda vector, limit, countries=None: [])


def test_gathers_evidence_for_every_factor():
    fake_dispatch = MagicMock(return_value={"ok": True, "data": [], "count": 0, "message": ""})
    result = evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=fake_dispatch)
    assert set(result.keys()) == {"clutter", "connect", "clarity", "competitive",
                                  "credibility", "conversion"}
    for bundle in result.values():
        assert "posts" in bundle
        assert "trends" in bundle


def test_clutter_break_queries_brand_and_influencer_sources_first():
    fake_dispatch = MagicMock(return_value={"ok": True, "data": [], "count": 0, "message": ""})
    evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=fake_dispatch)
    posts_calls = [c for c in fake_dispatch.call_args_list if c.args[0] == "search_posts"]
    clutter_call = posts_calls[0]
    assert clutter_call.args[1]["sources"] == ["brand", "influencer"]


def test_connect_and_conversion_query_community_sources():
    result_calls: list[tuple[str, dict]] = []
    def record(name, args, embed_query):
        result_calls.append((name, dict(args)))
        return {"ok": True, "data": [], "count": 0, "message": ""}
    evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=record)
    community_post_calls = [args for name, args in result_calls if name == "search_posts"
                            and args.get("sources") == ["community"]]
    assert len(community_post_calls) >= 2


def test_countries_filter_is_forwarded_when_given():
    fake_dispatch = MagicMock(return_value={"ok": True, "data": [], "count": 0, "message": ""})
    evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=fake_dispatch,
                             countries=["AE"])
    for c in fake_dispatch.call_args_list:
        assert c.args[1].get("countries") == ["AE"]


def test_trends_are_searched_for_clutter_competitive_and_credibility_only(monkeypatch):
    searched = []
    monkeypatch.setattr(evidence, "nearest_trends",
                        lambda vector, limit, countries=None: searched.append(limit) or [])
    fake_dispatch = MagicMock(return_value={"ok": True, "data": [], "count": 0, "message": ""})
    result = evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=fake_dispatch)
    assert len(searched) == 3
    assert result["connect"]["trends"] is None
    assert result["competitive"]["trends"] is not None
    assert all(c.args[0] == "search_posts" for c in fake_dispatch.call_args_list)


def test_gather_evidence_searches_the_knowledge_base_for_every_factor():
    from unittest.mock import patch

    from services.food_intelligence_service.app.idea_testing import evidence
    from services.food_intelligence_service.app.idea_testing.schema import ConceptExtraction

    concept = ConceptExtraction(subject="s", food_relation="food", input_kind="concept", related_dashboard="food", classification_reason="r", need="n", proposition="p", claims=["c"], category="cat",
                                audience="a", cues=[])

    def make_chunks(vector, model, limit=3):
        return [{"chunk_id": f"d1-{search.call_count}", "document_id": "d1",
                 "chunk_text": "relevant", "distance": 0.1}]

    with patch(f"{evidence.__name__}._search_knowledge_chunks", side_effect=make_chunks) as search:
        result = evidence.gather_evidence(concept, embed_query=lambda q: [0.0],
                                          dispatch=lambda *a, **k: {"ok": False, "data": [], "count": 0})
    assert search.call_count == 6  # one call per 6C factor
    for factor_id in evidence.FACTOR_IDS:
        assert result[factor_id]["documents"]["ok"] is True
        assert result[factor_id]["documents"]["count"] == 1


def test_every_factor_keeps_the_documents_it_retrieved():
    """A small library means the same chunk is often the nearest match for several
    factors. Dropping it from all but the first starved the factors that sort last,
    which are exactly the ones that need market data (credibility, conversion), so
    every factor keeps whatever it retrieved."""
    from unittest.mock import patch

    from services.food_intelligence_service.app.idea_testing import evidence
    from services.food_intelligence_service.app.idea_testing.schema import ConceptExtraction

    concept = ConceptExtraction(subject="s", food_relation="food", input_kind="concept", related_dashboard="food", classification_reason="r", need="n", proposition="p", claims=["c"], category="cat",
                                audience="a", cues=[])
    shared_chunk = {"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "relevant", "distance": 0.1}

    with patch(f"{evidence.__name__}._search_knowledge_chunks", return_value=[shared_chunk]):
        result = evidence.gather_evidence(concept, embed_query=lambda q: [0.0],
                                          dispatch=lambda *a, **k: {"ok": False, "data": [], "count": 0})

    for factor_id in evidence.FACTOR_IDS:
        assert result[factor_id]["documents"]["data"] == [shared_chunk], factor_id
        assert result[factor_id]["documents"]["count"] == 1, factor_id
        assert result[factor_id]["documents"]["ok"] is True, factor_id


def test_evidence_block_spells_a_repeated_chunk_out_only_once():
    """Keeping a chunk on every factor must not repeat its full text six times in
    the prompt; later factors get a pointer back to the copy already quoted."""
    from services.food_intelligence_service.app.idea_testing.scoring import _evidence_block

    chunk = {"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "AED 1,749 psf citywide"}
    bundle = {"posts": {"ok": False, "data": [], "message": "none"}, "trends": None,
              "documents": {"ok": True, "count": 1, "data": [chunk]}}
    block = _evidence_block({"clutter": bundle, "credibility": dict(bundle)})

    assert block.count("AED 1,749 psf citywide") == 1
    assert "match for this factor, quoted above: chunk_id d1-0" in block
    # The later factor still sees that the document applies to it.
    assert block.count("Documents (1):") == 2


def test_every_retrieved_post_is_kept_however_far_it_is():
    def fake(name, args, embed_query):
        return {"ok": True, "count": 2, "message": "",
                "data": [{"post_id": "near", "distance": 0.35}, {"post_id": "far", "distance": 0.8}]}
    result = evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=fake)
    assert [p["post_id"] for p in result["clutter"]["posts"]["data"]] == ["near", "far"]


def test_trends_keep_the_market_filter_instead_of_widening(monkeypatch):
    seen = {}
    def nearest(vector, limit, countries=None):
        seen["countries"] = countries
        return [{"trend_id": "t1", "distance": 0.5, "country_posts": 3}]
    monkeypatch.setattr(evidence, "nearest_trends", nearest)
    fake_dispatch = MagicMock(return_value={"ok": True, "data": [], "count": 0, "message": ""})
    result = evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0],
                                      dispatch=fake_dispatch, countries=["AE"])
    assert seen["countries"] == ["AE"]
    assert result["clutter"]["trends"] == {"ok": True, "count": 1, "message": "",
                                           "data": [{"trend_id": "t1", "distance": 0.5,
                                                     "country_posts": 3}]}


def test_post_searches_record_whether_they_were_limited_to_some_sources():
    fake_dispatch = MagicMock(return_value={"ok": True, "data": [], "count": 0, "message": ""})
    result = evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=fake_dispatch)
    assert result["credibility"]["source_filter"] is None
    assert result["clutter"]["source_filter"] == ["brand", "influencer"]


def test_specifics_sharpen_the_queries_that_need_them():
    concept = _CONCEPT.model_copy(update={"specifics": ["Dubai Marina", "AED 1.2m"]})
    queries = {}
    def record(name, args, embed_query):
        queries.setdefault(len(queries), args["query"])
        return {"ok": True, "data": [], "count": 0, "message": ""}
    evidence.gather_evidence(concept, embed_query=lambda q: [0.0], dispatch=record)
    with_specifics = [i for i, q in queries.items() if "Dubai Marina AED 1.2m" in q]
    assert with_specifics == [0, 1, 3, 4, 5]
    assert _CONCEPT.specifics == []


def test_specific_chunks_fill_each_factor_after_its_own_top_three():
    from services.food_intelligence_service.app.idea_testing.evidence import _with_specific_chunks

    own = [{"chunk_id": f"o{i}"} for i in range(5)]
    specific = [{"chunk_id": "o1"}, {"chunk_id": "s1"}, {"chunk_id": "s2"}, {"chunk_id": "s3"}]
    picked = [c["chunk_id"] for c in _with_specific_chunks(own, specific)]
    assert picked == ["o0", "o1", "o2", "s1", "s2"]


def test_without_specific_chunks_a_factor_keeps_its_own_top_five():
    from services.food_intelligence_service.app.idea_testing.evidence import _with_specific_chunks

    own = [{"chunk_id": f"o{i}"} for i in range(6)]
    assert [c["chunk_id"] for c in _with_specific_chunks(own, [])] == ["o0", "o1", "o2", "o3", "o4"]
