from unittest.mock import MagicMock, patch

from services.trends_real_estate_service.app.idea_testing import store


def test_build_cache_key_changes_with_country():
    extracted = {"need": "n"}
    key_ae = store.build_cache_key(extracted, "run-1", "AE", "gpt-4o", "idea-testing-v1")
    key_sa = store.build_cache_key(extracted, "run-1", "SA", "gpt-4o", "idea-testing-v1")
    assert key_ae != key_sa


def test_build_cache_key_two_markets_with_no_run_still_differ_by_country():
    # Both AE and SA have no run of their own (trends_run_id is None for
    # both) -- country alone must still separate their cache entries.
    extracted = {"need": "n"}
    key_ae = store.build_cache_key(extracted, None, "AE", "gpt-4o", "idea-testing-v1")
    key_sa = store.build_cache_key(extracted, None, "SA", "gpt-4o", "idea-testing-v1")
    assert key_ae != key_sa


def test_build_cache_key_is_stable_for_identical_inputs():
    extracted = {"need": "n", "proposition": "p"}
    key1 = store.build_cache_key(extracted, "run-1", "AE", "gpt-4o", "idea-testing-v1")
    key2 = store.build_cache_key(dict(extracted), "run-1", "AE", "gpt-4o", "idea-testing-v1")
    assert key1 == key2


def _mock_conn_and_cursor():
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    conn_ctx = MagicMock()
    conn_ctx.__enter__.return_value = conn
    conn_ctx.__exit__.return_value = False
    return conn_ctx, cur


def test_save_assessment_inserts_with_on_conflict_do_nothing():
    conn_ctx, cur = _mock_conn_and_cursor()
    with patch.object(store, "get_conn", return_value=conn_ctx):
        store.save_assessment(
            assessment_id="a1", concept_id="c1", test_type="quick-idea", headline="H",
            summary="S", factor_scores=[], overall_score=50, confidence_score=50,
            confidence_breakdown={}, recommendations=[], trends_run_id=None, country=None,
            model="gpt-4o", framework_version="idea-testing-v1", cache_key="key1")
    executed_sql = cur.execute.call_args[0][0]
    assert "ON CONFLICT (cache_key) DO NOTHING" in executed_sql
