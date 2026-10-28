from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.trends import store

_ROW = {"trend_id": "t--abc", "run_id": "sa-1", "level": "micro", "parent_trend_id": None,
        "name": "T", "quadrant": "watchlist", "volume_index": 1.0, "growth_index": 1.0,
        "post_count": 1, "unique_authors": 1, "narrative": {}, "metrics": {}, "timeline": [],
        "example_posts": {}, "member_posts": [], "country": "SA"}


def _run(born):
    cur = MagicMock()
    cur.fetchone.return_value = (born,)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    @contextmanager
    def fake_conn():
        yield conn

    with patch.object(store, "get_conn", fake_conn), \
         patch.object(store.psycopg2.extras, "execute_values") as insert:
        store.replace_run("sa-1", [_ROW])
    sql = [c.args[0] for c in cur.execute.call_args_list]
    return sql, insert, conn


def test_replace_run_deletes_and_inserts_on_one_connection_and_keeps_the_run_age():
    born = datetime(2026, 10, 14, tzinfo=timezone.utc)
    sql, insert, _ = _run(born)
    assert "DELETE FROM food_intel.trends" in sql[1]
    insert.assert_called_once()
    assert "SET created_at" in sql[2]


def test_replace_run_of_a_new_run_leaves_created_at_to_the_default():
    sql, insert, _ = _run(None)
    insert.assert_called_once()
    assert not any("SET created_at" in s for s in sql)
