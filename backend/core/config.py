from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from functools import lru_cache

# Anchor .env path to project root (two levels up from this file: core/ -> backend/ -> project root)
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    # Database
    database_url: str = "postgresql://bug0:bug0pass@localhost:5432/bug0db"
    # Redis
    redis_url: str = "redis://:bug0redis@localhost:6380/0"
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
    ollama_api_key: str = ""
    ollama_base_url: str = "https://api.ollama.com/v1"
    ollama_model: str = "qwen3.5"
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

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        if self.environment != "development" and self.secret_key == "REPLACE_THIS_WITH_RANDOM_32_CHAR_STRING":
            raise ValueError(
                "SECRET_KEY must be set to a secure random value in non-development environments."
            )
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
