from pydantic_settings import BaseSettings
from pydantic import model_validator, Field
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # App
    APP_NAME: str = "IntelliClaim"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "production"] = "production"
    DEBUG: bool = False

    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    MAX_IMAGE_PIXELS: int = Field(default=20_000_000, gt=0)
    MAX_IMAGES_PER_CLAIM: int = Field(default=12, gt=0)

    @model_validator(mode="after")
    def production_secrets(self):
        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if len(self.ML_API_KEY) < 32:
                raise ValueError("Production requires a strong ML_API_KEY")
            if len(self.SECRET_KEY) < 32 or self.SECRET_KEY.startswith("change-this"):
                raise ValueError("Production requires a strong explicitly configured SECRET_KEY")
            if self.S3_ACCESS_KEY == "minioadmin" or self.S3_SECRET_KEY == "minioadmin":
                raise ValueError("Production requires non-default storage credentials")
            if "postgres:postgres@" in self.DATABASE_URL:
                raise ValueError("Production requires non-default database/graph credentials")
        return self

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/intelliclaim"
    # For local dev without Docker, use SQLite:
    # DATABASE_URL: str = "sqlite+aiosqlite:///./intelliclaim.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Auth
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Storage (MinIO / S3)
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "intelliclaim-images"

    # ML Service
    ML_API_KEY: str = ""
    PROCESSING_LEASE_SECONDS: int = Field(default=180, ge=30)
    PROCESSING_MAX_RUNS: int = Field(default=3, ge=1, le=10)
    MAX_CLAIM_ATTEMPTS: int = Field(default=5, ge=1)
    WORKER_POLL_SECONDS: int = Field(default=10, ge=1)
    ML_SERVICE_URL: str = "http://localhost:8001"

    # Neo4j (Fraud Graph)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "intelliclaim"

    # SMTP Email Notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 0
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
