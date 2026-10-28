from fastapi.testclient import TestClient

from services.trends_real_estate_service.app.main import app


def test_root_identifies_the_service():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "trends_real_estate"


def test_health_is_mounted_under_the_v1_prefix():
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_settings_carry_the_project_filters():
    from services.trends_real_estate_service.app.core.config import get_settings

    settings = get_settings()
    assert settings.BRAND_PROJECTS == ["realestate_dbh", "realestate_trends"]
    assert settings.INFLUENCER_PROJECT == "realestate_trends_influencers"
    assert settings.ENRICH_PLATFORMS == ["instagram", "tiktok", "twitter", "linkedin"]
