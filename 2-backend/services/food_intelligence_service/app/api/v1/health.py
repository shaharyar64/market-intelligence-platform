from fastapi import APIRouter
from services.food_intelligence_service.app.db import analysis_store

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    try:
        analysis_store.run_query("SELECT 1")
        postgres_ok = True
    except Exception:
        postgres_ok = False
    return {"status": "healthy", "postgres": "ok" if postgres_ok else "unavailable"}
