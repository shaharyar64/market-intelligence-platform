from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Real Estate Intelligence service settings.

    Mirrors food_intelligence_service's Settings, which this service was
    copied from, plus the real-estate account filters. See the README's
    "Twin service" note before changing anything the two share.
    """

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Real Estate Intelligence API"

    AWS_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    RE_MEDIA_S3_BUCKET: str = "raw-data-bucket"
    RE_MEDIA_S3_PREFIX_TEMPLATE: str = "media/{platform}/"
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
    ASSISTANT_TEMPERATURE: float = 0.3

    # Which profile `project` values mark a tracked account. Developers and
    # influencers are separate because only Trends Explorer unions them.
    BRAND_PROJECTS: list[str] = ["realestate_dbh", "realestate_trends"]
    INFLUENCER_PROJECT: str = "realestate_trends_influencers"
    ENRICH_PROJECTS: list[str] = ["realestate_dbh", "realestate_trends",
                                  "realestate_trends_influencers"]
    ENRICH_PLATFORMS: list[str] = ["instagram", "tiktok", "twitter", "linkedin"]

    EVIDENCE_MIN_POSTS: int = 3

    TREND_EMBED_MODEL: str = "text-embedding-3-large"
    TREND_EMBED_VARIANT: str = ""
    TREND_EMBED_DIM: int = 1024
    TREND_PROMPT_VERSION: str = "re-trends-v5"
    # Our cohorts are brand / influencer / community. "all" means no cohort
    # filter, which is what a cross-source trend run wants.
    TREND_COHORT: str = "all"
    TREND_MIN_POSTS: int = 50
    TREND_NAMING_MODEL: str | None = None
    TREND_CACHE_DIR: str = ".trend_cache_re"
    TREND_ACCOUNT_BIAS_SHRINK: int = 20
    TREND_KEYWORD_MAX_ACCOUNT_SHARE: float = 0.5
    TREND_KEYWORD_MIN_CLUSTER_POSTS: int = 3
    TREND_OUTLIER_RESCUE_PERCENTILE: float = 50.0
    TREND_DOCUMENT_RESCUE_PERCENTILE: float = 25.0
    TREND_DOCUMENT_SOURCE: Literal["analysis", "caption"] = "analysis"
    TREND_EXCLUDE_AUTHORS: list[str] = ["rallysaudi", "zahra_ksa"]
    TREND_TRACKED_SOURCES: list[str] = ["brand", "influencer"]

    PLATFORM_TIMEZONE: str = "Asia/Dubai"
    FRONTEND_URL: str = ""
    CORS_ORIGINS: str = ""

    # Same name and defaults the gateway uses, so one env var governs both.
    ENV_NAME: str = "dev"

    @property
    def is_production(self) -> bool:
        return self.ENV_NAME.lower() not in {"dev", "development", "local", "test"}

    @property
    def cors_allow_origins(self) -> list[str]:
        configured = [o.strip() for o in self.CORS_ORIGINS.split(",")]
        origins = [
            self.FRONTEND_URL.rstrip("/"),
            *configured,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        return list(dict.fromkeys(o for o in origins if o))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
