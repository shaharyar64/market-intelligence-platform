"""The personas a caller can answer the assistant's questions as.

Served from the same definitions the assistant reads, so the picker can never
offer a persona the assistant does not know.
"""
from typing import Any

from fastapi import APIRouter, Depends

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.personas import definitions

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("")
async def list_personas(current_user: dict[str, Any] = Depends(get_current_user)):
    return {"personas": definitions.summaries()}
