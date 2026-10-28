from unittest.mock import MagicMock, call

import pytest

from services.trends_real_estate_service.app.idea_testing import evidence
from services.trends_real_estate_service.app.idea_testing.schema import ConceptExtraction

_CONCEPT = ConceptExtraction(
    need="Buyers fear handover delays",
    proposition="Milestone-linked payment plan",
    claims=["Payments tied to verified construction milestones"],
    category="off-plan payment plans",
    audience="first-time off-plan buyers",
    cues=["reassuring, transparent tone"],
)


@pytest.fixture(autouse=True)
def _no_real_knowledge_search(monkeypatch):
    monkeypatch.setattr(evidence, "_search_knowledge_chunks", lambda vector, model, limit=3: [])


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


def test_competitive_edge_also_checks_brand_trend_participation():
    calls = []
    def record(name, args, embed_query):
        calls.append(name)
        return {"ok": True, "data": [], "count": 0, "message": ""}
    evidence.gather_evidence(_CONCEPT, embed_query=lambda q: [0.0], dispatch=record)
    assert "search_trends" in calls


def test_gather_evidence_searches_the_knowledge_base_for_every_factor():
    from unittest.mock import patch

    from services.trends_real_estate_service.app.idea_testing import evidence
    from services.trends_real_estate_service.app.idea_testing.schema import ConceptExtraction

    concept = ConceptExtraction(need="n", proposition="p", claims=["c"], category="cat",
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

    from services.trends_real_estate_service.app.idea_testing import evidence
    from services.trends_real_estate_service.app.idea_testing.schema import ConceptExtraction

    concept = ConceptExtraction(need="n", proposition="p", claims=["c"], category="cat",
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
    from services.trends_real_estate_service.app.idea_testing.scoring import _evidence_block

    chunk = {"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "AED 1,749 psf citywide"}
    bundle = {"posts": {"ok": False, "data": [], "message": "none"}, "trends": None,
              "documents": {"ok": True, "count": 1, "data": [chunk]}}
    block = _evidence_block({"clutter": bundle, "credibility": dict(bundle)})

    assert block.count("AED 1,749 psf citywide") == 1
    assert "also relevant here, quoted above: chunk_id d1-0" in block
    # The later factor still sees that the document applies to it.
    assert block.count("Documents (1):") == 2
