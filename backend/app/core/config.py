from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
    PROCESSING_MODE: Literal["inline", "celery"] = "inline"

    # JWT Auth
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Storage (MinIO / S3)
    STORAGE_BACKEND: Literal["local", "s3", "blob"] = "local"
    UPLOADS_DIR: str = str(PROJECT_ROOT / "var" / "uploads")
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "intelliclaim-images"
    S3_PUBLIC_ENDPOINT: str = ""

    # ML Service
    ML_SERVICE_URL: str = "http://localhost:8001"
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024

    # Neo4j (Fraud Graph)
    NEO4J_URI: str = "bolt://localhost:7687"
    GRAPH_BACKEND: Literal["sql", "neo4j"] = "sql"
    NEO4J_HTTP_URL: str = "http://localhost:7474"
    NEO4J_DATABASE: str = "neo4j"
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
