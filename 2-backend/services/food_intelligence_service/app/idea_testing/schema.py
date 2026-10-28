"""Pydantic models for the Idea Testing LLM calls and API payloads."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

FRAMEWORK_VERSION = "idea-testing-v4"

FACTOR_IDS: tuple[str, ...] = (
    "clutter", "connect", "clarity", "competitive", "credibility", "conversion",
)
FactorId = Literal["clutter", "connect", "clarity", "competitive", "credibility", "conversion"]
TestType = Literal["quick-idea", "advertising", "innovation"]
InputFormat = Literal["text", "image", "pdf"]
FoodRelation = Literal["food", "food_adjacent", "not_food"]
InputKind = Literal["concept", "question", "other_text"]
RelatedDashboard = Literal["food", "real_estate", "none"]
CLASSIFICATION_FIELDS = ("subject", "food_relation", "input_kind", "related_dashboard",
                         "classification_reason")

FACTOR_CRITERIA: dict[str, tuple[tuple[str, str], ...]] = {
    "clutter": (
        ("novel_message", "The core message differs from what the retrieved brand and influencer posts already say."),
        ("avoids_generic_claims", "It avoids generic category claims such as healthy, natural, delicious or premium."),
        ("distinctive_hook", "It has a distinctive hook, format or angle a consumer would remember."),
        ("stands_out_in_feed", "It would stand out in a feed full of this category's content."),
    ),
    "connect": (
        ("real_tension", "It addresses a real need or tension that is visible in the community evidence."),
        ("emotional_payoff", "It offers a clear emotional or personal payoff, not only a functional one."),
        ("defined_audience", "The target audience is specific and clearly defined."),
        ("fits_audience_language", "It fits how the audience actually talks and behaves in the evidence."),
    ),
    "clarity": (
        ("single_message", "It carries one main message, not several competing ones."),
        ("instant_understanding", "A consumer would understand it within a few seconds."),
        ("plain_language", "It is free of jargon and vague or ambiguous terms."),
        ("explicit_benefit", "The benefit is stated explicitly rather than left to be inferred."),
    ),
    "competitive": (
        ("point_of_difference", "It has a clear point of difference from what the retrieved brand evidence shows."),
        ("not_already_claimed", "The difference is not already claimed by the brands or trends in the evidence."),
        ("hard_to_copy", "The difference would be hard for a competitor to copy quickly."),
        ("difference_matters", "The difference is something consumers in the evidence actually care about."),
    ),
    "credibility": (
        ("mechanism", "It explains how the benefit is delivered: ingredient, process, sourcing or mechanism."),
        ("specific_claims", "Its claims are specific or quantified rather than vague."),
        ("evidence_consistent", "The evidence supports its claims rather than contradicting or ignoring them."),
        ("believable_offer", "The offer is believable for the category, format and implied price."),
    ),
    "conversion": (
        ("reason_to_try_now", "It gives a clear reason to try it now."),
        ("low_friction", "Trying it is low friction: price, availability, format and occasion."),
        ("demand_signals", "The evidence shows demand, purchase intent or switching language for this."),
        ("beats_current_option", "It gives a reason to switch away from what the audience uses today."),
    ),
}


class ConceptExtraction(BaseModel):
    """Step A of the brief's flow: what the concept is actually saying,
    extracted once and reused for every downstream retrieval and scoring
    call so results are stable even if the user's raw phrasing is noisy."""
    need: str = Field(description="The core consumer need or problem this concept addresses.")
    proposition: str = Field(description="The central proposition or benefit being offered.")
    claims: list[str] = Field(default_factory=list,
                              description="Specific claims or reasons-to-believe stated in the concept.")
    category: str = Field(description="The food category/segment this concept belongs to, "
                                      "e.g. 'plant-based dairy', 'high-protein snacking'.")
    audience: str = Field(description="The target audience described or implied.")
    cues: list[str] = Field(default_factory=list,
                            description="Important execution or visual cues mentioned.")
    specifics: list[str] = Field(default_factory=list,
                                 description="Concrete product details named in the concept: "
                                             "flavours or ingredients, brand, market or country, "
                                             "pack sizes and formats, channels, price points.")
    subject: str = Field(description="What the input is actually about, in a few plain words, "
                                     "e.g. 'high-protein yogurt', 'renewable energy', "
                                     "'off-plan villas'.")
    food_relation: FoodRelation = Field(
        description="food: the subject is a food or beverage product, brand, range or campaign. "
                    "food_adjacent: not food or drink itself, but its core purpose is eating or "
                    "drinking, such as a restaurant, food delivery, kitchen appliance or food "
                    "packaging. not_food: anything else, even if it mentions food in passing.")
    input_kind: InputKind = Field(
        description="concept: a product, service or campaign idea that can be tested. question: "
                    "the input asks something rather than proposing an idea. other_text: a "
                    "greeting, test message, random text, or an image with no idea on it.")
    related_dashboard: RelatedDashboard = Field(
        description="The dashboard whose market this subject belongs to: food, real_estate, "
                    "or none.")
    classification_reason: str = Field(
        description="One short sentence explaining food_relation and input_kind.")


class Citation(BaseModel):
    evidence_type: Literal["post", "trend", "document"]
    platform: str | None = None
    post_id: str | None = None
    trend_id: str | None = None
    document_id: str | None = None
    quote: str = Field(description="A short verbatim excerpt or tightly paraphrased finding.")


class CriterionScore(BaseModel):
    criterion_id: str
    label: str
    rating: int = Field(ge=0, le=3)


class FactorScore(BaseModel):
    factor_id: FactorId
    score: int = Field(ge=0, le=100)
    verdict: str = Field(description="A 2-4 word verdict, e.g. 'Genuinely distinctive'.")
    finding: str = Field(description="1-2 sentences explaining the score, grounded in evidence.")
    citations: list[Citation] = Field(default_factory=list, max_length=3)
    criteria: list[CriterionScore] = Field(default_factory=list)


class CriterionRating(BaseModel):
    criterion_id: str = Field(description="One of the criterion ids listed for this factor.")
    rating: int = Field(ge=0, le=3, description="0 absent or contradicted, 1 weak, 2 solid, "
                                                 "3 outstanding and backed by evidence.")


class RatedFactor(BaseModel):
    factor_id: FactorId
    citations: list[Citation] = Field(
        default_factory=list, max_length=3,
        description="1-3 items from this factor's evidence that the finding will rest on. "
                    "Empty only when this factor's evidence is empty.")
    finding: str = Field(description="1-2 sentences of reasoning that state what the cited "
                                     "items show, written before rating the criteria.")
    ratings: list[CriterionRating] = Field(
        description="One rating for every criterion listed for this factor.")
    verdict: str = Field(description="A 2-4 word verdict, e.g. 'Genuinely distinctive'.")


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


class RatedScoringResult(BaseModel):
    headline: str = Field(description="A short overall verdict headline.")
    summary: str = Field(description="2-4 sentence overall summary of the concept.")
    factors: list[RatedFactor] = Field(min_length=6, max_length=6)
    recommendations: list[str] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def _every_factor_rates_its_own_criteria(self) -> "RatedScoringResult":
        ids = {f.factor_id for f in self.factors}
        if ids != set(FACTOR_IDS):
            raise ValueError(
                f"factors must contain exactly the six 6C factor ids {set(FACTOR_IDS)}, got {ids}")
        for f in self.factors:
            expected = {cid for cid, _ in FACTOR_CRITERIA[f.factor_id]}
            got = [r.criterion_id for r in f.ratings]
            if set(got) != expected or len(got) != len(expected):
                raise ValueError(f"{f.factor_id} must rate exactly {sorted(expected)}, got {got}")
        return self
