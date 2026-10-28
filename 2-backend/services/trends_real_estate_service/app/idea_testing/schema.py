"""Pydantic models for the Idea Testing LLM calls and API payloads."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

FRAMEWORK_VERSION = "idea-testing-v2"

FACTOR_IDS: tuple[str, ...] = (
    "clutter", "connect", "clarity", "competitive", "credibility", "conversion",
)
FactorId = Literal["clutter", "connect", "clarity", "competitive", "credibility", "conversion"]
TestType = Literal["quick-idea", "advertising", "innovation"]
InputFormat = Literal["text", "image", "pdf"]


class ConceptExtraction(BaseModel):
    """Step A of the brief's flow: what the concept is actually saying,
    extracted once and reused for every downstream retrieval and scoring
    call so results are stable even if the user's raw phrasing is noisy."""
    need: str = Field(description="The core consumer need or problem this concept addresses.")
    proposition: str = Field(description="The central proposition or benefit being offered.")
    claims: list[str] = Field(default_factory=list,
                              description="Specific claims or reasons-to-believe stated in the concept.")
    category: str = Field(description="The real-estate category/segment this concept belongs to, "
                                      "e.g. 'branded residences', 'off-plan payment plans'.")
    audience: str = Field(description="The target audience described or implied.")
    cues: list[str] = Field(default_factory=list,
                            description="Important execution or visual cues mentioned.")


class Citation(BaseModel):
    evidence_type: Literal["post", "trend", "document"]
    platform: str | None = None
    post_id: str | None = None
    trend_id: str | None = None
    document_id: str | None = None
    quote: str = Field(description="A short verbatim excerpt or tightly paraphrased finding.")


class FactorScore(BaseModel):
    factor_id: FactorId
    score: int = Field(ge=0, le=100)
    verdict: str = Field(description="A 2-4 word verdict, e.g. 'Genuinely distinctive'.")
    finding: str = Field(description="1-2 sentences explaining the score, grounded in evidence.")
    citations: list[Citation] = Field(default_factory=list, max_length=3)


class ScoringResult(BaseModel):
    headline: str = Field(description="A short overall verdict headline.")
    summary: str = Field(description="2-4 sentence overall summary of the concept.")
    factors: list[FactorScore] = Field(min_length=6, max_length=6)
    recommendations: list[str] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def _factors_cover_every_6c_factor(self) -> "ScoringResult":
        ids = {f.factor_id for f in self.factors}
        if ids != set(FACTOR_IDS):
            raise ValueError(
                f"factors must contain exactly the six 6C factor ids {set(FACTOR_IDS)}, got {ids}")
        return self
