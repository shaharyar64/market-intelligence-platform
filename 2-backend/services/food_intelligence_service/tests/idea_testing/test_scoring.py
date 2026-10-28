from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.idea_testing import scoring
from services.food_intelligence_service.app.idea_testing.schema import (
    FACTOR_IDS,
    ConceptExtraction,
    ScoringResult,
)

_CONCEPT = ConceptExtraction(
    subject="s", food_relation="food", input_kind="concept", related_dashboard="food", classification_reason="r", need="need", proposition="prop", claims=["c1"], category="cat",
    audience="aud", cues=["cue"],
)
_EVIDENCE = {
    fid: {"posts": {"ok": True, "data": [{"platform": "instagram", "post_id": f"{fid}1",
                                          "caption": "example", "distance": 0.3}],
                    "count": 1, "message": ""},
         "trends": None}
    for fid in FACTOR_IDS
}
def _stub_result():
    from services.food_intelligence_service.app.idea_testing.schema import (
        FACTOR_CRITERIA,
        CriterionRating,
        RatedFactor,
        RatedScoringResult,
    )
    return RatedScoringResult(
        headline="Headline", summary="Summary", recommendations=["Do X", "Do Y"],
        factors=[RatedFactor(factor_id=fid, finding="f", verdict="Mixed", citations=[],
                             ratings=[CriterionRating(criterion_id=cid, rating=2)
                                      for cid, _ in FACTOR_CRITERIA[fid]])
                 for fid in FACTOR_IDS])


_STUB_RESULT = _stub_result()


def test_score_concept_returns_a_scoring_result_built_from_the_llm_ratings():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB_RESULT
    with patch.object(scoring, "_structured_llm", return_value=fake_llm):
        result = scoring.score_concept(_CONCEPT, _EVIDENCE)
    assert isinstance(result, ScoringResult)
    assert result.headline == "Headline"
    assert [f.score for f in result.factors] == [67] * 6


def test_score_concept_includes_every_factors_evidence_in_the_prompt():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB_RESULT
    with patch.object(scoring, "_structured_llm", return_value=fake_llm):
        scoring.score_concept(_CONCEPT, _EVIDENCE)
    messages = fake_llm.invoke.call_args[0][0]
    user_content = messages[1].content
    for fid in FACTOR_IDS:
        assert f"{fid}1" in user_content  # the fake post_id for that factor


def test_score_concept_prompt_forbids_uncited_evidence():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB_RESULT
    with patch.object(scoring, "_structured_llm", return_value=fake_llm):
        scoring.score_concept(_CONCEPT, _EVIDENCE)
    messages = fake_llm.invoke.call_args[0][0]
    assert "only" in messages[0].content.lower()
    assert "invent" in messages[0].content.lower()


def test_evidence_block_includes_document_evidence():
    evidence_by_factor = {
        "clutter": {
            "posts": {"ok": False, "data": [], "message": "none"},
            "trends": None,
            "documents": {"ok": True, "count": 1,
                          "data": [{"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "insight"}]},
        }
    }
    block = scoring._evidence_block(evidence_by_factor)
    assert "Documents (1):" in block
    assert "d1-0" in block


def test_system_prompt_explains_how_to_cite_a_document():
    assert "document_id" in scoring._SYSTEM_PROMPT
    assert "—" not in scoring._SYSTEM_PROMPT and "–" not in scoring._SYSTEM_PROMPT


def _rated_result(rating_by_factor):
    from services.food_intelligence_service.app.idea_testing.schema import (
        FACTOR_CRITERIA,
        CriterionRating,
        RatedFactor,
        RatedScoringResult,
    )
    return RatedScoringResult(
        headline="H", summary="S", recommendations=["Do X", "Do Y"],
        factors=[RatedFactor(factor_id=fid, finding="f", verdict="v", citations=[],
                             ratings=[CriterionRating(criterion_id=cid, rating=r)
                                      for (cid, _), r in zip(FACTOR_CRITERIA[fid],
                                                             rating_by_factor[fid])])
                 for fid in FACTOR_IDS])


def _score_with(rated, evidence=_EVIDENCE):
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = rated
    with patch.object(scoring, "_structured_llm", return_value=fake_llm):
        return scoring.score_concept(_CONCEPT, evidence)


def test_factor_score_is_computed_from_the_criterion_ratings():
    ratings = {fid: [3, 3, 3, 3] for fid in FACTOR_IDS}
    ratings["clutter"] = [0, 0, 0, 0]
    ratings["clarity"] = [3, 2, 1, 1]
    result = _score_with(_rated_result(ratings))
    scores = {f.factor_id: f.score for f in result.factors}
    assert scores["clutter"] == 0
    assert scores["clarity"] == 58
    assert scores["connect"] == 100


def test_scored_factors_carry_their_criterion_breakdown():
    result = _score_with(_rated_result({fid: [1, 2, 3, 0] for fid in FACTOR_IDS}))
    clutter = next(f for f in result.factors if f.factor_id == "clutter")
    assert [c.rating for c in clutter.criteria] == [1, 2, 3, 0]
    assert all(c.label for c in clutter.criteria)


def test_a_factor_with_no_evidence_is_not_capped():
    evidence = dict(_EVIDENCE)
    evidence["competitive"] = {"posts": {"ok": False, "data": [], "count": 0, "message": "none"},
                               "trends": {"ok": False, "data": [], "count": 0, "message": "none"},
                               "documents": {"ok": False, "data": [], "count": 0}}
    result = _score_with(_rated_result({fid: [3, 3, 3, 3] for fid in FACTOR_IDS}), evidence)
    scores = {f.factor_id: f.score for f in result.factors}
    assert scores["competitive"] == 100
    assert scores["clutter"] == 100


def test_system_prompt_lists_every_criterion():
    from services.food_intelligence_service.app.idea_testing.schema import FACTOR_CRITERIA
    for criteria in FACTOR_CRITERIA.values():
        for cid, _ in criteria:
            assert cid in scoring._SYSTEM_PROMPT


def test_evidence_block_labels_how_closely_each_post_matches():
    block = scoring._evidence_block({
        "clutter": {"posts": {"ok": True, "count": 2, "data": [
            {"post_id": "p1", "distance": 0.31}, {"post_id": "p2", "distance": 0.52}]},
                    "trends": None}})
    assert '"match": "strong"' in block
    assert '"match": "weak"' in block


def test_evidence_block_labels_documents_by_match_too():
    block = scoring._evidence_block({
        "clutter": {"posts": {"ok": False, "data": [], "message": "none"}, "trends": None,
                    "documents": {"ok": True, "count": 1, "data": [
                        {"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "x",
                         "distance": 0.31}]}}})
    assert '"match": "strong"' in block


def test_repeated_document_keeps_its_own_match_label_per_factor():
    chunk = {"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "x"}
    none = {"ok": False, "data": [], "message": "none"}
    block = scoring._evidence_block({
        "clutter": {"posts": none, "trends": None,
                    "documents": {"ok": True, "count": 1, "data": [{**chunk, "distance": 0.55}]}},
        "connect": {"posts": none, "trends": None,
                    "documents": {"ok": True, "count": 1, "data": [{**chunk, "distance": 0.31}]}},
    })
    assert '"match": "weak"' in block
    assert "strong match for this factor, quoted above: chunk_id d1-0" in block


def test_system_prompt_requires_citations_and_accepts_qualitative_research():
    assert "MUST cite 1 to 3 items" in scoring._SYSTEM_PROMPT
    assert "Qualitative research counts too" in scoring._SYSTEM_PROMPT


def test_system_prompt_explains_market_share_on_trends():
    assert "country_share_pct" in scoring._SYSTEM_PROMPT


def test_evidence_block_keeps_non_ascii_text_readable():
    evidence_by_factor = {
        "clutter": {
            "posts": {"ok": False, "data": [], "message": "none"},
            "trends": None,
            "documents": {"ok": True, "count": 1, "data": [
                {"chunk_id": "d1-0", "document_id": "d1", "chunk_text": "Farm’s Select • عصائر"}]},
        }
    }
    block = scoring._evidence_block(evidence_by_factor)
    assert "Farm’s Select • عصائر" in block
