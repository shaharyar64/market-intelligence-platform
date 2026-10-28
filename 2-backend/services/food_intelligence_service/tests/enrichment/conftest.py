import pytest


@pytest.fixture(autouse=True)
def reset_agent_graph():
    from services.food_intelligence_service.app.enrichment import agent
    agent._GRAPH = None
    yield
    agent._GRAPH = None
