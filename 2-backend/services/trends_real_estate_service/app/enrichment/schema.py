"""Structured output schemas for the analysis graph nodes."""
from typing import Literal

from pydantic import BaseModel, Field


class ThemeItem(BaseModel):
    label: str = Field(description="The property theme in Sentence case, 1-3 English words, reused identically across posts so themes can be counted, e.g. 'Waterfront living', 'Payment plan', 'Rooftop pool', 'Smart home'. Not a developer, project, campaign or marketing activity.")
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 confidence this theme is genuinely present in the caption.")
    evidence: list[str] = Field(default_factory=list, description="Verbatim phrase(s) copied from the caption that justify this theme.")


class OfferingItem(BaseModel):
    offering: str = Field(description="A specific development, property type or amenity being talked about, in short lowercase English even when the caption is Arabic, e.g. 'branded residences', 'townhouse', 'rooftop pool', 'creek harbour'. A named project counts. Not a developer name and not a hashtag.")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, description="Verbatim phrase(s) from the caption mentioning the offering.")


class DescriptionOutput(BaseModel):
    description: str = Field(description="1-2 sentence neutral summary of what the caption communicates. No invented facts.")
    language: str = Field(description="Dominant caption language as ISO 639-1 code, e.g. 'ar', 'en'. Use 'mixed' if genuinely both.")


class KeywordsOutput(BaseModel):
    keywords: list[str] = Field(default_factory=list, description="Salient keywords/hashtags actually present in the caption.")


class SemioticTextOutput(BaseModel):
    semiotic_text: str = Field(default="", description="Brief reading of tone/cultural cues/signals conveyed by the wording. Empty if not determinable.")


class ThemesOutput(BaseModel):
    themes: list[ThemeItem] = Field(default_factory=list)


class OfferingFocusOutput(BaseModel):
    offering_focus: list[OfferingItem] = Field(default_factory=list)


# What the image physically SHOWS. Deliberately about subject rather than
# style - style is scored separately on the semiotic axes below, and mixing the
# two produces a category a labeller cannot decide from one image. Every value
# here is answerable by looking, without inferring the poster's intent.
FunctionalCategory = Literal[
    "unit_interior",    # rooms, finishes, fit-out, furniture
    "exterior_facade",  # the building itself, elevation, entrance
    "masterplan",       # aerial, site plan, district-scale render
    "amenity",          # pool, gym, park, clubhouse, retail
    "view",             # what you see from it: sea, skyline, golf, marina
    "lifestyle_scene",  # people using the place, not the place alone
    "floorplan",        # layouts, dimensions, unit mix, spec sheets
]


class FunctionalVisualItem(BaseModel):
    category: FunctionalCategory
    confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence: str = Field(description="What is actually observed in the image that supports this category.")


class FunctionalVisualOutput(BaseModel):
    functional_visual: list[FunctionalVisualItem] = Field(default_factory=list)


# The mood the imagery projects. Derived from the style labels already applied
# to 8,883 of this market's own images in realestate.image_classification_*,
# trimmed to the seven that carried real volume there - so these are axes the
# corpus has demonstrably expressed, not invented ones.
SemioticAxis = Literal[
    "premium",       # Luxurious / Premium
    "minimalist",    # Minimalist / Monochrome
    "natural",       # Nature-Inspired / Earthy
    "urban",         # Urban / Industrial
    "homely",        # Warm & Homely
    "bold",          # Bold & Edgy
    "aspirational",  # Aspirational Lifestyle
]


_AXIS_HINT = "0-1 score for how strongly the image visually conveys this. Null when the image gives no real signal."


class SemioticVisualOutput(BaseModel):
    premium: float | None = Field(description=_AXIS_HINT)
    minimalist: float | None = Field(description=_AXIS_HINT)
    natural: float | None = Field(description=_AXIS_HINT)
    urban: float | None = Field(description=_AXIS_HINT)
    homely: float | None = Field(description=_AXIS_HINT)
    bold: float | None = Field(description=_AXIS_HINT)
    aspirational: float | None = Field(description=_AXIS_HINT)

    @property
    def scores(self) -> dict[str, float]:
        pairs = (
            ("premium", self.premium), ("minimalist", self.minimalist),
            ("natural", self.natural), ("urban", self.urban),
            ("homely", self.homely), ("bold", self.bold),
            ("aspirational", self.aspirational),
        )
        return {axis: max(0.0, min(1.0, v)) for axis, v in pairs if v is not None}
