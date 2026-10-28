from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from services.saudi_real_estate_service.app.api.deps import get_current_user
from typing import Dict, Any, List, Optional
from services.saudi_real_estate_service.app.services.search_products import (
    fetch_top5_products,
    fetch_product_distribution,
    fetch_product_distribution_over_time,
    fetch_top5_over_time_grouped,
    fetch_top_growing_products,
    fetch_top_growing_products_over_time,
    fetch_maps
)
from services.saudi_real_estate_service.app.models.search_products import (
    Top5ProductsResponse,
    ProductDistributionResponse,
    ProductDistributionOverTimeResponse,
    Top5ProductsOverTimeResponse,
    TopGrowingProductsResponse,
    TopGrowingProductsOverTimeResponse
)


router = APIRouter(prefix="/search-products", tags=["Search Products"])

DATE_DESC = "Defaults to 2025-01-01 if not provided."
END_DATE_DESC = "Defaults to no upper bound if not provided."
PRODUCTS_DESC = "Up to 5 product names. Defaults to top 5 products if not provided."


@router.get("/top5", response_model=Top5ProductsResponse)
async def get_top5_products(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    products: Optional[List[str]] = Query(None, description=PRODUCTS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if products and len(products) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 products.")
    try:
        data = await fetch_top5_products(start_date, end_date, products)
        return {"top5_products": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution", response_model=ProductDistributionResponse)
async def get_product_distribution(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    products: Optional[List[str]] = Query(None, description=PRODUCTS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if products and len(products) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 products.")
    try:
        distribution = await fetch_product_distribution(start_date, end_date, products)
        return {"distribution": distribution}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution-over-time", response_model=ProductDistributionOverTimeResponse)
async def get_product_distribution_over_time(
    frequency: str = Query("3m", enum=["1m", "3m", "6m", "1y"]),
    products: Optional[List[str]] = Query(None, description="Up to 5 product names. Defaults to top 5 products by total search volume."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if products and len(products) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 products.")
    try:
        data = await fetch_product_distribution_over_time(frequency, products, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top5-over-time", response_model=Top5ProductsOverTimeResponse)
async def get_top5_over_time(
    frequency: str = Query("3m", enum=["1m", "3m", "6m", "1y"]),
    products: Optional[List[str]] = Query(None, description="Up to 5 product names. Defaults to top 5 products by avg value."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if products and len(products) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 products.")
    try:
        data = await fetch_top5_over_time_grouped(frequency, products, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-growing", response_model=TopGrowingProductsResponse)
async def get_top_growing_products(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    products: Optional[List[str]] = Query(None, description="Up to 5 product names. When provided, returns exactly these products (ignores `limit`)."),
    limit: Optional[int] = Query(None, ge=1, description="Max rows to return, ordered by growth desc. Omit (and omit `products`) to return every tracked product, including negative growers."),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if products and len(products) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 products.")
    try:
        data = await fetch_top_growing_products(start_date, end_date, products, limit)
        return {"top_growing_products": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-growing-over-time", response_model=TopGrowingProductsOverTimeResponse)
async def get_top_growing_products_over_time(
    frequency: str = Query("1m", enum=["1m", "3m", "6m", "1y"]),
    products: Optional[List[str]] = Query(None, description="Up to 5 product names. Defaults to top 5 fastest-growing products."),
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if products and len(products) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 products.")
    try:
        data = await fetch_top_growing_products_over_time(frequency, products, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/maps")
async def get_maps(
    product: Optional[str] = Query(None, description="Filter region-level scores to a single product. Defaults to all products."),
    start_date: Optional[date] = Query(None, description="Restrict to geographic snapshots refreshed on/after this date. Defaults to no lower bound (all snapshots)."),
    end_date: Optional[date] = Query(None, description="Restrict to geographic snapshots refreshed on/before this date. Defaults to no upper bound (all snapshots)."),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_maps(product, start_date, end_date)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
