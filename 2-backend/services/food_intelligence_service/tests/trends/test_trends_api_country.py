from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.food_intelligence_service.app.api.deps import get_current_user
from services.food_intelligence_service.app.main import app

client = TestClient(app)
_MODULE = "services.food_intelligence_service.app.api.v1.trends"


@pytest.fixture(autouse=True)
def _authenticated():
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test"}
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_country_is_forwarded_to_run_resolution():
    with patch(f"{_MODULE}.trend_service.latest_run_id", return_value="sa-1") as latest, \
         patch(f"{_MODULE}.trend_service.list_trends", return_value=[]):
        client.get("/api/v1/trends?country=SA")
    latest.assert_called_with("SA")


def test_no_country_resolves_the_all_markets_run():
    with patch(f"{_MODULE}.trend_service.latest_run_id", return_value="all-1") as latest, \
         patch(f"{_MODULE}.trend_service.list_trends", return_value=[]):
        client.get("/api/v1/trends")
    latest.assert_called_with(None)


def test_an_unknown_market_is_rejected():
    response = client.get("/api/v1/trends?country=ZZ")
    assert response.status_code == 422


def test_a_market_with_no_run_yet_returns_404():
    """AE has no tracked posts until UAE accounts are onboarded, so its run does
    not exist. That is a 404 with a clear message, not an all-markets fallback."""
    with patch(f"{_MODULE}.trend_service.latest_run_id", return_value=None):
        response = client.get("/api/v1/trends?country=AE")
    assert response.status_code == 404
    assert "trend run" in response.json()["detail"].lower()
