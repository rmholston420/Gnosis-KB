"""Application configuration via Pydantic Settings.

All settings can be overridden via environment variables or .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gnosis application settings.

    Loaded from environment variables and .env file.
    All settings have sensible defaults for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_name: str = "Gnosis Knowledge Base"
    app_version: str = "1.0.0"
    debug: bool = False

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+asyncpg://gnosis:gnosis_secret@localhost:5432/gnosis",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://gnosis:gnosis_secret@localhost:5432/gnosis",
        alias="DATABASE_URL_SYNC",
    )

    # ---- Vault ----
    vault_path: Path = Field(
        default=Path.home() / "gnosis-vault",
        alias="VAULT_PATH",
    )
    lightrag_working_dir: str = Field(
        default=str(Path.home() / ".gnosis" / "lightrag"),
        alias="LIGHTRAG_WORKING_DIR",
    )

    # ---- Qdrant ----
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(default="gnosis_notes", alias="QDRANT_COLLECTION_NAME")

    # ---- Ollama ----
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_llm_model: str = Field(default="mistral", alias="OLLAMA_LLM_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")

    # ---- Groq ----
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")

    # ---- OpenAI ----
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # ---- OpenRouter ----
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        alias="OPENROUTER_MODEL",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )

    # ---- Security ----
    secret_key: str = Field(
        default="changeme-replace-in-production",
        alias="SECRET_KEY",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ---- CORS ----
    cors_origins: list[str] = Field(
        default=["http://localhost:3010", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings.

    Uses lru_cache to ensure Settings is only instantiated once.
    In tests, call get_settings.cache_clear() to reset.
    """
    return Settings()
