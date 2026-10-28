from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from services.data_scraping_service.app.models.instagram import InstagramProfileJobError


class TwitterProfileScrapeRequest(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=50)
    country: str | None = Field(default=None, max_length=3)
    industry: str | None = Field(default=None, max_length=100)
    project: str | None = Field(default=None, max_length=100)
    save_to_database: bool = True

    @field_validator("usernames")
    @classmethod
    def clean_usernames(cls, values: list[str]) -> list[str]:
        usernames: list[str] = []
        for value in values:
            value = value.strip()
            if "://" in value:
                value = urlparse(value).path.rstrip("/").split("/")[-1]
            value = value.lstrip("@")
            if not value:
                raise ValueError("usernames cannot contain blank values")
            usernames.append(value)
        return list(dict.fromkeys(usernames))

    @field_validator("country")
    @classmethod
    def normalize_country(cls, country: str | None) -> str | None:
        return country.upper() if country else None


class TwitterProfile(BaseModel):
    id: str | None = None
    username: str | None = None
    full_name: str | None = None
    bio: str | None = None
    followers: int = 0
    following: int = 0
    posts: int = 0
    is_verified: bool = False
    is_blue_verified: bool = False
    verified_type: str | None = None
    created_at: datetime | None = None
    last_updated: datetime
    country: str | None = None
    industry: str | None = None
    project: str | None = None


class TwitterProfileScrapeResponse(BaseModel):
    requested: int
    scraped: int
    saved_to_database: bool
    profiles: list[TwitterProfile]


class TwitterProfileJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class TwitterProfileJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_username: str | None = None
    saved_to_database: bool
    profiles: list[TwitterProfile] = Field(default_factory=list)
    errors: list[InstagramProfileJobError] = Field(default_factory=list)
