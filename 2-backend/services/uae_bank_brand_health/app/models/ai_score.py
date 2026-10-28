from pydantic import BaseModel, Field, RootModel
from typing import Dict, List


class AiScoreItem(BaseModel):
    bank: str
    llm: str
    score: float


class AiScoreResponse(RootModel[Dict[str, List[AiScoreItem]]]):
    pass


class OverallDiscoverabilityResponse(RootModel[List[AiScoreItem]]):
    pass


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
    category: str


class CitationsResponse(RootModel[List[CitationItem]]):
    pass


class CitationKpi(BaseModel):
    total_citations: int
    assistant_count: int
    assistants: List[str]
    unique_urls: int
    cited_by_all_assistants: int
    max_overlap: int
    overlap_distribution: Dict[str, int]


class CitationsWithKpiResponse(BaseModel):
    citations: List[CitationItem]
    kpi: CitationKpi


class CitationAnalysisKpi(BaseModel):
    total_citations: int
    bank_citations: int = Field(description="Citations attributable to a single bank (excludes 'All Banks').")
    market_level_citations: int = Field(description="Citations tagged 'All Banks' (market-wide prompts).")
    unique_domains: int
    unique_urls: int
    cited_by_all_assistants: int = Field(description="URLs cited by every assistant; always over the unfiltered set.")


class BankCitationCount(BaseModel):
    bank: str
    citations: int
    unique_urls: int
    unique_domains: int
    share_pct: float = Field(description="Share (%) of all bank-attributed citations.")


class BankAssistantCount(BaseModel):
    bank: str
    llm: str
    citations: int


class BankSectionCount(BaseModel):
    bank: str
    analysis_section: str
    citations: int


class TopDomain(BaseModel):
    domain: str
    citations: int
    banks: int = Field(description="Number of distinct banks this domain was cited for.")
    assistants: List[str]
    sections: List[str]


class DomainBankCount(BaseModel):
    bank: str
    domain: str
    citations: int


class BankSourceKind(BaseModel):
    bank: str
    kind: str = Field(description="own_site | third_party")
    citations: int


class CategoryCount(BaseModel):
    category: str
    citations: int
    share_pct: float = Field(description="Share (%) of all bank-attributed citations.")


class CategoryAssistantCount(BaseModel):
    category: str
    llm: str
    citations: int


class CategoryBankCount(BaseModel):
    bank: str
    category: str
    citations: int


class CategorySectionCount(BaseModel):
    category: str
    analysis_section: str
    citations: int


class EvidenceRecencyCount(BaseModel):
    bucket: str = Field(description="2026 | 2025 | 2023–2024 | 2020–2022 | Before 2020 | Undated")
    llm: str
    bank: str
    citations: int


class CitationAnalysisResponse(BaseModel):
    categories: List[str] = Field(
        description="All source categories, most-cited first, over the full unfiltered "
        "data. Stable across llm filters; use it for legends and colour assignment."
    )
    kpi: CitationAnalysisKpi
    by_bank: List[BankCitationCount]
    by_bank_assistant: List[BankAssistantCount]
    by_bank_section: List[BankSectionCount]
    top_domains: List[TopDomain]
    domain_by_bank: List[DomainBankCount]
    source_mix: List[BankSourceKind]
    by_category: List[CategoryCount]
    by_category_assistant: List[CategoryAssistantCount]
    by_category_bank: List[CategoryBankCount]
    evidence_recency: List[EvidenceRecencyCount] = Field(
        description="Citations per publication-year bucket, assistant and bank (market-level "
        "rows have bank 'All Banks'). Rows with no publication date are 'Undated'."
    )
    source_by_section: List[CategorySectionCount] = Field(
        description="Citations per source category and analysis section, over all rows "
        "including market-level (All Banks) ones, so Overall Discoverability is included."
    )


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
