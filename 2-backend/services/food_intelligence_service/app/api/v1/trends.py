from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from services.food_intelligence_service.app.api.deps import get_current_user
from services.food_intelligence_service.app.services import trend_service

router = APIRouter(prefix="/trends", tags=["Trends"])

Country = Literal["SA", "AE"]
_COUNTRY = Query(None, description="Scope to one market. Omit for all markets.")


def _run_or_404(country: str | None = None) -> str:
    run_id = trend_service.latest_run_id(country)
    if not run_id:
        raise HTTPException(status_code=404, detail="No trend run available yet.")
    return run_id


@router.get("/overview")
async def trends_overview(
    period: str = Query("month", pattern="^(month|cumulative)$"),
    country: Country | None = _COUNTRY,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Overview page payload: KPIs, quadrant map, emerging, movers, umbrellas."""
    run_id = await run_in_threadpool(_run_or_404, country)
    try:
        return await run_in_threadpool(trend_service.overview, run_id, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_trends(
    level: str = Query("micro", pattern="^(micro|umbrella)$"),
    period: str = Query("cumulative", pattern="^(month|cumulative)$"),
    quadrant: str | None = Query(None),
    q: str | None = Query(None, description="Name search"),
    country: Country | None = _COUNTRY,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Trends Explorer list."""
    run_id = await run_in_threadpool(_run_or_404, country)
    try:
        rows = await run_in_threadpool(trend_service.list_trends, run_id, level, period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if quadrant:
        rows = [r for r in rows if r["quadrant"] == quadrant]
    if q:
        rows = [r for r in rows if q.lower() in r["name"].lower()]
    return {"run_id": run_id, "trends": rows}


_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/{trend_id}")
async def trend_detail(trend_id: str,
                       date_from: str | None = Query(default=None, pattern=_ISO_DATE),
                       date_to: str | None = Query(default=None, pattern=_ISO_DATE),
                       country: Country | None = _COUNTRY,
                       current_user: Dict[str, Any] = Depends(get_current_user)):
    """Full detail for one trend. With a date window, every number, chart and
    example post is recomputed from the posts published inside it."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to.")
    run_id = await run_in_threadpool(_run_or_404, country)
    try:
        detail = await run_in_threadpool(trend_service.trend_detail, run_id, trend_id,
                                         date_from, date_to)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if detail is None:
        raise HTTPException(status_code=404, detail="Trend not found in the latest run.")
    return detail
