from datetime import date, datetime, timezone
from unittest.mock import ANY, MagicMock, patch

import pytest

from services.trends_real_estate_service.app.idea_testing import service
from services.trends_real_estate_service.app.idea_testing.schema import (
    FACTOR_IDS,
    ConceptExtraction,
    FactorScore,
    ScoringResult,
)

_CONCEPT = ConceptExtraction(need="n", proposition="p", claims=[], category="cat",
                             audience="a", cues=[])
_SCORING = ScoringResult(
    headline="H", summary="S",
    factors=[FactorScore(factor_id=fid, score=70, verdict="v", finding="f", citations=[])
            for fid in FACTOR_IDS],
    recommendations=["Do X", "Do Y"])
_EMPTY_ENVELOPE = {"ok": False, "data": [], "count": 0, "message": "no data"}


def _evidence_stub(*a, **k):
    return {fid: {"posts": _EMPTY_ENVELOPE, "trends": None} for fid in FACTOR_IDS}


def _final_row(**overrides) -> dict:
    row = {"assessment_id": "a1", "concept_id": "c1", "title": "Balcony Herb Kits",
           "test_type": "quick-idea",
           "headline": "H", "summary": "S", "factor_scores": [], "overall_score": 70,
           "confidence_score": 50, "confidence_breakdown": {}, "recommendations": [],
           "trends_run_id": "run-1", "country": "AE", "model": "gpt-4o",
           "framework_version": "idea-testing-v1", "cache_key": "key1",
           "created_at": "2026-01-01T00:00:00Z"}
    row.update(overrides)
    return row


def test_assess_concept_returns_a_cached_result_when_present():
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment",
                      return_value=_final_row()) as cached, \
         patch.object(service, "gather_evidence") as fake_gather:
        result = service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    assert result["cached"] is True
    assert result["assessment_id"] == "a1"
    assert result["title"] == "Balcony Herb Kits"
    fake_gather.assert_not_called()  # cache hit skips retrieval entirely


def test_assess_concept_cached_result_never_leaks_the_cache_key():
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment", return_value=_final_row()):
        result = service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    assert "cache_key" not in result


def test_assess_concept_runs_the_full_pipeline_on_a_cache_miss():
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment",
                      side_effect=[None, _final_row()]), \
         patch.object(service.store, "data_as_of", return_value=_AS_OF), \
         patch.object(service.store, "save_assessment") as save, \
         patch.object(service, "gather_evidence", side_effect=_evidence_stub), \
         patch.object(service, "score_concept", return_value=_SCORING):
        result = service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    assert result["cached"] is False
    assert result["overall_score"] == 70  # simple average of six 70s
    assert result["title"] == "Balcony Herb Kits"
    save.assert_called_once()


def test_assess_concept_cache_hit_and_cache_miss_share_the_same_response_shape():
    hit_keys = None
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment", return_value=_final_row()):
        hit = service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    hit_keys = set(hit) - {"cached"}

    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment",
                      side_effect=[None, _final_row()]), \
         patch.object(service.store, "data_as_of", return_value=_AS_OF), \
         patch.object(service.store, "save_assessment"), \
         patch.object(service, "gather_evidence", side_effect=_evidence_stub), \
         patch.object(service, "score_concept", return_value=_SCORING):
        miss =service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    miss_keys = set(miss) - {"cached"}

    assert hit_keys == miss_keys
    assert "cache_key" not in hit_keys


def test_assess_concept_raises_when_the_concept_does_not_exist():
    with patch.object(service.store, "get_concept", return_value=None):
        with pytest.raises(service.ConceptNotFoundError):
            service.assess_concept("does-not-exist", "quick-idea", "run-1", "AE",
                                   embed_query=lambda q: [0.0])


def test_assess_concept_falls_back_to_the_all_markets_run_id_for_the_cache_key_when_none():
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service, "trend_service") as fake_trend_service, \
         patch.object(service.store, "build_cache_key", return_value="key1") as build_key, \
         patch.object(service.store, "get_cached_assessment", return_value=_final_row()):
        fake_trend_service.latest_run_id.return_value = "all-markets-run"
        service.assess_concept("c1", "quick-idea", None, "SA", embed_query=lambda q: [0.0])
    fake_trend_service.latest_run_id.assert_called_once_with(None)
    build_key.assert_called_once_with(_CONCEPT.model_dump(), "all-markets-run", "SA", ANY, ANY)


def test_assess_concept_does_not_call_the_fallback_when_a_run_id_is_given():
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service, "trend_service") as fake_trend_service, \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment", return_value=_final_row()):
        service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    fake_trend_service.latest_run_id.assert_not_called()


def test_assess_and_compare_rejects_more_than_three_concepts():
    with pytest.raises(ValueError):
        service.assess_and_compare(["c1", "c2", "c3", "c4"], "quick-idea", "run-1", "AE",
                                   embed_query=lambda q: [0.0])


def test_assess_and_compare_scores_each_concept_independently_then_compares():
    with patch.object(service, "assess_concept") as fake_assess, \
         patch.object(service.store, "save_comparison") as save_cmp:
        fake_assess.side_effect = [
            {"assessment_id": "a1", "concept_id": "c1", "title": "Balcony Herb Kits",
             "overall_score": 80,
             "factor_scores": [{"factor_id": fid, "score": 80} for fid in FACTOR_IDS]},
            {"assessment_id": "a2", "concept_id": "c2", "title": "Rooftop Compost Pods",
             "overall_score": 60,
             "factor_scores": [{"factor_id": fid, "score": 60} for fid in FACTOR_IDS]},
        ]
        result = service.assess_and_compare(["c1", "c2"], "quick-idea", "run-1", "AE",
                                            embed_query=lambda q: [0.0])
    assert fake_assess.call_count == 2
    assert result["comparison"]["winner_assessment_id"] == "a1"  # deterministic: highest overall_score
    assert result["comparison"]["verdict"] == "Balcony Herb Kits scores highest overall (80/100)."
    assert result["comparison"]["narrative"] == (
        "Balcony Herb Kits scored 80/100. Rooftop Compost Pods scored 60/100.")
    save_cmp.assert_called_once()


def test_assess_and_compare_skips_comparison_for_a_single_concept():
    with patch.object(service, "assess_concept",
                      return_value={"assessment_id": "a1", "concept_id": "c1",
                                   "overall_score": 80, "factor_scores": []}):
        result = service.assess_and_compare(["c1"], "quick-idea", "run-1", "AE",
                                            embed_query=lambda q: [0.0])
    assert result["comparison"] is None


def _post(platform: str, post_id: str, distance: float, source: str, author: str,
          posted_at: datetime = datetime(2026, 8, 1, tzinfo=timezone.utc)) -> dict:
    return {"platform": platform, "post_id": post_id, "distance": distance,
            "source": source, "author_username": author, "posted_at": posted_at}


def test_confidence_inputs_deduplicates_a_post_seen_in_multiple_factor_bundles():
    # The same (platform, post_id) is returned by three different factor
    # bundles (as clutter/connect/conversion routinely do in practice).
    shared = _post("instagram", "p1", 0.2, "community", "user1")
    only_in_clutter = _post("instagram", "p2", 0.3, "brand", "user2")
    evidence_by_factor = {
        "clutter": {"posts": {"ok": True, "data": [shared, only_in_clutter]}, "trends": None},
        "connect": {"posts": {"ok": True, "data": [dict(shared)]}, "trends": None},
        "clarity": {"posts": {"ok": False, "data": [], "message": "none"}, "trends": None},
        "competitive": {"posts": {"ok": False, "data": [], "message": "none"}, "trends": None},
        "credibility": {"posts": {"ok": False, "data": [], "message": "none"}, "trends": None},
        "conversion": {"posts": {"ok": True, "data": [dict(shared)]}, "trends": None},
    }
    inputs = service._confidence_inputs(evidence_by_factor)
    assert inputs["total_posts"] == 2  # shared counted once, only_in_clutter once
    assert inputs["sources"] == {"community", "brand"}
    assert inputs["authors"] == {"user1", "user2"}
    assert len(inputs["distances"]) == 2


def test_confidence_inputs_dedup_changes_the_computed_confidence_score():
    shared = _post("instagram", "p1", 0.2, "community", "user1")
    evidence_dup = {fid: {"posts": {"ok": True, "data": [dict(shared)]}, "trends": None}
                    for fid in FACTOR_IDS}
    evidence_single = {"clutter": {"posts": {"ok": True, "data": [dict(shared)]}, "trends": None},
                       **{fid: {"posts": {"ok": False, "data": [], "message": "none"},
                               "trends": None}
                          for fid in FACTOR_IDS if fid != "clutter"}}
    dup_conf = service._compute_confidence(evidence_dup, _AS_OF)
    single_conf = service._compute_confidence(evidence_single, _AS_OF)
    assert dup_conf["components"]["volume"] == single_conf["components"]["volume"]
    assert dup_conf["components"]["quality"] == single_conf["components"]["quality"]


_AS_OF = date(2026, 8, 31)


def test_compute_confidence_recency_is_the_share_of_posts_from_the_last_year():
    recent = _post("instagram", "p1", 0.2, "community", "u1")
    old = _post("instagram", "p2", 0.2, "community", "u2",
                posted_at=datetime(2019, 10, 9, tzinfo=timezone.utc))
    evidence = {"clutter": {"posts": {"ok": True, "data": [recent, old]}, "trends": None},
                **{fid: {"posts": _EMPTY_ENVELOPE, "trends": None}
                   for fid in FACTOR_IDS if fid != "clutter"}}
    conf = service._compute_confidence(evidence, _AS_OF)
    assert conf["components"]["recency"] == 50.0


def test_compute_confidence_recency_is_0_when_every_post_is_old():
    old = _post("instagram", "p1", 0.2, "community", "u1",
                posted_at=datetime(2022, 4, 19, tzinfo=timezone.utc))
    evidence = {fid: {"posts": {"ok": True, "data": [dict(old)]}, "trends": None}
                for fid in FACTOR_IDS}
    assert service._compute_confidence(evidence, _AS_OF)["components"]["recency"] == 0.0


def test_assess_concept_anchors_recency_on_the_datas_as_of_date():
    with patch.object(service.store, "get_concept",
                      return_value={"concept_id": "c1", "title": "Balcony Herb Kits",
                                   "extracted": _CONCEPT.model_dump()}), \
         patch.object(service.store, "build_cache_key", return_value="key1"), \
         patch.object(service.store, "get_cached_assessment", side_effect=[None, _final_row()]), \
         patch.object(service.store, "data_as_of", return_value=_AS_OF) as as_of, \
         patch.object(service.store, "save_assessment"), \
         patch.object(service, "gather_evidence", side_effect=_evidence_stub), \
         patch.object(service, "score_concept", return_value=_SCORING):
        service.assess_concept("c1", "quick-idea", "run-1", "AE", embed_query=lambda q: [0.0])
    as_of.assert_called_once_with("run-1")


def test_shape_assessment_adds_a_confidence_label_and_explanation():
    row = _final_row(confidence_score=64, confidence_breakdown={
        "relevance": 37.4, "volume": 86.7, "spread": 100.0, "recency": 25.0, "quality": 66.7})
    shaped = service.shape_assessment(row, cached=False)
    assert shaped["confidence_label"] == "Good"
    assert shaped["confidence_explanation"].startswith("Plenty of relevant posts")


def _row_with_citations(*citations: dict) -> dict:
    return _final_row(factor_scores=[
        {"factor_id": "credibility", "score": 60, "verdict": "v", "finding": "f",
         "citations": list(citations)}])


def test_shape_assessment_attaches_the_stored_post_url_to_each_post_citation():
    post = {"evidence_type": "post", "platform": "instagram", "post_id": "Cch4COJLchq",
            "trend_id": None, "quote": "q"}
    with patch.object(service.store, "post_urls",
                      return_value={("instagram", "Cch4COJLchq"): "https://www.instagram.com/p/Cch4COJLchq"}) as urls:
        shaped = service.shape_assessment(_row_with_citations(post), cached=True)
    urls.assert_called_once_with({("instagram", "Cch4COJLchq")})
    citation = shaped["factor_scores"][0]["citations"][0]
    assert citation["post_url"] == "https://www.instagram.com/p/Cch4COJLchq"


def test_shape_assessment_drops_non_http_post_urls():
    post = {"evidence_type": "post", "platform": "x", "post_id": "p1", "trend_id": None, "quote": "q"}
    with patch.object(service.store, "post_urls", return_value={("x", "p1"): "javascript:alert(1)"}):
        shaped = service.shape_assessment(_row_with_citations(post), cached=True)
    assert shaped["factor_scores"][0]["citations"][0]["post_url"] is None


def test_shape_assessment_skips_the_url_lookup_when_nothing_cites_a_post():
    trend = {"evidence_type": "trend", "platform": None, "post_id": None, "trend_id": "t1", "quote": "q"}
    with patch.object(service.store, "post_urls") as urls:
        shaped = service.shape_assessment(_row_with_citations(trend), cached=True)
    urls.assert_not_called()
    assert shaped["factor_scores"][0]["citations"][0]["post_url"] is None


def test_shape_assessment_does_not_mutate_the_stored_row():
    post = {"evidence_type": "post", "platform": "instagram", "post_id": "p1", "trend_id": None, "quote": "q"}
    row = _row_with_citations(post)
    with patch.object(service.store, "post_urls", return_value={("instagram", "p1"): "https://x.test/p1"}):
        service.shape_assessment(row, cached=True)
    assert "post_url" not in row["factor_scores"][0]["citations"][0]


def test_shape_assessment_resolves_an_active_document_citation():
    from services.trends_real_estate_service.app.idea_testing import service
    row = _final_row(factor_scores=[
        {"factor_id": "credibility", "score": 60, "verdict": "v", "finding": "f",
         "citations": [{"evidence_type": "document", "document_id": "d1", "quote": "q"}]}])
    with patch.object(service.store, "post_urls", return_value={}), \
         patch.object(service.knowledge_store, "document_status",
                      return_value={"d1": {"title": "Q3 Outlook", "deleted_at": None}}) as lookup:
        shaped = service.shape_assessment(row, cached=True)
    lookup.assert_called_once_with({"d1"})
    citation = shaped["factor_scores"][0]["citations"][0]
    assert citation["document_title"] == "Q3 Outlook"
    assert citation["document_deleted"] is False


def test_shape_assessment_flags_a_deleted_document_citation():
    from services.trends_real_estate_service.app.idea_testing import service
    row = _final_row(factor_scores=[
        {"factor_id": "credibility", "score": 60, "verdict": "v", "finding": "f",
         "citations": [{"evidence_type": "document", "document_id": "d1", "quote": "frozen quote"}]}])
    with patch.object(service.store, "post_urls", return_value={}), \
         patch.object(service.knowledge_store, "document_status",
                      return_value={"d1": {"title": "Q3 Outlook", "deleted_at": "2026-09-17T00:00:00Z"}}):
        shaped = service.shape_assessment(row, cached=True)
    citation = shaped["factor_scores"][0]["citations"][0]
    assert citation["document_deleted"] is True
    assert citation["quote"] == "frozen quote"  # the quote itself survives deletion


def test_shape_assessment_skips_the_document_lookup_when_nothing_cites_a_document():
    from services.trends_real_estate_service.app.idea_testing import service
    row = _final_row(factor_scores=[
        {"factor_id": "credibility", "score": 60, "verdict": "v", "finding": "f",
         "citations": [{"evidence_type": "post", "platform": "instagram", "post_id": "p1", "quote": "q"}]}])
    with patch.object(service.store, "post_urls", return_value={}), \
         patch.object(service.knowledge_store, "document_status") as lookup:
        service.shape_assessment(row, cached=True)
    lookup.assert_not_called()


def test_shape_assessment_explains_rows_with_an_empty_breakdown():
    shaped = service.shape_assessment(_final_row(confidence_breakdown={}), cached=True)
    assert shaped["confidence_label"] == "Moderate"
    assert shaped["confidence_explanation"]


def test_get_comparison_by_id_returns_assessments_in_original_order():
    comparison_row = {
        "comparison_id": "cmp1", "assessment_ids": ["a2", "a1"],
        "winner_assessment_id": "a2", "factor_leaders": [{"factor_id": "clutter", "assessment_id": "a2"}],
        "verdict": "B wins", "narrative": "B scored higher than A.",
    }
    rows_by_id = {
        "a1": _final_row(assessment_id="a1", title="Concept A", overall_score=50),
        "a2": _final_row(assessment_id="a2", title="Concept B", overall_score=80),
    }
    with patch.object(service.store, "get_comparison", return_value=comparison_row), \
         patch.object(service.store, "get_assessment", side_effect=lambda aid: rows_by_id[aid]):
        result = service.get_comparison_by_id("cmp1")
    assert [a["assessment_id"] for a in result["assessments"]] == ["a2", "a1"]
    assert result["comparison"]["comparison_id"] == "cmp1"
    assert result["comparison"]["winner_assessment_id"] == "a2"
    assert all(a["cached"] is True for a in result["assessments"])


def test_get_comparison_by_id_raises_when_comparison_is_missing():
    with patch.object(service.store, "get_comparison", return_value=None):
        with pytest.raises(service.ComparisonNotFoundError):
            service.get_comparison_by_id("no-such-id")


def test_get_comparison_by_id_raises_when_a_referenced_assessment_is_missing():
    comparison_row = {
        "comparison_id": "cmp1", "assessment_ids": ["a1", "a-deleted"],
        "winner_assessment_id": "a1", "factor_leaders": [], "verdict": "v", "narrative": "n",
    }
    with patch.object(service.store, "get_comparison", return_value=comparison_row), \
         patch.object(service.store, "get_assessment",
                      side_effect=lambda aid: _final_row(assessment_id="a1") if aid == "a1" else None):
        with pytest.raises(service.ComparisonNotFoundError):
            service.get_comparison_by_id("cmp1")
