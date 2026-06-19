"""Application configuration via pydantic-settings.

All values read from environment variables (with .env file support).
Sensible defaults allow the app to start without any env vars set.

Exports
-------
settings     : Settings   -- singleton instance (import directly for speed)
get_settings : () -> Settings -- callable shim used by FastAPI Depends()
                                 and any code that prefers the function form
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
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

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    access_token_expire_minutes: int = 10080  # 7 days
    auth_required: bool = False  # Set True to enforce login

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

    # Bootstrap admin (used by startup event if no users exist)
    initial_admin_email: str = "admin@gnosis.local"
    initial_admin_password: str = "gnosis_admin"

    # Multi-user vault root  (parent directory that contains per-user slug dirs)
    vault_root: str = "./vaults"


# Singleton — import `settings` directly when you don’t need DI.
settings = Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Compatible with FastAPI’s ``Depends(get_settings)`` pattern and with
    plain ``get_settings()`` call sites (routers, alembic env.py, etc.).
    """
    return settings
