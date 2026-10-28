from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from services.bank_brand_health.app.api.deps import get_current_user
from services.bank_brand_health.app.services.search_data import (
    fetch_top5_banks,
    fetch_bank_distribution,
    fetch_bank_distribution_over_time,
    fetch_top5_banks_over_time_grouped,
    fetch_top_growing_banks,
    fetch_top_growing_banks_over_time,
    fetch_maps
)
from services.bank_brand_health.app.models.search_data import (
    Top5BanksResponse,
    BankDistributionResponse,
    BankDistributionOverTimeResponse,
    Top5BanksOverTimeResponse,
    TopGrowingBanksResponse,
    TopGrowingBanksOverTimeResponse
)


router = APIRouter(prefix="/search-data", tags=["Search Data"])

DATE_DESC = "Defaults to 2025-01-01 if not provided."
END_DATE_DESC = "Defaults to no upper bound if not provided."
BANKS_DESC = "Up to 5 bank names. Defaults to top 5 banks if not provided."


@router.get("/top5", response_model=Top5BanksResponse)
async def get_top5_banks(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    banks: Optional[List[str]] = Query(None, description=BANKS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top5_banks(start_date, end_date, banks)
        return {"top5_banks": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution", response_model=BankDistributionResponse)
async def get_bank_distribution(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    banks: Optional[List[str]] = Query(None, description=BANKS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        distribution = await fetch_bank_distribution(start_date, end_date, banks)
        return {"distribution": distribution}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution-over-time", response_model=BankDistributionOverTimeResponse)
async def get_bank_distribution_over_time(
    frequency: str = Query("3m", enum=["1m", "3m", "6m", "1y"]),
    banks: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 banks by total search volume."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_bank_distribution_over_time(frequency, banks, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top5-over-time", response_model=Top5BanksOverTimeResponse)
async def get_top5_banks_over_time(
    frequency: str = Query("3m", enum=["1m", "3m", "6m", "1y"]),
    banks: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 banks by avg value."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top5_banks_over_time_grouped(frequency, banks, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-growing", response_model=TopGrowingBanksResponse)
async def get_top_growing_banks(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    banks: Optional[List[str]] = Query(None, description="Up to 5 bank names. When provided, returns exactly these banks (ignores `limit`)."),
    limit: Optional[int] = Query(None, ge=1, description="Max rows to return, ordered by growth desc. Omit (and omit `banks`) to return every tracked bank, including negative growers."),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top_growing_banks(start_date, end_date, banks, limit)
        return {"top_growing_banks": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-growing-over-time", response_model=TopGrowingBanksOverTimeResponse)
async def get_top_growing_banks_over_time(
    frequency: str = Query("1m", enum=["1m", "3m", "6m", "1y"]),
    banks: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 fastest-growing banks."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if banks and len(banks) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top_growing_banks_over_time(frequency, banks, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/maps")
async def get_maps(
    bank: Optional[str] = Query(None, description="Filter region-level scores to a single bank. Defaults to all banks."),
    start_date: Optional[date] = Query(None, description="Restrict to geographic snapshots refreshed on/after this date. Defaults to no lower bound (all snapshots)."),
    end_date: Optional[date] = Query(None, description="Restrict to geographic snapshots refreshed on/before this date. Defaults to no upper bound (all snapshots)."),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_maps(bank, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
