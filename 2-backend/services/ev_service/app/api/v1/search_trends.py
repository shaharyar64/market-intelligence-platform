from fastapi import APIRouter, Query
from typing import Optional
from services.ev_service.app.services.search_trends import (
    fetch_top5_products,
    fetch_product_distribution,
    fetch_top5_over_time_grouped,
    fetch_top_growing_products,
    fetch_top_growing_products_over_time
)

router = APIRouter(
    prefix="/search-trends",
    tags=["search trends"]
)


@router.get("/themes/top5-products")
async def get_top5_products(country: Optional[str] = Query(default="Overall")):
    return await fetch_top5_products(country)


@router.get("/themes/product-distribution")
async def get_product_distribution(country: Optional[str] = Query(default="Overall")):
    return await fetch_product_distribution(country)


@router.get("/themes/top5-over-time")
async def get_top5_over_time_grouped(
    frequency: str = Query(default="1m"),
    country: Optional[str] = Query(default="Overall"),
):
    return await fetch_top5_over_time_grouped(frequency, country)


@router.get("/themes/top-growing-products")
async def get_top_growing_products(country: Optional[str] = Query(default="Overall")):
    return await fetch_top_growing_products(country)


@router.get("/themes/top-growing-products-over-time")
async def get_top_growing_products_over_time(
    frequency: str = Query(default="1m"),
    country: Optional[str] = Query(default="Overall"),
):
    return await fetch_top_growing_products_over_time(frequency, country)
