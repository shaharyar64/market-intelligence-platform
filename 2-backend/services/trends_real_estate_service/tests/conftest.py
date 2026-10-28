import os

import pytest


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    if os.getenv("RUN_LIVE_PERSONA_TESTS") == "1":
        # The opt-in persona quality check exercises the configured model and
        # retrieval store. Replacing its AWS credentials with test placeholders
        # makes the live database secret impossible to resolve.
        yield
        return
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    from services.trends_real_estate_service.app.assistant import guard, intent
    from services.trends_real_estate_service.app.core.config import get_settings
    monkeypatch.setattr(intent, "_complete", lambda *a, **k: "{}")
    monkeypatch.setattr(guard, "review_general",
                        lambda *, answer, **k: {"status": "pass", "answer": answer,
                                                "removed": []})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
