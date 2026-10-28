from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LinkedInProfileScrapeRequest(BaseModel):
    profile_urls: list[str] = Field(min_length=1, max_length=50)
    country: str | None = Field(default=None, max_length=3)
    project: str | None = Field(default=None, max_length=100)
    save_to_database: bool = True

    @field_validator("profile_urls")
    @classmethod
    def clean_urls(cls, values: list[str]) -> list[str]:
        urls = [value.strip() for value in values]
        if any(not url or "linkedin.com/company/" not in url for url in urls):
            raise ValueError("Every profile URL must be a LinkedIn company URL")
        return list(dict.fromkeys(urls))

    @field_validator("country")
    @classmethod
    def normalize_country(cls, country: str | None) -> str | None:
        return country.upper() if country else None


class LinkedInProfile(BaseModel):
    url: str | None = None
    company_name: str | None = None
    website_url: str | None = None
    industry: str | None = None
    employee_count: int = 0
    follower_count: int = 0
    universal_name: str | None = None
    tagline: str | None = None
    hashtag: str | None = None
    country: str | None = None
    city: str | None = None
    postal_code: str | None = None
    founded_on: int | None = None
    description: str | None = None
    project: str | None = None
    last_updated: datetime


class LinkedInProfileScrapeResponse(BaseModel):
    requested: int
    scraped: int
    saved_to_database: bool
    profiles: list[LinkedInProfile]


class LinkedInProfileJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class LinkedInProfileJobError(BaseModel):
    profile_url: str
    message: str


class LinkedInProfileJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_profile_url: str | None = None
    saved_to_database: bool
    profiles: list[LinkedInProfile] = Field(default_factory=list)
    errors: list[LinkedInProfileJobError] = Field(default_factory=list)
