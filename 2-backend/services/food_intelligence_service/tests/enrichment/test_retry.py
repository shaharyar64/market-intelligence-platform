import pytest


def test_invoke_with_retry_returns_result_on_first_success(mock_settings):
    from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry
    assert invoke_with_retry(lambda: 42, "test_node") == 42


def test_invoke_with_retry_retries_then_succeeds(mock_settings):
    from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("transient")
        return "ok"
    assert invoke_with_retry(flaky, "test_node", max_attempts=3) == "ok"
    assert calls["n"] == 2


def test_invoke_with_retry_raises_node_failed_after_exhausting_attempts(mock_settings):
    from services.food_intelligence_service.app.enrichment.retry import invoke_with_retry, NodeFailed
    def always_fails():
        raise ValueError("boom")
    with pytest.raises(NodeFailed) as exc_info:
        invoke_with_retry(always_fails, "test_node", max_attempts=2)
    assert exc_info.value.node_name == "test_node"
