from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

class TikTokProfileScrapeRequest(BaseModel):
    profiles: list[str] = Field(
        min_length=1,
        max_length=50,
        description="TikTok usernames, @usernames, or profile/video/photo URLs",
    )
    max_items: int = Field(default=1000, ge=1, le=10000)
    get_followers: bool = True
    get_following: bool = True
    country: str | None = Field(default=None, max_length=3)
    industry: str | None = Field(default=None, max_length=100)
    project: str | None = Field(default=None, max_length=100)
    save_to_database: bool = True

    @field_validator("profiles")
    @classmethod
    def normalize_profiles(cls, values: list[str]) -> list[str]:
        urls: list[str] = []
        for value in values:
            value = value.strip()
            if not value:
                raise ValueError("profiles cannot contain blank values")
            if "://" in value:
                parsed = urlparse(value)
                parts = [part for part in parsed.path.split("/") if part]
                username = next((part[1:] for part in parts if part.startswith("@")), None)
                if not username:
                    raise ValueError(f"TikTok username is missing from URL: {value}")
            else:
                username = value.lstrip("@")
            urls.append(f"https://www.tiktok.com/@{username}")
        return list(dict.fromkeys(urls))

    @field_validator("country")
    @classmethod
    def normalize_country(cls, country: str | None) -> str | None:
        return country.upper() if country else None

    @model_validator(mode="after")
    def validate_database_metadata(self):
        if self.save_to_database:
            missing = [
                field
                for field in ("country", "industry", "project")
                if not getattr(self, field)
            ]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} required when save_to_database is true"
                )
        return self


class TikTokProfile(BaseModel):
    id: str | None = None
    url: str | None = None
    username: str | None = None
    nickname: str | None = None
    bio: str | None = None
    bio_url: str | None = None
    followers: int = 0
    following: int = 0
    likes: int = 0
    videos: int = 0
    is_verified: bool = False
    profile_category: str | None = None
    avatar: str | None = None
    country: str | None = None
    industry: str | None = None
    project: str | None = None
    last_updated: datetime


class TikTokProfileScrapeResponse(BaseModel):
    requested: int
    scraped: int
    saved_to_database: bool
    profiles: list[TikTokProfile]


class TikTokProfileJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class TikTokProfileJobError(BaseModel):
    profile: str
    message: str


class TikTokProfileJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_profile: str | None = None
    saved_to_database: bool
    profiles: list[TikTokProfile] = Field(default_factory=list)
    errors: list[TikTokProfileJobError] = Field(default_factory=list)
