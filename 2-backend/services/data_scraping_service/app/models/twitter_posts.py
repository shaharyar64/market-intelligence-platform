from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from services.data_scraping_service.app.models.instagram import InstagramProfileJobError
from services.data_scraping_service.app.models.twitter import TwitterProfileScrapeRequest


class TwitterPostScrapeRequest(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date = Field(description="Exclusive; tweets on this date are not included")
    save_to_database: bool = True

    @model_validator(mode="before")
    @classmethod
    def normalize_usernames(cls, data):
        if isinstance(data, dict) and "usernames" in data:
            data = dict(data)
            data["usernames"] = TwitterProfileScrapeRequest.clean_usernames(data["usernames"])
        return data

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class TwitterPost(BaseModel):
    id: str
    username: str
    text: str = ""
    uploaded_at: date
    views: int = 0
    replies: int = 0
    retweet: int = 0
    likes: int = 0
    last_updated: date


class TwitterPostScrapeResponse(BaseModel):
    requested_usernames: int
    scraped_posts: int
    saved_to_database: bool
    posts: list[TwitterPost]


class TwitterPostJobCreated(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    total: int
    progress_url: str


class TwitterPostJobStatus(BaseModel):
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
    posts: list[TwitterPost] = Field(default_factory=list)
    errors: list[InstagramProfileJobError] = Field(default_factory=list)
