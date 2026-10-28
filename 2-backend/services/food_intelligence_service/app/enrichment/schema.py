"""Structured output schemas for the analysis graph nodes."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ThemeItem(BaseModel):
    label: str = Field(description="Short English label for a communication theme, e.g. 'Ramadan recipes', 'High protein'.")
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 confidence this theme is genuinely present in the caption.")
    evidence: list[str] = Field(default_factory=list, description="Verbatim phrase(s) copied from the caption that justify this theme.")


ProductKind = Literal["product", "ingredient", "dish", "brand", "hashtag"]


class ProductItem(BaseModel):
    product: str = Field(description="A specific product or product category discussed, in short lowercase singular English even when the caption is Arabic, e.g. 'laban', 'pancake', 'cream cheese'. Not a brand name or a hashtag.")
    product_ar: str = Field(default="", description="The same product's common Gulf Arabic name, singular, without the definite article, e.g. 'لبن', 'حليب', 'جبنة كريمية'.")
    kind: ProductKind = Field(default="product", description="product: a packaged or retail food item; ingredient: used to cook with; dish: a prepared meal or recipe; brand or hashtag only if one slipped in.")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, description="Verbatim phrase(s) from the caption mentioning the product.")


class DescriptionOutput(BaseModel):
    description: str = Field(description="1-2 sentence neutral summary of what the caption communicates. No invented facts.")
    language: str = Field(description="Dominant caption language as ISO 639-1 code, e.g. 'ar', 'en'. Use 'mixed' if genuinely both.")


class KeywordsOutput(BaseModel):
    keywords: list[str] = Field(default_factory=list, description="Salient keywords/hashtags actually present in the caption.")


class SemioticTextOutput(BaseModel):
    semiotic_text: str = Field(default="", description="Brief reading of tone/cultural cues/signals conveyed by the wording. Empty if not determinable.")


class ThemesOutput(BaseModel):
    themes: list[ThemeItem] = Field(default_factory=list)


class ProductFocusOutput(BaseModel):
    product_focus: list[ProductItem] = Field(default_factory=list)


FunctionalCategory = Literal["product", "ingredient", "prepared_food", "family", "individual", "in_home", "out_of_home"]


class FunctionalVisualItem(BaseModel):
    category: FunctionalCategory
    confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence: str = Field(description="What is actually observed in the image that supports this category.")


class FunctionalVisualOutput(BaseModel):
    functional_visual: list[FunctionalVisualItem] = Field(default_factory=list)


SemioticAxis = Literal["premium", "healthy", "natural", "modern", "traditional", "sophisticated", "indulgent"]


_AXIS_HINT = "0-1 score for how strongly the image visually conveys this. Null when the image gives no real signal."


class SemioticVisualOutput(BaseModel):
    premium: Optional[float] = Field(description=_AXIS_HINT)
    healthy: Optional[float] = Field(description=_AXIS_HINT)
    natural: Optional[float] = Field(description=_AXIS_HINT)
    modern: Optional[float] = Field(description=_AXIS_HINT)
    traditional: Optional[float] = Field(description=_AXIS_HINT)
    sophisticated: Optional[float] = Field(description=_AXIS_HINT)
    indulgent: Optional[float] = Field(description=_AXIS_HINT)

    @property
    def scores(self) -> dict[str, float]:
        pairs = (
            ("premium", self.premium), ("healthy", self.healthy), ("natural", self.natural),
            ("modern", self.modern), ("traditional", self.traditional),
            ("sophisticated", self.sophisticated), ("indulgent", self.indulgent),
        )
        return {axis: max(0.0, min(1.0, v)) for axis, v in pairs if v is not None}
