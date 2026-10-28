from fastapi import APIRouter, HTTPException, Depends, Query
from services.bank_brand_health.app.services.digital_banking_experience import (
    fetch_digital_banking_experience,
)
from services.bank_brand_health.app.models.ai_score import AiScoreResponse
from services.bank_brand_health.app.api.deps import get_current_user
from typing import Dict, Any

router = APIRouter(
    prefix="/digital-banking-experience", tags=["Digital Banking Experience"]
)


@router.get("", response_model=AiScoreResponse)
@router.get("/", response_model=AiScoreResponse, include_in_schema=False)
async def get_digital_banking_experience(
    llm: str | None = Query(
        default="Overall", description="Overall, ChatGPT, Gemini, Claude, or Grok"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return await fetch_digital_banking_experience(llm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
