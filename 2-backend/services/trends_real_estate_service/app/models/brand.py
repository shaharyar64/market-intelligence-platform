
from pydantic import BaseModel


class BrandSummary(BaseModel):
    key: str
    name: str
    account_type: str = "brand"
    post_count: int
    platforms: list[str]


class BrandListResponse(BaseModel):
    brands: list[BrandSummary]


class PlatformAccount(BaseModel):
    platform: str
    account_username: str | None = None
    followers: int = 0
    is_verified: bool = False


class BrandOverview(BaseModel):
    key: str
    name: str
    account_type: str = "brand"
    platforms: list[str]
    accounts: list[PlatformAccount]
    followers_total: int
    post_count: int
    total_engagement: int
    avg_engagement_per_post: float
    first_post_date: str | None = None
    last_post_date: str | None = None
    theme_count: int
    offering_count: int
    visual_territories: list[str] = []


class ThemeAgg(BaseModel):
    label: str
    post_count: int
    engagement: int
    avg_confidence: float
    evidence: list[str]
    example_post_ids: list[str]


class ThemesResponse(BaseModel):
    brand_key: str
    min_posts: int
    themes: list[ThemeAgg]


class OfferingAgg(BaseModel):
    offering: str
    offering_native: str | None = None
    post_count: int
    engagement: int
    avg_confidence: float
    evidence: list[str]
    example_post_ids: list[str]


class OfferingsResponse(BaseModel):
    brand_key: str
    min_posts: int
    offerings: list[OfferingAgg]


class Owner(BaseModel):
    username: str | None = None
    name: str | None = None


class TopContentItem(BaseModel):
    post_id: str
    platform: str
    post_url: str | None = None
    owner: Owner | None = None
    posted_at: str | None = None
    text: str
    engagement: dict[str, int]
    themes: list[str]
    offerings: list[str]


class TopContentResponse(BaseModel):
    brand_key: str
    items: list[TopContentItem]


class FunctionalVisualCategory(BaseModel):
    category: str
    post_count: int
    pct: float


class FunctionalVisualResponse(BaseModel):
    brand_key: str
    categories: list[FunctionalVisualCategory]


class SemioticResponse(BaseModel):
    brand_key: str
    axes: dict[str, float]
