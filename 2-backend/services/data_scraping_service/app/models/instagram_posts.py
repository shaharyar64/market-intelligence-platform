from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from services.data_scraping_service.app.models.instagram import (
    InstagramProfileJobError,
    InstagramProfileScrapeRequest,
)


class InstagramPostScrapeRequest(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date
    max_items_per_username: int = Field(default=10000, ge=1, le=1_000_000)
    save_to_database: bool = True
    upload_images_to_s3: bool = True

    @field_validator("usernames")
    @classmethod
    def clean_usernames(cls, usernames: list[str]) -> list[str]:
        return InstagramProfileScrapeRequest.clean_usernames(usernames)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class InstagramPost(BaseModel):
    id: str
    username: str | None = None
    uploaded_at: datetime
    caption: str = ""
    views: int = 0
    comments: int = 0
    likes: int = 0
    last_updated: datetime
    thumbnail_url: str | None = None
    s3_key: str | None = None
    image_upload_status: Literal["disabled", "uploaded", "skipped", "failed"] = "disabled"


class InstagramPostScrapeResponse(BaseModel):
    requested_usernames: int
    scraped_posts: int
    saved_to_database: bool
    upload_images_to_s3: bool
    images_uploaded: int
    images_skipped: int
    images_failed: int
    posts: list[InstagramPost]


class InstagramPostJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class InstagramPostJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    total: int
    completed: int
    successful: int
    failed: int
    progress_percent: float
    current_username: str | None = None
    scraped_posts: int
    saved_to_database: bool
    upload_images_to_s3: bool
    images_uploaded: int
    images_skipped: int
    images_failed: int
    posts: list[InstagramPost] = Field(default_factory=list)
    errors: list[InstagramProfileJobError] = Field(default_factory=list)
