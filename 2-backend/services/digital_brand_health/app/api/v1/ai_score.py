from fastapi import APIRouter, HTTPException, Depends, Query
from services.digital_brand_health.app.services.ai_score import (
    fetch_overall_discoverability,
    fetch_theme_discoverability,
    fetch_product_discoverability,
    fetch_audience_affinity,
    fetch_citations,
    fetch_citation_analysis,
    fetch_brand_projection,
    fetch_ai_score_banks,
)
from services.digital_brand_health.app.models.filters import BanksFilterResponse
from services.digital_brand_health.app.models.ai_score import (
    AiScoreResponse,
    OverallDiscoverabilityResponse,
    AudienceAffinityResponse,
    CitationsWithKpiResponse,
    CitationAnalysisResponse,
    BrandProjectionResponse,
)
from services.digital_brand_health.app.api.deps import get_current_user
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
        return OverallDiscoverabilityResponse(data)
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


@router.get("/citations", response_model=CitationsWithKpiResponse)
async def get_citations(
    llm: str | None = Query(
        default=None,
        alias="assistant",
        description="Filter to ChatGPT, Gemini, Claude, or Grok. Omit for all "
        "assistants. kpi.total_citations/unique_urls scope to this filter; "
        "kpi's cross-assistant fields (assistant_count, cited_by_all_assistants, "
        "max_overlap, overlap_distribution) always cover all citations, since "
        "cross-model agreement is only meaningful across the full dataset.",
    ),
    bank: str | None = Query(
        default=None,
        description="Filter to a single bank (e.g. 'Al Rajhi Bank'). Omit for all "
        "banks. Scopes the citations and every kpi field, including the "
        "cross-assistant overlap.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        data = await fetch_citations(llm, bank)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citation-analysis", response_model=CitationAnalysisResponse)
async def get_citation_analysis(
    llm: str | None = Query(
        default=None,
        alias="assistant",
        description="Filter to ChatGPT, Gemini, Claude, or Grok. Omit for all assistants.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return await fetch_citation_analysis(llm)
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
