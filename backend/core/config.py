from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://bug0:bug0pass@localhost:5432/bug0db"
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = "bug0redis"
    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "bug0minio"
    minio_secret_key: str = "bug0miniopass"
    minio_bucket: str = "bug0-artifacts"
    # Auth
    secret_key: str = "REPLACE_THIS_WITH_RANDOM_32_CHAR_STRING"
    access_token_expire_minutes: int = 1440
    # OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    # AI
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    llm_provider: str = "claude"
    # Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Notifications
    sendgrid_api_key: str = ""
    # App
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    environment: str = "development"
    # Sentry
    sentry_dsn: str = ""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
