from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from services.saudi_real_estate_service.app.api.deps import get_current_user
from services.saudi_real_estate_service.app.services.search_data import (
    fetch_top5_banks,
    fetch_bank_distribution,
    fetch_bank_distribution_over_time,
    fetch_top5_banks_over_time_grouped,
    fetch_top_growing_banks,
    fetch_top_growing_banks_over_time,
    fetch_maps,
    fetch_search_data_banks
)
from services.saudi_real_estate_service.app.models.search_data import (
    Top5BanksResponse,
    BankDistributionResponse,
    BankDistributionOverTimeResponse,
    Top5BanksOverTimeResponse,
    TopGrowingBanksResponse,
    TopGrowingBanksOverTimeResponse
)
from services.saudi_real_estate_service.app.models.filters import BanksFilterResponse


router = APIRouter(prefix="/search-data", tags=["Search Data"])


@router.get("/banks", response_model=BanksFilterResponse)
async def get_search_data_banks(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Developer keywords available in this router's data — use these exact
    spellings for the `banks`/`bank` params below, not /filters/banks (a
    different, shorter name vocabulary sourced from social_data)."""
    try:
        banks = await fetch_search_data_banks()
        return {"banks": banks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

DATE_DESC = "Defaults to 2025-01-01 if not provided."
END_DATE_DESC = "Defaults to no upper bound if not provided."
BANKS_DESC = "Up to 5 bank names. Defaults to top 5 banks if not provided."


@router.get("/top5", response_model=Top5BanksResponse)
async def get_top5_banks(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    bank: Optional[List[str]] = Query(None, description=BANKS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top5_banks(start_date, end_date, bank)
        return {"top5_banks": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution", response_model=BankDistributionResponse)
async def get_bank_distribution(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    bank: Optional[List[str]] = Query(None, description=BANKS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        distribution = await fetch_bank_distribution(start_date, end_date, bank)
        return {"distribution": distribution}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution-over-time", response_model=BankDistributionOverTimeResponse)
async def get_bank_distribution_over_time(
    frequency: str = Query("3m", enum=["1m", "3m", "6m", "1y"]),
    bank: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 banks by total search volume."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_bank_distribution_over_time(frequency, bank, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top5-over-time", response_model=Top5BanksOverTimeResponse)
async def get_top5_banks_over_time(
    frequency: str = Query("3m", enum=["1m", "3m", "6m", "1y"]),
    bank: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 banks by avg value."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top5_banks_over_time_grouped(frequency, bank, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-growing", response_model=TopGrowingBanksResponse)
async def get_top_growing_banks(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    bank: Optional[List[str]] = Query(None, description="Up to 5 bank names. When provided, returns exactly these banks (ignores `limit`)."),
    limit: Optional[int] = Query(None, ge=1, description="Max rows to return, ordered by growth desc. Omit (and omit `bank`) to return every tracked bank, including negative growers."),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top_growing_banks(start_date, end_date, bank, limit)
        return {"top_growing_banks": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-growing-over-time", response_model=TopGrowingBanksOverTimeResponse)
async def get_top_growing_banks_over_time(
    frequency: str = Query("1m", enum=["1m", "3m", "6m", "1y"]),
    bank: Optional[List[str]] = Query(None, description="Up to 5 bank names. Defaults to top 5 fastest-growing banks."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_top_growing_banks_over_time(frequency, bank, start_date, end_date)
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
