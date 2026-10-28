from unittest.mock import MagicMock, patch

from services.trends_real_estate_service.app.idea_testing import scoring
from services.trends_real_estate_service.app.idea_testing.schema import (
    FACTOR_IDS,
    ConceptExtraction,
    FactorScore,
    ScoringResult,
)

_CONCEPT = ConceptExtraction(
    need="need", proposition="prop", claims=["c1"], category="cat",
    audience="aud", cues=["cue"],
)
_EVIDENCE = {
    fid: {"posts": {"ok": True, "data": [{"platform": "instagram", "post_id": f"{fid}1",
                                          "caption": "example", "distance": 0.3}],
                    "count": 1, "message": ""},
         "trends": None}
    for fid in FACTOR_IDS
}
_STUB_RESULT = ScoringResult(
    headline="Headline", summary="Summary",
    factors=[FactorScore(factor_id=fid, score=60, verdict="Mixed", finding="f", citations=[])
            for fid in FACTOR_IDS],
    recommendations=["Do X", "Do Y"],
)


def test_score_concept_returns_the_llm_result():
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = _STUB_RESULT
    with patch.object(scoring, "_structured_llm", return_value=fake_llm):
        result = scoring.score_concept(_CONCEPT, _EVIDENCE)
    assert result == _STUB_RESULT


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
