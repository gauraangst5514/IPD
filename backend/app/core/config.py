from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "IntelliClaim"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

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
