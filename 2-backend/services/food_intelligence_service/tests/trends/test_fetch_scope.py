from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.trends import store


def _captured_sql(**kwargs):
    cur = MagicMock()
    cur.fetchmany.return_value = []
    cur.description = []
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    with patch.object(store, "get_conn") as gc:
        gc.return_value.__enter__.return_value = conn
        store.fetch_cohort_posts("all", "tag", **kwargs)
    return " ".join(str(c.args[0]) for c in cur.execute.call_args_list), cur.execute.call_args_list


def test_country_adds_a_filter_and_parameter():
    sql, calls = _captured_sql(country="SA")
    assert "country" in sql.lower()
    assert any("SA" in str(c.args[1:]) for c in calls)


def test_exclude_authors_adds_a_negated_filter():
    sql, calls = _captured_sql(exclude_authors=["spam_account"])
    assert "author_username" in sql.lower()
    assert any("spam_account" in str(c.args[1:]) for c in calls)


def test_no_country_adds_no_country_filter():
    sql, _ = _captured_sql()
    assert "p.country" not in sql
