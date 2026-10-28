from pydantic import BaseModel
from typing import List, Optional, Dict


class BrandSummary(BaseModel):
    key: str
    name: str
    account_type: str = "brand"
    post_count: int
    platforms: List[str]


class BrandListResponse(BaseModel):
    brands: List[BrandSummary]


class PlatformAccount(BaseModel):
    platform: str
    account_username: Optional[str] = None
    followers: int = 0
    is_verified: bool = False


class BrandOverview(BaseModel):
    key: str
    name: str
    account_type: str = "brand"
    platforms: List[str]
    accounts: List[PlatformAccount]
    followers_total: int
    post_count: int
    total_engagement: int
    avg_engagement_per_post: float
    first_post_date: Optional[str] = None
    last_post_date: Optional[str] = None
    theme_count: int
    product_count: int
    visual_territories: List[str] = []


class ThemeAgg(BaseModel):
    label: str
    post_count: int
    engagement: int
    avg_confidence: float
    evidence: List[str]
    example_post_ids: List[str]


class ThemesResponse(BaseModel):
    brand_key: str
    min_posts: int
    themes: List[ThemeAgg]


class ProductAgg(BaseModel):
    product: str
    product_native: Optional[str] = None
    post_count: int
    engagement: int
    avg_confidence: float
    evidence: List[str]
    example_post_ids: List[str]


class ProductsResponse(BaseModel):
    brand_key: str
    min_posts: int
    products: List[ProductAgg]


class Owner(BaseModel):
    username: Optional[str] = None
    name: Optional[str] = None


class TopContentItem(BaseModel):
    post_id: str
    platform: str
    post_url: Optional[str] = None
    owner: Optional[Owner] = None
    posted_at: Optional[str] = None
    text: str
    engagement: Dict[str, int]
    themes: List[str]
    products: List[str]


class TopContentResponse(BaseModel):
    brand_key: str
    items: List[TopContentItem]


class FunctionalVisualCategory(BaseModel):
    category: str
    post_count: int
    pct: float


class FunctionalVisualResponse(BaseModel):
    brand_key: str
    categories: List[FunctionalVisualCategory]


class SemioticResponse(BaseModel):
    brand_key: str
    axes: Dict[str, float]
