from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Analytics Platform dashboards"
    DEBUG: bool = False

    # Services
    HORECA_SERVICE_URL: str = "http://localhost:8001"
    EV_SERVICE_URL: str = "http://localhost:8002"
    BANK_SPATIAL_SERVICE_URL: str = "http://localhost:8003"
    BEER_CIDER_SERVICE_URL: str = "http://localhost:8004"
    DIGITAL_BRAND_HEALTH_SERVICE_URL: str = "http://localhost:8005"
    DATA_SCRAPING_SERVICE_URL: str = "http://localhost:8006"
    REAL_ESTATE_SERVICE_URL: str = "http://localhost:8007"
    FOOD_INTELLIGENCE_SERVICE_URL: str = "http://localhost:8008"
    SAUDI_REAL_ESTATE_SERVICE_URL: str = "http://localhost:8009"
    TRENDS_REAL_ESTATE_SERVICE_URL: str = "http://localhost:8010"
    BANK_BRAND_HEALTH_SERVICE_URL: str = "http://localhost:8011"
    CEER_CAMPAIGN_SERVICE_URL: str = "http://localhost:8012"
    UAE_BANK_BRAND_HEALTH_SERVICE_URL: str = "http://localhost:8013"

    REQUEST_TIMEOUT : int = 320

    # AWS Configuration
    AWS_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # Cognito Configuration
    COGNITO_USER_POOL_ID: str | None = None
    COGNITO_CLIENT_ID: str | None = None
    COGNITO_CLIENT_SECRET: str | None = None

    # Admin Configuration
    ADMIN_GROUP_NAME: str = "Admins"
    USER_GROUP_NAME: str = "Users"

    # Database Configuration (NEW)
    # Set POSTGRES_DSN for local dev to connect directly and skip Secrets Manager.
    # Leave it empty in prod so credentials resolve from SECRET_NAME as before.
    POSTGRES_DSN: str | None = None
    DB_NAME: str | None = None
    DB_ADMIN: str | None = None
    SECRET_NAME: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str = "5432"
    DB_TABLE_NAME: str = 'beer_pricing_analysis."plaformsV2"'

    # Redis Configuration
    REDIS_HOST: str | None = None
    REDIS_PASSWORD: str | None = None

    # Email / SES
    SES_FROM_EMAIL: str = "noreply@example.com"
    FRONTEND_URL: str = "https://dashboard.example.com"

    # Browser authentication
    AUTH_COOKIE_SECURE: bool | None = None
    AUTH_COOKIE_MAX_AGE: int = 2_592_000
    CORS_ORIGINS: str = ""

    # Environment
    ENV_NAME: str = "dev"

    @property
    def auth_cookie_secure(self) -> bool:
        if self.AUTH_COOKIE_SECURE is not None:
            return self.AUTH_COOKIE_SECURE
        return self.ENV_NAME.lower() not in {"dev", "development", "local", "test"}

    @property
    def cors_origins(self) -> list[str]:
        configured = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        origins = [
            self.FRONTEND_URL.rstrip("/"),
            *configured,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        return list(dict.fromkeys(origin for origin in origins if origin))

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
