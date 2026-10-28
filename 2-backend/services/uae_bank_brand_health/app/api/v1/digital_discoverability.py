from fastapi import APIRouter, HTTPException, Depends, Query
from services.uae_bank_brand_health.app.services.digital_discoverability import (
    fetch_digital_overall_discoverability,
    fetch_digital_theme_discoverability,
    fetch_digital_product_discoverability,
)
from services.uae_bank_brand_health.app.models.ai_score import (
    AiScoreResponse,
    OverallDiscoverabilityResponse,
)
from services.uae_bank_brand_health.app.api.deps import get_current_user
from typing import Dict, Any

router = APIRouter(prefix="/digital-discoverability", tags=["Digital Discoverability"])


@router.get("/overall", response_model=OverallDiscoverabilityResponse)
async def get_digital_overall_discoverability(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_digital_overall_discoverability(llm)
        return OverallDiscoverabilityResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", response_model=AiScoreResponse)
async def get_digital_theme_discoverability(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_digital_theme_discoverability(llm)
        return AiScoreResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products", response_model=AiScoreResponse)
async def get_digital_product_discoverability(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_digital_product_discoverability(llm)
        return AiScoreResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
