from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.services import trend_service


def _resolve_previous(current: str, returns: str | None = None):
    cur = MagicMock()
    cur.fetchone.return_value = (returns,) if returns else None
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    with patch.object(trend_service.store, "get_conn") as gc:
        gc.return_value.__enter__.return_value = conn
        value = trend_service.previous_run_id(current)
    return value, cur.execute.call_args[0]


def test_previous_run_id_never_crosses_markets():
    """The comparison run must be resolved within the current run's own market -
    an all-markets overview must never be diffed against a country run or vice
    versa, which would match unrelated corpora on name slug alone (see D8)."""
    _, call = _resolve_previous("sa-2", returns="sa-1")
    sql = call[0].replace("\n", " ")
    assert "country IS NOT DISTINCT FROM" in sql
    assert "SELECT country FROM food_intel.trends" in sql
    # The market to match is looked up from the run actually being compared,
    # not assumed or hard-coded.
    assert call[1] == ("sa-2", "sa-%", "sa-2")


def test_previous_run_id_excludes_the_current_run():
    _, call = _resolve_previous("all-2", returns="all-1")
    sql = call[0].replace("\n", " ")
    assert "run_id <> %s" in sql
    assert call[1] == ("all-2", "all-%", "all-2")


def test_previous_run_id_stays_within_the_same_kind_of_run():
    """A tracked run must not be diffed against a community "all" run: the two
    corpora differ in size, so the deltas only measured the corpus change."""
    _, call = _resolve_previous("tracked-202610141140", returns=None)
    sql = call[0].replace("\n", " ")
    assert "run_id LIKE %s" in sql
    assert call[1][1] == "tracked-%"


def test_previous_run_id_returns_none_without_a_prior_run():
    value, _ = _resolve_previous("all-1", returns=None)
    assert value is None
