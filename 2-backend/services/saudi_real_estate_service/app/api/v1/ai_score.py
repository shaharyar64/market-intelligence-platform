from fastapi import APIRouter, HTTPException, Depends, Query
from services.saudi_real_estate_service.app.services.ai_score import (
    fetch_overall_discoverability,
    fetch_theme_discoverability,
    fetch_product_discoverability,
    fetch_market_positioning_discoverability,
    fetch_audience_affinity,
    fetch_citations,
    fetch_brand_projection,
    fetch_ai_score_banks,
)
from services.saudi_real_estate_service.app.models.filters import BanksFilterResponse
from services.saudi_real_estate_service.app.models.ai_score import (
    AiScoreResponse,
    OverallDiscoverabilityResponse,
    AudienceAffinityResponse,
    CitationsResponse,
    BrandProjectionResponse,
)
from services.saudi_real_estate_service.app.api.deps import get_current_user
from typing import Dict, Any

router = APIRouter(prefix="/ai-score", tags=["AI Score"])


@router.get("/banks", response_model=BanksFilterResponse)
async def get_ai_score_banks(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Banks that have AI Score / Perception data, for the Perception tab's bank filter."""
    try:
        banks = await fetch_ai_score_banks()
        return {"banks": banks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overall", response_model=OverallDiscoverabilityResponse)
async def get_overall_discoverability(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_overall_discoverability(llm)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", response_model=AiScoreResponse)
async def get_ai_score_services(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_theme_discoverability(llm)
        return AiScoreResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products", response_model=AiScoreResponse)
async def get_ai_score_products(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_product_discoverability(llm)
        return AiScoreResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-positioning", response_model=AiScoreResponse)
async def get_market_positioning_discoverability(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """No banking equivalent — real-estate-only AI-perception dimension."""
    try:
        data = await fetch_market_positioning_discoverability(llm)
        return AiScoreResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audience-affinity", response_model=AudienceAffinityResponse)
async def get_audience_affinity(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    bank: str | None = Query(default=None, description="Filter by exact bank name"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_audience_affinity(llm, bank)
        return AudienceAffinityResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citations", response_model=CitationsResponse)
async def get_citations(
    llm: str | None = Query(
        default=None, description="ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_citations(llm)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brand-projection", response_model=BrandProjectionResponse)
async def get_brand_projection(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    bank: str | None = Query(default=None, description="Filter by exact bank name"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_brand_projection(llm, bank)
        return BrandProjectionResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
