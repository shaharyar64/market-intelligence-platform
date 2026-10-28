from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from services.saudi_real_estate_service.app.api.deps import get_current_user

from services.saudi_real_estate_service.app.services.exclusive_summary import (
    fetch_top_digital_health,
    fetch_digital_equity_trend,
    fetch_top3_banks_trend,
)
from services.saudi_real_estate_service.app.models.exclusive_summary import (
    TopDigitalHealthResponse,
    DigitalEquityTrendResponse,
    Top3BanksTrendResponse
)

router = APIRouter(prefix="/exclusive-summary", tags=["Exclusive Summary"])


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
    bank: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 banks by avg score."),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top3_banks_trend(freq, bank)
        return {"top3_banks_trend": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
