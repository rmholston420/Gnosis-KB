"""Application configuration via pydantic-settings.

All values read from environment variables (with .env file support).
Environment variables always take precedence over .env file values.
Sensible defaults allow the app to start without any env vars set.

Exports
-------
settings          : Settings        -- singleton instance
get_settings      : () -> Settings  -- lru_cache shim for FastAPI Depends()
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config object — instantiated once and imported everywhere."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Environment variables always win over .env file
        env_nested_delimiter=None,
    )

    # Database
    # Default uses asyncpg (async driver required by SQLAlchemy async engine)
    database_url: str = "postgresql+asyncpg://gnosis:gnosis_secret@postgres:5432/gnosis"

    # Vector store
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "gnosis_notes"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "gnosis_notes"

    # Vault
    vault_path: str = "/vault"

    # Multi-user vault root (parent dir containing per-user slug dirs)
    vault_root: str = "./vaults"

    # LightRAG / graph-RAG working directory
    lightrag_data_dir: str = "/lightrag"

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days
    auth_required: bool = False

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3010",
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    # AI providers
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_llm_model: str = "mistral"
    ollama_embed_model: str = "nomic-embed-text"
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None

    # Application
    log_level: str = "info"
    log_format: str = "text"  # "text" | "json"
    debug: bool = False
    enable_pdf_export: bool = False

    # Bootstrap admin
    initial_admin_email: str = "admin@gnosis.local"
    initial_admin_password: str = "gnosis_admin"

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """Return the synchronous (psycopg2) variant of the database URL.

        Alembic migrations run synchronously and require psycopg2, while the
        main application uses asyncpg. This swaps the driver prefix so both
        can share the same base DATABASE_URL environment variable.
        """
        return (
            self.database_url
            .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            .replace("postgresql://", "postgresql+psycopg2://")
        )


# Singleton — import directly when you don't need DI.
settings = Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Compatible with ``Depends(get_settings)`` and plain call sites.
    """
    return settings
