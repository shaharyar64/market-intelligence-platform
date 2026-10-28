"""Per-market trend runs: the API picks a market's run only when asked for it."""
from fastapi.testclient import TestClient

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.main import app
from services.trends_real_estate_service.app.services import trend_service
from services.trends_real_estate_service.app.trends import store


def _client(monkeypatch, runs: dict):
    """A client whose latest run per market comes from `runs`, recording each
    market the endpoints asked for."""
    asked: list = []

    def latest(country=None):
        asked.append(country)
        return runs.get(country)

    monkeypatch.setattr(trend_service, "latest_run_id", latest)
    monkeypatch.setattr(trend_service, "list_trends", lambda run_id, level, period: [
        {"name": f"trend of {run_id}", "quadrant": "watchlist"}])
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test"}
    return TestClient(app), asked


def test_list_defaults_to_the_all_markets_run(monkeypatch):
    client, asked = _client(monkeypatch, {None: "tracked-1", "AE": "ae-1"})
    try:
        body = client.get("/api/v1/trends").json()
    finally:
        app.dependency_overrides.clear()
    assert asked == [None]
    assert body["run_id"] == "tracked-1" and body["country"] is None


def test_list_serves_the_requested_market(monkeypatch):
    client, asked = _client(monkeypatch, {None: "tracked-1", "SA": "sa-1"})
    try:
        body = client.get("/api/v1/trends", params={"country": "SA"}).json()
    finally:
        app.dependency_overrides.clear()
    assert asked == ["SA"]
    assert body["run_id"] == "sa-1" and body["country"] == "SA"
    assert body["trends"][0]["name"] == "trend of sa-1"


def test_unknown_market_is_rejected(monkeypatch):
    client, _ = _client(monkeypatch, {None: "tracked-1"})
    try:
        response = client.get("/api/v1/trends", params={"country": "KW"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_market_without_a_run_says_so(monkeypatch):
    client, _ = _client(monkeypatch, {None: "tracked-1"})
    try:
        response = client.get("/api/v1/trends", params={"country": "SA"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert "for SA" in response.json()["detail"]


def test_default_readers_never_pick_a_market_run():
    # Brand pages, the assistant and ad-hoc trends read "the latest run" through
    # this query. A market run written after an all-markets run must not become
    # theirs.
    assert "country IS NULL" in store.LATEST_RUN_SQL


def test_trend_rows_carry_their_market():
    assert "country" in store.TREND_COLUMNS


def _route(monkeypatch, runs: dict):
    """search_trends with its runs stubbed; returns which path each call took."""
    from services.trends_real_estate_service.app.assistant import retrieval
    took: list = []
    monkeypatch.setattr(retrieval, "_latest_run", lambda country=None: runs.get(country))
    monkeypatch.setattr(retrieval, "_search_run",
                        lambda run_id, *a: took.append(("run", run_id)) or [])
    monkeypatch.setattr(retrieval, "_trends_by_country",
                        lambda *a: took.append(("share", a[4])) or [])
    return retrieval.search_trends, took


def test_assistant_answers_one_market_from_that_markets_run(monkeypatch):
    search, took = _route(monkeypatch, {None: "tracked-1", "SA": "sa-1"})
    search(countries=["SA"])
    assert took == [("run", "sa-1")]


def test_assistant_treats_both_markets_as_the_whole_market(monkeypatch):
    search, took = _route(monkeypatch, {None: "tracked-1", "SA": "sa-1", "AE": "ae-1"})
    search(countries=["SA", "AE"])
    assert took == [("run", None)]


def test_assistant_falls_back_to_share_without_a_market_run(monkeypatch):
    search, took = _route(monkeypatch, {None: "tracked-1"})
    search(countries=["AE"])
    assert took == [("share", ["AE"])]
