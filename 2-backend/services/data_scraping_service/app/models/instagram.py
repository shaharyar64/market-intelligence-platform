from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class InstagramProfileScrapeRequest(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=50)
    include_about_section: bool = False
    country: str | None = Field(default=None, max_length=3)
    industry: str | None = Field(default=None, max_length=100)
    project: str | None = Field(default=None, max_length=100)
    save_to_database: bool = True

    @field_validator("usernames")
    @classmethod
    def clean_usernames(cls, usernames: list[str]) -> list[str]:
        cleaned = [username.strip().lstrip("@") for username in usernames]
        if any(not username for username in cleaned):
            raise ValueError("usernames cannot contain blank values")
        # Keep UI order while avoiding duplicate actor work.
        return list(dict.fromkeys(cleaned))

    @field_validator("country")
    @classmethod
    def normalize_country(cls, country: str | None) -> str | None:
        return country.upper() if country else None


class InstagramProfile(BaseModel):
    id: str | None = None
    username: str | None = None
    full_name: str | None = None
    followers: int = 0
    following: int = 0
    posts: int = 0
    category: str | None = None
    is_verified: bool = False
    bio: str | None = None
    external_url: str | None = None
    last_updated: datetime
    country: str | None = None
    industry: str | None = None
    project: str | None = None


class InstagramProfileScrapeResponse(BaseModel):
    requested: int
    scraped: int
    saved_to_database: bool
    profiles: list[InstagramProfile]


class InstagramProfileJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class InstagramProfileJobError(BaseModel):
    username: str
    message: str


class InstagramProfileJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_username: str | None = None
    save_to_database: bool
    profiles: list[InstagramProfile] = Field(default_factory=list)
    errors: list[InstagramProfileJobError] = Field(default_factory=list)
