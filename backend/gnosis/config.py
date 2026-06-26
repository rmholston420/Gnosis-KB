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

import sys
from functools import lru_cache

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
_DEFAULT_ADMIN_PASSWORD = "gnosis_admin"


class Settings(BaseSettings):
    """Central config object — instantiated once and imported everywhere."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter=None,
    )

    # Database
    # Default uses asyncpg (async driver required by SQLAlchemy async engine)
    database_url: str = "postgresql+asyncpg://gnosis:gnosis_secret@postgres:5432/gnosis"

    # Vector store
    qdrant_url: str = "http://qdrant:6333"
    # Single canonical name — the former `qdrant_collection` duplicate field has
    # been removed. Any env var previously set as QDRANT_COLLECTION should be
    # renamed to QDRANT_COLLECTION_NAME.
    qdrant_collection_name: str = "gnosis_notes"
    qdrant_api_key: str | None = None

    # Vault
    vault_path: str = "/vault"

    # Multi-user vault root (parent dir containing per-user slug dirs)
    vault_root: str = "./vaults"

    # LightRAG / graph-RAG working directory
    lightrag_data_dir: str = "/lightrag"

    # Auth
    secret_key: str = _DEFAULT_SECRET
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
    initial_admin_password: str = _DEFAULT_ADMIN_PASSWORD

    @model_validator(mode="after")
    def _check_secret_key_in_production(self) -> "Settings":
        """Fail fast if the default placeholder secret_key is used outside debug mode.

        A production deploy with the well-known placeholder key allows any
        attacker to forge valid JWTs. This guard causes an explicit startup
        crash with a clear message rather than silent insecurity.
        """
        if not self.debug and self.secret_key == _DEFAULT_SECRET:
            print(  # noqa: T201
                "\n[FATAL] secret_key is still the default placeholder value.\n"
                "Set SECRET_KEY to a random 32-byte hex string before running in production.\n"
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"\n",
                file=sys.stderr,
            )
            raise ValueError(
                "SECRET_KEY must be changed from the default before running with debug=False"
            )
        return self

    @model_validator(mode="after")
    def _warn_default_admin_password(self) -> "Settings":
        """Warn loudly when the default admin password is unchanged in production.

        Fix (2025-06-26): parallel to the secret_key guard. Unlike secret_key,
        a weak admin password is non-fatal (the app can still start) but we
        emit a prominent stderr warning so it is visible in Docker Compose logs
        and CI output. Change INITIAL_ADMIN_PASSWORD before first deployment.
        """
        if not self.debug and self.initial_admin_password == _DEFAULT_ADMIN_PASSWORD:
            print(  # noqa: T201
                "\n[WARNING] initial_admin_password is still the default 'gnosis_admin'.\n"
                "Set INITIAL_ADMIN_PASSWORD in your .env or environment before deploying.\n",
                file=sys.stderr,
            )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        """Return the synchronous (psycopg2) variant of the database URL.

        Alembic migrations run synchronously and require psycopg2, while the
        main application uses asyncpg. This swaps the driver prefix so both
        can share the same base DATABASE_URL environment variable.
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace(
            "postgresql://", "postgresql+psycopg2://"
        )


# Singleton — import directly when you don't need DI.
settings = Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Compatible with ``Depends(get_settings)`` and plain call sites.
    """
    return settings
