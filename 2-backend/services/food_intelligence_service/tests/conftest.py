import pytest


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+psycopg2://test:test@localhost/test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    from services.food_intelligence_service.app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
