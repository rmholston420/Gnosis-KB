"""Application configuration via pydantic-settings.

All settings are loaded from environment variables (with .env file support).
Every value has a sensible default for local development.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "Gnosis Knowledge Base"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://gnosis:gnosis_dev@localhost:5432/gnosis",
        description="Async SQLAlchemy database URL (asyncpg driver)",
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Sync URL for Alembic migrations (psycopg2)
    @property
    def database_url_sync(self) -> str:
        """Return synchronous database URL for Alembic."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )

    # -------------------------------------------------------------------------
    # Vector Store (Qdrant)
    # -------------------------------------------------------------------------
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "gnosis_notes"

    # -------------------------------------------------------------------------
    # Vault
    # -------------------------------------------------------------------------
    vault_path: Path = Field(
        default=Path("/vault"),
        description="Absolute path to the Markdown vault directory",
    )

    @field_validator("vault_path", mode="before")
    @classmethod
    def expand_vault_path(cls, v: object) -> Path:
        """Expand ~ and resolve relative paths."""
        return Path(str(v)).expanduser().resolve()

    # Vault PARA subdirectories
    vault_dirs: list[str] = [
        "00-inbox",
        "10-zettelkasten",
        "20-projects",
        "30-areas",
        "40-resources",
        "50-archive",
        "60-journals",
        "70-sources",
        "80-meta",
    ]

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------
    secret_key: str = Field(
        default="change_in_production_immediately",
        description="JWT signing secret — generate with: openssl rand -hex 32",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    # -------------------------------------------------------------------------
    # AI Providers
    # -------------------------------------------------------------------------
    # Ollama (primary / local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:14b"
    ollama_embed_model: str = "nomic-embed-text"

    # External fallbacks (optional)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # -------------------------------------------------------------------------
    # LightRAG
    # -------------------------------------------------------------------------
    lightrag_working_dir: str = "./lightrag-data"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:80",
    ]


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance.

    Using lru_cache ensures Settings is only instantiated once per process,
    which is the correct pattern for production apps.
    """
    return Settings()
