import os
import asyncio
import time


os.environ["DEBUG"] = "false"


def test_health_is_available_under_v1_prefix():
    from fastapi.testclient import TestClient
    from services.ceer_campaign_service.app.main import app

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ceer_campaign"}


def test_slow_database_does_not_block_health(monkeypatch):
    import httpx
    from services.ceer_campaign_service.app.main import app
    from services.ceer_campaign_service.app.services import campaign

    def slow_overview():
        time.sleep(0.25)
        return {"kpis": {}, "platforms": []}

    monkeypatch.setattr(campaign, "get_overview", slow_overview)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(client.get("/api/v1/campaign/overview"))
            await asyncio.sleep(0.02)
            health = await client.get("/api/v1/health")
            was_pending = not pending.done()
            await pending
            assert health.status_code == 200
            assert was_pending, "A slow campaign query blocked the health endpoint"

    asyncio.run(check())
