from fastapi import APIRouter
from services.bankspatial_service.app.services.maps import (
    fetch_map_data
)

router = APIRouter(
    prefix="/maps",
    tags=["Bank Spatial Maps"]
)

@router.get("/map-data")
async def get_map_data(
    cluster: str = None,
    sub_cluster: str = None,
    zone: str = None,
    country: str = None,
    category: str = None
):
    return await fetch_map_data(
        cluster=cluster,
        sub_cluster=sub_cluster,
        zone=zone,
        country=country,
        category=category
    )
