from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Food Intelligence service settings."""

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Food Intelligence API"

    AWS_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    FOOD_MEDIA_S3_BUCKET: str = "raw-data-bucket"
    FOOD_MEDIA_S3_PREFIX_TEMPLATE: str = "media/{platform}/"
    TRENDS_MEDIA_S3_BUCKET: str = "raw-data-bucket"
    TRENDS_MEDIA_KEY_PREFIX: str = "media/"

    COGNITO_USER_POOL_ID: str | None = None
    COGNITO_CLIENT_ID: str | None = None

    SECRET_NAME: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str = "5432"
    DB_NAME: str | None = None

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.0
    ASSISTANT_MODEL: str = "gpt-4o"
    IDEA_SCORING_MODEL: str = "gpt-4o-mini"

    ENRICH_PROJECTS: list[str] = ["food_trends_brands", "food_trends_influencers"]
    ENRICH_PLATFORMS: list[str] = ["instagram", "tiktok"]

    EVIDENCE_MIN_POSTS: int = 3

    TREND_EMBED_MODEL: str = "text-embedding-3-large"
    TREND_EMBED_VARIANT: str = ""
    TREND_EMBED_DIM: int = 1024
    TREND_PROMPT_VERSION: str = "trends-v2"
    TREND_COHORT: str = "cross_v1"
    TREND_MIN_POSTS: int = 50
    TREND_MIN_AUTHORS: int = 30
    TREND_NAMING_MODEL: str | None = None
    TREND_CACHE_DIR: str = ".trend_cache"
    TREND_TRACKED_SOURCES: list[str] = ["brand", "influencer"]
    TREND_EXCLUDE_AUTHORS: list[str] = []
    # Real estate defaults this to "analysis". Food cannot: only 7,604 of its
    # 408,308 posts carry post_analysis, so an analysis-mode community run would
    # find almost nothing. Analysis mode is opted into per run with --documents.
    TREND_DOCUMENT_SOURCE: Literal["analysis", "caption"] = "caption"
    TREND_DOCUMENT_RESCUE_PERCENTILE: float = 25.0

    PLATFORM_TIMEZONE: str = "Asia/Dubai"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
