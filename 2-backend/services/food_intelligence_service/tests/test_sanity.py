def test_settings_load(mock_settings):
    from services.food_intelligence_service.app.core.config import get_settings
    s = get_settings()
    assert s.OPENAI_API_KEY == "test-key"
