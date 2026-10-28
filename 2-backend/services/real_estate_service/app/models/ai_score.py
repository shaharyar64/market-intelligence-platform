from pydantic import BaseModel, RootModel
from typing import Dict, List


class AiScoreItem(BaseModel):
    bank: str
    llm: str
    score: float
    location: str | None = None


class AiScoreResponse(RootModel[Dict[str, List[AiScoreItem]]]):
    pass


class OverallDiscoverabilityResponse(BaseModel):
    data: List[AiScoreItem]


class AudienceAffinityItem(BaseModel):
    customer_segment: str
    llm: str
    score: float
    rationale: str


class AudienceAffinityResponse(RootModel[Dict[str, List[AudienceAffinityItem]]]):
    pass


class CitationItem(BaseModel):
    location: str
    bank: str
    llm: str
    model: str
    analysis_section: str
    prompt: str
    title: str
    url: str


class CitationsResponse(BaseModel):
    data: List[CitationItem]


class BrandProjectionPoint(BaseModel):
    type: str
    text: str


class BrandProjectionDetail(BaseModel):
    llm: str
    personality: str
    points: List[BrandProjectionPoint]


class BrandProjectionItem(BaseModel):
    personality: str
    strengths: List[str]
    positioning_opportunities: List[str]
    projections: List[BrandProjectionDetail]


class BrandProjectionResponse(RootModel[Dict[str, BrandProjectionItem]]):
    pass
