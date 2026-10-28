from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from services.digital_brand_health.app.api.deps import get_current_user
from services.digital_brand_health.app.services.filters import fetch_banks, fetch_products, fetch_associations
from services.digital_brand_health.app.models.filters import BanksFilterResponse, ProductsFilterResponse, AssociationsFilterResponse


router = APIRouter(prefix="/filters", tags=["Filters"])


@router.get("/banks", response_model=BanksFilterResponse)
async def get_banks(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        banks = await fetch_banks()
        return {"banks": banks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products", response_model=ProductsFilterResponse)
async def get_products(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        products = await fetch_products()
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/associations", response_model=AssociationsFilterResponse)
async def get_associations(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        associations = await fetch_associations()
        return {"associations": associations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
