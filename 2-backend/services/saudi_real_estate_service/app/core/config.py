from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Saudi Real Estate Intelligence API"
    DEBUG: bool = False
    
    # AWS Configuration
    AWS_REGION: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    
    # Cognito Configuration
    COGNITO_USER_POOL_ID: str
    COGNITO_CLIENT_ID: str
    COGNITO_CLIENT_SECRET: str | None = None
    
    # Admin Configuration
    ADMIN_GROUP_NAME: str = "Admins"
    USER_GROUP_NAME: str = "Users"
    
    # Database Configuration (NEW)
    DB_NAME: str
    SECRET_NAME: str
    DB_HOST: str
    DB_PORT: str = "5432"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()