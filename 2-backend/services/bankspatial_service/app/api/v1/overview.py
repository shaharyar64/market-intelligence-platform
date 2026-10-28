from fastapi import APIRouter
from services.bankspatial_service.app.services.overview import (
    get_kpis,
    get_categories,
    get_rating_distribution,
    get_network_strength_by_branches,
    get_filters
)

router = APIRouter(
    prefix="/overview",
    tags=["Bank Spatial Overview"]
)


@router.get("/kpis")
async def fetch_kpis(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None,
    category: str = None
):
    return await get_kpis(cluster, sub_cluster, zone, country, category)


@router.get("/categories")
async def fetch_kpis(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None,
    category: str = None
):
    return await get_categories(cluster, sub_cluster, zone, country, category)


@router.get("/rating-distribution")
async def fetch_rating_distribution(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None,
    category: str = None
):
    return await get_rating_distribution(cluster, sub_cluster, zone, country, category)


@router.get("/network-strength")
async def fetch_network_strength(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None
):
    return await get_network_strength_by_branches(cluster, sub_cluster, zone, country)


@router.get("/filters")
async def fetch_filters():
    return await get_filters()
