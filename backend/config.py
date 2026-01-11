"""
Configuration settings for Procura backend.
Production-ready configuration following FastAPI best practices.
"""
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Procura"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    demo_mode: bool = True  # Simulates actions without external calls

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = Field(default=1, description="Number of Gunicorn workers")

    # Database - async support
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/procura"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_pool_recycle: int = 3600  # Recycle connections after 1 hour

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600  # 1 hour default cache TTL

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60  # Requests per window
    rate_limit_window: int = 60  # Window in seconds

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""  # For embeddings

    # Model settings
    llm_model: str = "claude-sonnet-4-20250514"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0
    llm_timeout: int = 120  # seconds

    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Agent settings
    max_agent_iterations: int = 10
    agent_timeout_seconds: int = 120

    # RAG settings
    rag_enabled: bool = True
    rag_similarity_threshold: float = 0.7
    rag_top_k: int = 5

    # Approval thresholds
    po_approval_threshold: float = 10000.0
    match_confidence_threshold: float = 0.8

    # Observability
    langsmith_api_key: str = ""
    langsmith_project: str = "procura"
    langsmith_tracing: bool = True

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # CORS - supports both local dev and production Render URLs
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://procura-frontend.onrender.com",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for JWT signing"
    )
    access_token_expire_minutes: int = 30

    # Input validation limits
    max_upload_size_mb: int = 50
    max_bom_items: int = 10000
    max_request_body_size: int = 10 * 1024 * 1024  # 10MB

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure async driver is used."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v

    @field_validator("workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """Default to (2 * CPU cores) + 1 in production."""
        import os
        if v == 1 and os.getenv("ENVIRONMENT") == "production":
            cpu_count = os.cpu_count() or 1
            return (2 * cpu_count) + 1
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
