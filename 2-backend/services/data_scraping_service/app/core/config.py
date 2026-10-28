from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Data Scraping Service"
    API_V1_PREFIX: str = "/api/v1"
    APIFY_KEY: str | None = None
    TWITTER_API_KEY: str | None = None
    TWITTER_PROFILE_API_URL: str = "https://api.twitterapi.io/twitter/user/info"
    TWITTER_POSTS_API_URL: str = "https://api.twitterapi.io/twitter/user/last_tweets"
    TWITTER_KEYWORD_API_URL: str = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    APIFY_INSTAGRAM_PROFILE_ACTOR_ID: str = "dSCLg0C3YEZ83HzYX"
    APIFY_INSTAGRAM_POSTS_ACTOR_ID: str = "40m9Ov3RdhuAENlJ0"
    APIFY_TIKTOK_PROFILE_ACTOR_ID: str = "nZqIUKyoBelvbSn1g"
    APIFY_TIKTOK_POSTS_ACTOR_ID: str = "5K30i8aFccKNF5ICs"
    APIFY_LINKEDIN_PROFILE_ACTOR_ID: str = "AjfNXEI9qTA2IdaAX"
    APIFY_LINKEDIN_POSTS_ACTOR_ID: str = "WI0tj4Ieb5Kq458gB"
    APIFY_API_URL: str = "https://api.apify.com/v2"
    APIFY_REQUEST_TIMEOUT: int = 300
    INSTAGRAM_PROFILE_TABLE: str = "instagram_profile"
    INSTAGRAM_POSTS_TABLE: str = "instagram_posts"
    TWITTER_PROFILE_TABLE: str = "twitter_profiles"
    TWITTER_POSTS_TABLE: str = "twitter_posts"
    TWITTER_KEYWORD_POSTS_TABLE: str = "twitter_keyword_posts"
    TIKTOK_PROFILE_TABLE: str = "tiktok_profiles"
    TIKTOK_POSTS_TABLE: str = "tiktok_posts"
    LINKEDIN_PROFILE_TABLE: str = "linkedin_profiles"
    LINKEDIN_POSTS_TABLE: str = "linkedin_posts"
    INSTAGRAM_MEDIA_BUCKET: str = "raw-data-bucket"
    INSTAGRAM_MEDIA_PREFIX: str = "media/instagram/"
    AWS_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    REDIS_HOST: str | None = None
    REDIS_PASSWORD: str | None = None
    SCRAPING_JOB_TTL_SECONDS: int = 86400
    SCHEDULER_POLL_SECONDS: int = 30

    @field_validator(
        "INSTAGRAM_PROFILE_TABLE",
        "INSTAGRAM_POSTS_TABLE",
        "TWITTER_PROFILE_TABLE",
        "TWITTER_POSTS_TABLE",
        "TWITTER_KEYWORD_POSTS_TABLE",
        "TIKTOK_PROFILE_TABLE",
        "TIKTOK_POSTS_TABLE",
        "LINKEDIN_PROFILE_TABLE",
        "LINKEDIN_POSTS_TABLE",
    )
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        parts = value.split(".")
        if not all(part.isidentifier() for part in parts):
            raise ValueError("INSTAGRAM_PROFILE_TABLE must be a valid SQL identifier")
        return value

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
