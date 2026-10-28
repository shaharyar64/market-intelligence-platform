from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LinkedInPostScrapeRequest(BaseModel):
    target_urls: list[str] = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date = Field(description="Inclusive")
    max_posts: int = Field(default=100_000, ge=1, le=100_000)
    save_to_database: bool = True

    @field_validator("target_urls")
    @classmethod
    def clean_urls(cls, values: list[str]) -> list[str]:
        urls = [value.strip() for value in values]
        if any(not url or "linkedin.com/company/" not in url for url in urls):
            raise ValueError("Every target URL must be a LinkedIn company URL")
        return list(dict.fromkeys(urls))

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LinkedInPost(BaseModel):
    post_text: str
    post_url: str
    likes: int = 0
    shares: int = 0
    comments: int = 0
    uploaded_at: datetime
    universal_name: str | None = None
    source_company: str | None = None
    last_updated: datetime


class LinkedInPostScrapeResponse(BaseModel):
    requested_companies: int
    scraped_posts: int
    saved_to_database: bool
    posts: list[LinkedInPost]


class LinkedInPostJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class LinkedInPostJobError(BaseModel):
    target_url: str
    message: str


class LinkedInPostJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_target_url: str | None = None
    scraped_posts: int
    saved_to_database: bool
    posts: list[LinkedInPost] = Field(default_factory=list)
    errors: list[LinkedInPostJobError] = Field(default_factory=list)
