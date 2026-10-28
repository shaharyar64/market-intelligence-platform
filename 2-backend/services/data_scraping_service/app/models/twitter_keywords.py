from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

class TwitterKeywordScrapeRequest(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date = Field(description="Inclusive")
    query_type: Literal["Latest", "Top"] = "Latest"
    lang: str | None = Field(default=None, max_length=10)
    location_query: str | None = Field(default=None, max_length=500)
    filter_by_country: bool = False
    country_filter_terms: list[str] | None = Field(
        default=None,
        description="Optional country, city, state, or demonym terms for country filtering",
    )
    exclude_retweets: bool = True
    exclude_replies: bool = False
    window_days: int = Field(default=31, ge=1, le=366)
    max_pages_per_window: int | None = Field(default=None, ge=1, le=1000)
    project: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=3)
    industry: str | None = Field(default=None, max_length=100)
    save_to_database: bool = True

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("keywords cannot contain blank values")
        return list(dict.fromkeys(cleaned))

    @field_validator("country")
    @classmethod
    def normalize_country(cls, country: str | None) -> str | None:
        return country.upper() if country else None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.filter_by_country and not self.country:
            raise ValueError("country is required when filter_by_country is enabled")
        return self


class TwitterKeywordPost(BaseModel):
    id: str
    keyword: str
    search_query: str
    username: str | None = None
    author_name: str | None = None
    author_id: str | None = None
    author_location: str | None = None
    country_match_source: str | None = None
    text: str | None = None
    url: str | None = None
    uploaded_at: datetime | None = None
    views: int = 0
    replies: int = 0
    retweet: int = 0
    likes: int = 0
    quotes: int = 0
    bookmarks: int = 0
    lang: str | None = None
    is_reply: bool | None = None
    conversation_id: str | None = None
    hashtags: str = "[]"
    mentions: str = "[]"
    expanded_urls: str = "[]"
    window_start: date
    window_end: date
    last_updated: datetime
    project: str | None = None
    country: str | None = None
    industry: str | None = None


class TwitterKeywordScrapeResponse(BaseModel):
    requested_keywords: int
    scraped_posts: int
    saved_to_database: bool
    posts: list[TwitterKeywordPost]


class TwitterKeywordJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class TwitterKeywordJobError(BaseModel):
    keyword: str
    message: str


class TwitterKeywordJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_keyword: str | None = None
    scraped_posts: int
    saved_to_database: bool
    posts: list[TwitterKeywordPost] = Field(default_factory=list)
    errors: list[TwitterKeywordJobError] = Field(default_factory=list)
