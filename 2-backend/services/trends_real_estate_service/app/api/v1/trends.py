from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.api.errors import internal_error
from services.trends_real_estate_service.app.services import trend_service

router = APIRouter(prefix="/trends", tags=["Trends"])

# ISO 3166-1 alpha-2, the codes the per-country runs carry. Omitted means the
# all-markets run, which is what every page showed before markets existed.
Country = Literal["AE", "SA"]
_COUNTRY = Query(None, description="Market: AE (UAE) or SA (KSA). Omit for all markets.")


def _run_or_404(country: str | None = None) -> str:
    run_id = trend_service.latest_run_id(country)
    if not run_id:
        where = f" for {country}" if country else ""
        raise HTTPException(status_code=404, detail=f"No trend run available yet{where}.")
    return run_id


@router.get("/overview")
async def trends_overview(
    period: str = Query("month", pattern="^(month|cumulative)$"),
    country: Country | None = _COUNTRY,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Overview page payload: KPIs, quadrant map, emerging, movers, umbrellas."""
    run_id = await run_in_threadpool(_run_or_404, country)
    try:
        payload = await run_in_threadpool(trend_service.overview, run_id, period)
    except Exception:
        raise internal_error("trends_overview") from None
    payload["country"] = country
    return payload


@router.get("")
async def list_trends(
    level: str = Query("micro", pattern="^(micro|umbrella)$"),
    period: str = Query("cumulative", pattern="^(month|cumulative)$"),
    quadrant: str | None = Query(None),
    q: str | None = Query(None, description="Name search"),
    country: Country | None = _COUNTRY,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Trends Explorer list."""
    run_id = await run_in_threadpool(_run_or_404, country)
    try:
        rows = await run_in_threadpool(trend_service.list_trends, run_id, level, period)
    except Exception:
        raise internal_error("list_trends") from None
    if quadrant:
        rows = [r for r in rows if r["quadrant"] == quadrant]
    if q:
        rows = [r for r in rows if q.lower() in r["name"].lower()]
    return {"run_id": run_id, "country": country, "trends": rows}


_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/{trend_id}")
async def trend_detail(trend_id: str,
                       date_from: str | None = Query(default=None, pattern=_ISO_DATE),
                       date_to: str | None = Query(default=None, pattern=_ISO_DATE),
                       country: Country | None = _COUNTRY,
                       current_user: dict[str, Any] = Depends(get_current_user)):
    """Full detail for one trend. With a date window, every number, chart and
    example post is recomputed from the posts published inside it."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to.")
    run_id = await run_in_threadpool(_run_or_404, country)
    try:
        detail = await run_in_threadpool(trend_service.trend_detail, run_id, trend_id,
                                         date_from, date_to)
    except Exception:
        raise internal_error("trend_detail") from None
    if detail is None:
        raise HTTPException(status_code=404, detail="Trend not found in the latest run.")
    return detail
