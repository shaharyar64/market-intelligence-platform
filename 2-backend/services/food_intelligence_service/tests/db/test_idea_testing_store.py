import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database (with pgvector) to run this test.",
)

_MIGRATION = (Path(__file__).resolve().parents[4]
              / "shared" / "migrations" / "031_create_food_intel_idea_testing.sql")
_SCRATCH_MARKERS = ("scratch", "test", "tmp")


def _assert_scratch_database(dsn: str) -> None:
    name = make_url(dsn).database or ""
    if not any(marker in name.lower() for marker in _SCRATCH_MARKERS):
        raise RuntimeError(
            f"Refusing to run: TEST_POSTGRES_DSN points at database {name!r}, which does not look "
            f"like a scratch database. Point it at a throwaway database whose name contains one of "
            f"{_SCRATCH_MARKERS}."
        )


@pytest.fixture(scope="module")
def scratch_engine():
    _assert_scratch_database(TEST_POSTGRES_DSN)
    engine = create_engine(TEST_POSTGRES_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS food_intel.idea_comparisons CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS food_intel.idea_assessments CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS food_intel.idea_concepts CASCADE"))
        sql = _MIGRATION.read_text(encoding="utf-8")
        for statement in [s.strip() for s in sql.split(";") if s.strip()]:
            conn.execute(text(statement))
    yield engine
    engine.dispose()


def _columns(engine, table: str) -> set[str]:
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'food_intel' AND table_name = :t"), {"t": table})
        return {r[0] for r in rows}


def test_idea_concepts_has_the_expected_columns(scratch_engine):
    assert _columns(scratch_engine, "idea_concepts") == {
        "concept_id", "created_by", "title", "input_format", "raw_text",
        "file_s3_key", "extracted", "created_at",
    }


def test_idea_assessments_has_the_expected_columns(scratch_engine):
    assert _columns(scratch_engine, "idea_assessments") == {
        "assessment_id", "concept_id", "test_type", "headline", "summary", "factor_scores",
        "overall_score", "confidence_score", "confidence_breakdown",
        "recommendations", "trends_run_id", "country", "model",
        "framework_version", "cache_key", "created_at",
    }


def test_idea_comparisons_has_the_expected_columns(scratch_engine):
    assert _columns(scratch_engine, "idea_comparisons") == {
        "comparison_id", "assessment_ids", "winner_assessment_id",
        "factor_leaders", "verdict", "narrative", "created_at",
    }


def test_cache_key_is_unique(scratch_engine):
    with scratch_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO food_intel.idea_concepts "
            "(concept_id, created_by, title, input_format, extracted) "
            "VALUES ('c1', 'user1', 'Test', 'text', '{}'::jsonb)"))
        conn.execute(text(
            "INSERT INTO food_intel.idea_assessments "
            "(assessment_id, concept_id, test_type, headline, summary, factor_scores, overall_score, "
            " confidence_score, confidence_breakdown, recommendations, model, "
            " framework_version, cache_key) "
            "VALUES ('a1', 'c1', 'quick-idea', 'Headline', 'Summary', '[]'::jsonb, 50, 50, '{}'::jsonb, "
            " '[]'::jsonb, 'gpt-4o', 'idea-testing-v1', 'dupekey')"))
        with pytest.raises(Exception):
            conn.execute(text(
                "INSERT INTO food_intel.idea_assessments "
                "(assessment_id, concept_id, test_type, headline, summary, factor_scores, overall_score, "
                " confidence_score, confidence_breakdown, recommendations, model, "
                " framework_version, cache_key) "
                "VALUES ('a2', 'c1', 'quick-idea', 'Headline', 'Summary', '[]'::jsonb, 50, 50, '{}'::jsonb, "
                " '[]'::jsonb, 'gpt-4o', 'idea-testing-v1', 'dupekey')"))


def test_save_and_get_concept_round_trips(scratch_engine, monkeypatch):
    from services.food_intelligence_service.app.idea_testing import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_concept("c10", "user1", "Milestone plan", "text", "raw text", None,
                       {"need": "n", "proposition": "p", "claims": [], "category": "cat",
                        "audience": "a", "cues": []})
    concept = store.get_concept("c10")
    assert concept["title"] == "Milestone plan"
    assert concept["extracted"]["category"] == "cat"


def test_save_and_get_assessment_round_trips(scratch_engine, monkeypatch):
    from services.food_intelligence_service.app.idea_testing import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_concept("c11", "user1", "T", "text", "raw", None, {"category": "cat"})
    store.save_assessment(
        assessment_id="a11", concept_id="c11", test_type="quick-idea",
        headline="Test Headline", summary="Test Summary",
        factor_scores=[{"factor_id": "clutter", "score": 70}], overall_score=70,
        confidence_score=55, confidence_breakdown={"relevance": 60}, recommendations=["Do X"],
        trends_run_id="run-1", country="AE", model="gpt-4o", framework_version="idea-testing-v1",
        cache_key="key-a11")
    assessment = store.get_assessment("a11")
    assert assessment["overall_score"] == 70
    assert assessment["confidence_score"] == 55
    assert assessment["factor_scores"][0]["factor_id"] == "clutter"
    assert assessment["headline"] == "Test Headline"
    assert assessment["summary"] == "Test Summary"


def test_save_assessment_on_conflicting_cache_key_does_not_raise(scratch_engine, monkeypatch):
    from services.food_intelligence_service.app.idea_testing import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_concept("c13", "user1", "T", "text", "raw", None, {})
    kwargs = dict(
        concept_id="c13", test_type="quick-idea", headline="Headline", summary="Summary",
        factor_scores=[], overall_score=50, confidence_score=50, confidence_breakdown={},
        recommendations=[], trends_run_id="run-1", country="AE", model="gpt-4o",
        framework_version="idea-testing-v1", cache_key="conflict-key-13")
    store.save_assessment(assessment_id="a13", **kwargs)
    store.save_assessment(assessment_id="a13-loser", **kwargs)  # must not raise
    winner = store.get_cached_assessment("conflict-key-13")
    assert winner["assessment_id"] == "a13"


def test_get_cached_assessment_finds_by_cache_key(scratch_engine, monkeypatch):
    from services.food_intelligence_service.app.idea_testing import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_concept("c12", "user1", "T", "text", "raw", None, {})
    store.save_assessment(
        assessment_id="a12", concept_id="c12", test_type="quick-idea",
        headline="Headline", summary="Summary",
        factor_scores=[], overall_score=50, confidence_score=50, confidence_breakdown={},
        recommendations=[], trends_run_id="run-1", country=None, model="gpt-4o",
        framework_version="idea-testing-v1", cache_key="unique-key-12")
    hit = store.get_cached_assessment("unique-key-12")
    assert hit["assessment_id"] == "a12"
    assert store.get_cached_assessment("no-such-key") is None


def test_build_cache_key_is_stable_for_identical_inputs():
    from services.food_intelligence_service.app.idea_testing import store
    extracted = {"need": "n", "proposition": "p"}
    key1 = store.build_cache_key(extracted, "run-1", "AE", "gpt-4o", "idea-testing-v1")
    key2 = store.build_cache_key(dict(extracted), "run-1", "AE", "gpt-4o", "idea-testing-v1")
    assert key1 == key2


def test_build_cache_key_changes_with_the_run_id():
    from services.food_intelligence_service.app.idea_testing import store
    extracted = {"need": "n"}
    key1 = store.build_cache_key(extracted, "run-1", "AE", "gpt-4o", "idea-testing-v1")
    key2 = store.build_cache_key(extracted, "run-2", "AE", "gpt-4o", "idea-testing-v1")
    assert key1 != key2


def test_build_cache_key_changes_with_the_country():
    from services.food_intelligence_service.app.idea_testing import store
    extracted = {"need": "n"}
    key1 = store.build_cache_key(extracted, "run-1", "AE", "gpt-4o", "idea-testing-v1")
    key2 = store.build_cache_key(extracted, "run-1", "SA", "gpt-4o", "idea-testing-v1")
    assert key1 != key2
