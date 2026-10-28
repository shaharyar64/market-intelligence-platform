"""The sidebar listing, unpacked against a fake cursor.

This exists because of a bug that shipped: `list_for_user` read r[3] and r[4]
for updated_at and messages, which were the right indices for the food service's
five-column SELECT. Removing personas dropped a column from the query and left
the arithmetic behind, so every call raised

    AttributeError: 'int' object has no attribute 'isoformat'

and the endpoint - which deliberately swallows exceptions so a broken sidebar
cannot stop someone asking a question - returned an empty list. The UI showed
"Your chats will appear here" over a table with rows in it, which is why nobody
noticed for weeks.

No database needed: the failure is in how the tuple is read, not in the SQL.
"""
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from services.trends_real_estate_service.app.assistant import session
from services.trends_real_estate_service.app.trends import store

UPDATED = datetime(2026, 9, 7, 8, 38, 21, tzinfo=timezone.utc)

# conversation_id, title, persona, updated_at, messages - the shape the SELECT
# returns.
ROWS = [
    ("7704cb31", "ROSHN and Dar Al Arkan keep coming up", "luxury-buyer", UPDATED, 4),
    ("79680c34", "Which property trends are breaking out?", None, None, 2),
]


class _Cursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Conn:
    def __init__(self, rows):
        self._cursor = _Cursor(rows)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_conn(monkeypatch):
    conn = _Conn(ROWS)

    @contextmanager
    def _get_conn():
        yield conn

    monkeypatch.setattr(store, "get_conn", _get_conn)
    return conn


def test_list_for_user_reads_the_columns_its_query_selects(fake_conn):
    rows = session.list_for_user("14685458-20d1-70b3-38c8-117faa8ac2a7")

    assert rows == [
        {"conversation_id": "7704cb31",
         "title": "ROSHN and Dar Al Arkan keep coming up",
         "persona": "luxury-buyer",
         "updated_at": "2026-09-07T08:38:21+00:00",
         "messages": 4},
        {"conversation_id": "79680c34",
         "title": "Which property trends are breaking out?",
         "persona": None,
         "updated_at": None,
         "messages": 2},
    ]


def test_the_query_selects_exactly_the_five_columns_unpacked(fake_conn):
    """The unpacking is positional, so the guard has to cover the SELECT too -
    adding or removing a column without shifting the indices reintroduces the
    bug. The order is pinned, not just the presence.
    """
    session.list_for_user("someone")
    sql = fake_conn.cursor().executed[0][0]
    select = sql.split("FROM")[0]
    columns = ("conversation_id", "title", "persona", "updated_at", "messages")
    positions = [select.index(c) for c in columns]
    assert positions == sorted(positions), "SELECT order no longer matches the unpacking"


def test_the_caller_is_always_scoped_by_user(fake_conn):
    """A listing that forgets its WHERE hands one user another user's chats."""
    session.list_for_user("user-abc")
    sql, params = fake_conn.cursor().executed[0]
    assert "user_sub = %s" in sql
    assert params == ("user-abc",)
