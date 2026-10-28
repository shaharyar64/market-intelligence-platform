from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.services.user_directory import resolve_email

_MODULE = "services.food_intelligence_service.app.services.user_directory"


def _fake_connect(row):
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_resolve_email_returns_email_when_lookup_succeeds():
    conn = _fake_connect(("user@example.com",))
    with patch(f"{_MODULE}.shared_db.get_uri", return_value="postgresql+psycopg2://u:p@h:5432/dashboards"), \
         patch(f"{_MODULE}.psycopg2.connect", return_value=conn):
        assert resolve_email("some-sub") == "user@example.com"


def test_resolve_email_returns_none_when_no_matching_row():
    conn = _fake_connect(None)
    with patch(f"{_MODULE}.shared_db.get_uri", return_value="postgresql+psycopg2://u:p@h:5432/dashboards"), \
         patch(f"{_MODULE}.psycopg2.connect", return_value=conn):
        assert resolve_email("no-such-sub") is None


def test_resolve_email_returns_none_when_connection_fails():
    with patch(f"{_MODULE}.shared_db.get_uri", return_value="postgresql+psycopg2://u:p@h:5432/dashboards"), \
         patch(f"{_MODULE}.psycopg2.connect", side_effect=OSError("unreachable")):
        assert resolve_email("some-sub") is None
