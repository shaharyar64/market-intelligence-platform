from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.services import trend_service


def _resolve(country, returns="all-1"):
    cur = MagicMock()
    cur.fetchone.return_value = (returns,)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    trend_service._latest_run_cache = {}
    with patch.object(trend_service.store, "get_conn") as gc:
        gc.return_value.__enter__.return_value = conn
        value = trend_service.latest_run_id(country)
    return value, cur.execute.call_args[0]


def test_all_markets_asks_for_a_null_country_run():
    """Without this filter a country run becomes 'the latest run' for every
    caller that did not ask for a market."""
    _, call = _resolve(None)
    assert "country IS NULL" in call[0].replace("\n", " ")


def test_a_market_asks_for_that_market():
    _, call = _resolve("SA")
    assert "country = " in call[0].replace("\n", " ").lower()
    assert "SA" in str(call[1:])


def test_markets_are_cached_separately():
    trend_service._latest_run_cache = {}
    with patch.object(trend_service.store, "get_conn") as gc:
        cur = MagicMock()
        cur.fetchone.side_effect = [("all-1",), ("sa-1",)]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        gc.return_value.__enter__.return_value = conn
        assert trend_service.latest_run_id(None) == "all-1"
        assert trend_service.latest_run_id("SA") == "sa-1"
        # Both cached now, so no further queries.
        assert trend_service.latest_run_id(None) == "all-1"
        assert cur.execute.call_count == 2
