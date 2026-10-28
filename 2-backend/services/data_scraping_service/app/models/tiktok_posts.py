from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TikTokPostScrapeRequest(BaseModel):
    start_urls: list[str] = Field(min_length=1, max_length=50)
    max_items: int = Field(default=1_000_000, ge=1, le=1_000_000)
    start_date: date | None = None
    end_date: date | None = Field(default=None, description="Inclusive")
    country: str | None = Field(default=None, max_length=3)
    industry: str | None = Field(default=None, max_length=100)
    project: str | None = Field(default=None, max_length=100)
    save_to_database: bool = True

    @field_validator("start_urls")
    @classmethod
    def clean_urls(cls, urls: list[str]) -> list[str]:
        cleaned = [url.strip() for url in urls]
        if any(not url or "tiktok.com/" not in url for url in cleaned):
            raise ValueError("Every start URL must be a valid TikTok URL")
        return list(dict.fromkeys(cleaned))

    @field_validator("country")
    @classmethod
    def normalize_country(cls, country: str | None) -> str | None:
        return country.upper() if country else None

    @model_validator(mode="after")
    def validate_dates(self):
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TikTokPost(BaseModel):
    id: str
    text: str | None = None
    text_language: str | None = None
    uploaded_at: datetime | None = None
    web_video_url: str | None = None
    location_created: str | None = None
    is_ad: bool = False
    author_id: str | None = None
    username: str | None = None
    nickname: str | None = None
    author_verified: bool = False
    author_followers: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    reposts: int = 0
    duration: int | None = None
    cover_url: str | None = None
    music_name: str | None = None
    hashtags: str = "[]"
    is_slideshow: bool = False
    is_pinned: bool = False
    is_sponsored: bool = False
    input_url: str | None = None
    country: str | None = None
    industry: str | None = None
    project: str | None = None
    last_updated: datetime


class TikTokPostScrapeResponse(BaseModel):
    requested_urls: int
    scraped_posts: int
    saved_to_database: bool
    posts: list[TikTokPost]


class TikTokPostJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class TikTokPostJobError(BaseModel):
    start_url: str
    message: str


class TikTokPostJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_url: str | None = None
    scraped_posts: int
    saved_to_database: bool
    posts: list[TikTokPost] = Field(default_factory=list)
    errors: list[TikTokPostJobError] = Field(default_factory=list)
