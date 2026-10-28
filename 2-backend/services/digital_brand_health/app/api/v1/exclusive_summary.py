from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from services.digital_brand_health.app.api.deps import get_current_user

from services.digital_brand_health.app.services.exclusive_summary import (
    fetch_brand_iq_snapshot,
    fetch_brand_iq_trend,
    fetch_top_digital_health,
    fetch_digital_equity_trend,
    fetch_top3_banks_trend,
)
from services.digital_brand_health.app.models.exclusive_summary import (
    BrandIQSnapshotResponse,
    BrandIQTrendResponse,
    TopDigitalHealthResponse,
    DigitalEquityTrendResponse,
    Top3BanksTrendResponse
)

router = APIRouter(prefix="/exclusive-summary", tags=["Exclusive Summary"])


@router.get("/brand-iq/{segment}/snapshot", response_model=BrandIQSnapshotResponse)
async def get_brand_iq_snapshot(
    segment: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the normal or digital BrandIQ snapshot."""
    if segment not in {"normal", "digital"}:
        raise HTTPException(status_code=400, detail="segment must be 'normal' or 'digital'")
    try:
        return {"snapshot": await fetch_brand_iq_snapshot(segment)}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/brand-iq/{segment}/trend", response_model=BrandIQTrendResponse)
async def get_brand_iq_trend(
    segment: str,
    banks: Optional[List[str]] = Query(None, description="Optional bank names; Average is always included."),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the normal or digital BrandIQ trend."""
    if segment not in {"normal", "digital"}:
        raise HTTPException(status_code=400, detail="segment must be 'normal' or 'digital'")
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        return {"trend": await fetch_brand_iq_trend(segment, banks)}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/top-digital-health", response_model=TopDigitalHealthResponse)
async def get_top_digital_health(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = await fetch_top_digital_health()
        return {"top_digital_health": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/digital-equity-trend", response_model=DigitalEquityTrendResponse)
async def get_digital_equity_trend(
    freq: str = "1m",
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_digital_equity_trend(freq)
        return {"digital_equity_trend": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top3-banks-trend", response_model=Top3BanksTrendResponse)
async def get_top3_banks_trend(
    freq: str = "1m",
    banks: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 banks by avg score."),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top3_banks_trend(freq, banks)
        return {"top3_banks_trend": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
