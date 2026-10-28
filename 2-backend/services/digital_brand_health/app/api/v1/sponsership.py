from fastapi import APIRouter, HTTPException, Depends
from services.digital_brand_health.app.services.sponsership import fetch_sponsership
from services.digital_brand_health.app.api.deps import get_current_user
from typing import Dict, Any


router = APIRouter(prefix="/sponsorship", tags=["Sponsership"])


async def _get_sponsership_data(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = await fetch_sponsership()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=Dict[str, Dict[str, float]])
@router.get("/", response_model=Dict[str, Dict[str, float]], include_in_schema=False)
async def get_sponsership(current_user: Dict[str, Any] = Depends(get_current_user)):
    return await _get_sponsership_data(current_user)
