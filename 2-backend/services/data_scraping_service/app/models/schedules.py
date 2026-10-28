from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from pydantic import BaseModel, Field, model_validator

from services.data_scraping_service.app.models.instagram import InstagramProfileScrapeRequest


class InstagramScheduledPostsPayload(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=50)
    initial_start_date: date
    max_items_per_username: int = Field(default=10000, ge=1, le=1_000_000)
    upload_images_to_s3: bool = True

    @model_validator(mode="after")
    def clean_usernames(self):
        self.usernames = InstagramProfileScrapeRequest.clean_usernames(self.usernames)
        return self


class InstagramScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    resource_type: Literal["profiles", "posts"]
    cron_expression: str = Field(
        description="Five-field cron: minute hour day-of-month month day-of-week"
    )
    timezone: str = "UTC"
    request_payload: dict[str, Any]
    enabled: bool = True

    @model_validator(mode="after")
    def validate_schedule(self):
        if not croniter.is_valid(self.cron_expression):
            raise ValueError("cron_expression must be a valid five-field cron expression")
        if len(self.cron_expression.split()) != 5:
            raise ValueError("cron_expression must contain exactly five fields")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone is not a valid IANA timezone") from exc
        if self.resource_type == "profiles":
            payload = InstagramProfileScrapeRequest.model_validate(self.request_payload)
            self.request_payload = payload.model_copy(update={"save_to_database": True}).model_dump(mode="json")
        else:
            self.request_payload = InstagramScheduledPostsPayload.model_validate(
                self.request_payload
            ).model_dump(mode="json")
        return self


class InstagramScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    cron_expression: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    request_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.cron_expression is not None:
            if len(self.cron_expression.split()) != 5 or not croniter.is_valid(self.cron_expression):
                raise ValueError("cron_expression must be a valid five-field cron expression")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone is not a valid IANA timezone") from exc
        return self


class InstagramSchedule(BaseModel):
    id: str
    name: str
    platform: str
    resource_type: str
    cron_expression: str
    timezone: str
    request_payload: dict[str, Any]
    enabled: bool
    next_run_at: datetime | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ScheduleRunAccepted(BaseModel):
    schedule_id: str
    status: Literal["running"] = "running"
