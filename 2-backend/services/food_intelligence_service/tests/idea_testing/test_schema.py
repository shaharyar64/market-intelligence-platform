import pytest
from pydantic import ValidationError

from services.food_intelligence_service.app.idea_testing.schema import (
    FACTOR_IDS,
    Citation,
    ConceptExtraction,
    FactorScore,
    ScoringResult,
)


def test_factor_ids_match_the_6c_framework():
    assert FACTOR_IDS == ("clutter", "connect", "clarity", "competitive",
                          "credibility", "conversion")


def test_concept_extraction_requires_core_fields():
    concept = ConceptExtraction(
        subject="s", food_relation="food", input_kind="concept", related_dashboard="food", classification_reason="r", need="Buyers want certainty on handover dates",
        proposition="A payment plan tied to construction milestones",
        claims=["Milestone-linked payments"],
        category="off-plan payment plans",
        audience="first-time off-plan buyers",
        cues=["clean, minimal branding"],
    )
    assert concept.category == "off-plan payment plans"


def test_factor_score_rejects_out_of_range_scores():
    with pytest.raises(ValidationError):
        FactorScore(factor_id="clutter", score=150, verdict="x", finding="x", citations=[])


def test_factor_score_rejects_unknown_factor_id():
    with pytest.raises(ValidationError):
        FactorScore(factor_id="not_a_factor", score=50, verdict="x", finding="x", citations=[])


def test_citation_requires_a_quote_and_an_evidence_type():
    cite = Citation(evidence_type="post", platform="instagram", post_id="p1",
                    trend_id=None, quote="Handover was delayed again")
    assert cite.evidence_type == "post"


def test_scoring_result_holds_six_factors_and_recommendations():
    factors = [FactorScore(factor_id=fid, score=60, verdict="Mixed", finding="f",
                           citations=[]) for fid in FACTOR_IDS]
    result = ScoringResult(headline="Promising but unproven", summary="s",
                           factors=factors, recommendations=["Do X", "Do Y"])
    assert len(result.factors) == 6


def test_scoring_result_rejects_fewer_than_six_factors():
    factors = [FactorScore(factor_id=fid, score=60, verdict="Mixed", finding="f",
                           citations=[]) for fid in FACTOR_IDS[:5]]
    with pytest.raises(ValidationError):
        ScoringResult(headline="H", summary="s", factors=factors,
                     recommendations=["Do X", "Do Y"])


def test_scoring_result_rejects_an_empty_factors_list():
    with pytest.raises(ValidationError):
        ScoringResult(headline="H", summary="s", factors=[],
                     recommendations=["Do X", "Do Y"])


def test_scoring_result_rejects_more_than_six_factors():
    factors = [FactorScore(factor_id=fid, score=60, verdict="Mixed", finding="f",
                           citations=[]) for fid in FACTOR_IDS]
    factors.append(FactorScore(factor_id="clutter", score=60, verdict="Mixed", finding="f",
                               citations=[]))
    with pytest.raises(ValidationError):
        ScoringResult(headline="H", summary="s", factors=factors,
                     recommendations=["Do X", "Do Y"])


def test_scoring_result_rejects_a_duplicate_factor_id_covering_only_five_distinct_factors():
    factors = [FactorScore(factor_id=fid, score=60, verdict="Mixed", finding="f",
                           citations=[]) for fid in FACTOR_IDS[:5]]
    factors.append(FactorScore(factor_id=FACTOR_IDS[0], score=60, verdict="Mixed", finding="f",
                               citations=[]))
    with pytest.raises(ValidationError):
        ScoringResult(headline="H", summary="s", factors=factors,
                     recommendations=["Do X", "Do Y"])


def test_citation_accepts_document_evidence_type():
    citation = Citation(evidence_type="document", document_id="d1", quote="A quoted finding.")
    assert citation.evidence_type == "document"
    assert citation.document_id == "d1"


def test_concept_extraction_requires_the_classification_fields():
    with pytest.raises(ValidationError):
        ConceptExtraction(need="n", proposition="p", category="c", audience="a")


def test_concept_extraction_rejects_an_unknown_food_relation():
    with pytest.raises(ValidationError):
        ConceptExtraction(need="n", proposition="p", category="c", audience="a", subject="s",
                          food_relation="maybe", input_kind="concept",
                          related_dashboard="food", classification_reason="r")


def test_every_factor_has_four_named_criteria():
    from services.food_intelligence_service.app.idea_testing.schema import FACTOR_CRITERIA
    assert set(FACTOR_CRITERIA) == set(FACTOR_IDS)
    for criteria in FACTOR_CRITERIA.values():
        assert len(criteria) == 4
        assert len({cid for cid, _ in criteria}) == 4


def _rated(fid, rating=2, criteria=None):
    from services.food_intelligence_service.app.idea_testing.schema import (
        FACTOR_CRITERIA,
        CriterionRating,
        RatedFactor,
    )
    ids = criteria if criteria is not None else [cid for cid, _ in FACTOR_CRITERIA[fid]]
    return RatedFactor(factor_id=fid, finding="f", verdict="v", citations=[],
                       ratings=[CriterionRating(criterion_id=cid, rating=rating) for cid in ids])


def test_rated_scoring_result_requires_each_factors_own_criteria():
    from services.food_intelligence_service.app.idea_testing.schema import RatedScoringResult
    factors = [_rated(fid) for fid in FACTOR_IDS]
    factors[0] = _rated("clutter", criteria=["novel_message", "x", "y", "z"])
    with pytest.raises(ValidationError):
        RatedScoringResult(headline="H", summary="s", factors=factors,
                           recommendations=["Do X", "Do Y"])


def test_criterion_rating_is_bounded_0_to_3():
    from services.food_intelligence_service.app.idea_testing.schema import CriterionRating
    with pytest.raises(ValidationError):
        CriterionRating(criterion_id="novel_message", rating=4)
