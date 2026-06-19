"""Application configuration via pydantic-settings.

All values read from environment variables (with .env file support).
Sensible defaults allow the app to start without any env vars set.

Exports
-------
settings          : Settings        -- singleton instance
get_settings      : () -> Settings  -- lru_cache shim for FastAPI Depends()
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config object — instantiated once and imported everywhere."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./gnosis_dev.db"

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "gnosis_notes"

    # Vault
    vault_path: str = "./vault"

    # Multi-user vault root (parent dir containing per-user slug dirs)
    vault_root: str = "./vaults"

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    access_token_expire_minutes: int = 10080  # 7 days
    auth_required: bool = False

    # AI providers
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:14b"
    ollama_embed_model: str = "nomic-embed-text"
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None

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
        """Database URL for Alembic / sync drivers.

        async_engine_from_config (used by alembic/env.py) accepts the
        same aiosqlite/asyncpg URLs as the async engine, so we just
        return ``database_url`` unchanged.  The property exists so that
        ``get_settings().database_url_sync`` resolves without AttributeError
        regardless of which driver is configured.
        """
        return self.database_url


# Singleton — import directly when you don’t need DI.
settings = Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Compatible with ``Depends(get_settings)`` and plain call sites.
    """
    return settings
