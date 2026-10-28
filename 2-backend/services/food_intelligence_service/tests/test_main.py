from unittest.mock import patch


def test_lifespan_checks_postgres_not_mongo(mock_settings):
    import importlib
    from services.food_intelligence_service.app import main as main_module
    importlib.reload(main_module)

    with patch.object(main_module.analysis_store, "run_query", return_value=[{"1": 1}]) as mock_query:
        import asyncio
        async def _run():
            async with main_module.lifespan(main_module.app):
                pass
        asyncio.run(_run())

    mock_query.assert_called_once()
