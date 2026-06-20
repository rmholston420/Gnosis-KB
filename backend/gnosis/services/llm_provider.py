"""
Multi-provider LLM service with three-tier auto-fallback:
  Tier 1: Ollama (local, sovereign)
  Tier 2: Groq (fast cloud fallback)
  Tier 3: OpenAI (final fallback)

All providers share the OpenAI-compatible API surface.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import httpx
from openai import AsyncOpenAI

from gnosis.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMProvider:
    """Three-tier LLM provider with automatic fallback."""

    def __init__(self) -> None:
        self._ollama_client: AsyncOpenAI | None = None
        self._groq_client: AsyncOpenAI | None = None
        self._openai_client: AsyncOpenAI | None = None
        self._available: list[str] = []
        self._ollama_model: str = settings.ollama_llm_model

    async def initialize(self) -> None:
        """Probe each provider tier and record which are available."""
        self._ollama_model = settings.ollama_llm_model

        # Tier 1: Ollama
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                if resp.status_code == 200:
                    self._ollama_client = AsyncOpenAI(
                        base_url=f"{settings.ollama_base_url}/v1",
                        api_key="ollama",
                    )
                    self._available.append("ollama")
                    logger.info("LLM provider: Ollama available at %s", settings.ollama_base_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM provider: Ollama not reachable (%s) — will skip", exc)

        # Tier 2: Groq
        if settings.groq_api_key:
            self._groq_client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
            )
            self._available.append("groq")
            logger.info("LLM provider: Groq configured")

        # Tier 3: OpenAI
        if settings.openai_api_key:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self._available.append("openai")
            logger.info("LLM provider: OpenAI configured")

        if not self._available:
            logger.warning(
                "LLM provider: No providers available. "
                "Start Ollama or set GROQ_API_KEY / OPENAI_API_KEY."
            )

    # ---- Runtime introspection ----------------------------------------

    @property
    def is_available(self) -> bool:
        return bool(self._available)

    @property
    def active_provider(self) -> str:
        """Name of the highest-priority available provider."""
        for p in ("ollama", "groq", "openai"):
            if p in self._available:
                return p
        return "none"

    @property
    def active_model(self) -> str:
        """Model name in use for the active provider."""
        p = self.active_provider
        if p == "ollama":
            return self._ollama_model
        if p == "groq":
            return "llama-3.3-70b-versatile"
        if p == "openai":
            return "gpt-4o-mini"
        return ""

    def swap_model(self, model: str) -> None:
        """Hot-swap the Ollama model without restarting. No-op for other providers."""
        if "ollama" not in self._available:
            raise RuntimeError("Ollama is not an available provider")
        self._ollama_model = model
        logger.info("LLM provider: Ollama model swapped to %s", model)

    # ---- Client resolution --------------------------------------------

    def _get_client_and_model(self) -> tuple[AsyncOpenAI, str]:
        """Return the highest-priority available client and its model name."""
        if "ollama" in self._available and self._ollama_client:
            return self._ollama_client, self._ollama_model
        if "groq" in self._available and self._groq_client:
            return self._groq_client, "llama-3.3-70b-versatile"
        if "openai" in self._available and self._openai_client:
            return self._openai_client, "gpt-4o-mini"
        raise RuntimeError("No LLM provider available")

    def _get_client_for(self, provider: str) -> tuple[AsyncOpenAI, str]:
        """Return (client, model) for the named provider."""
        if provider == "ollama" and self._ollama_client:
            return self._ollama_client, self._ollama_model
        if provider == "groq" and self._groq_client:
            return self._groq_client, "llama-3.3-70b-versatile"
        if provider == "openai" and self._openai_client:
            return self._openai_client, "gpt-4o-mini"
        raise ValueError(f"Unknown or unconfigured provider: {provider}")

    # ---- Completion API -----------------------------------------------

    async def complete(
        self,
        prompt: str,
        system: str = "You are a helpful knowledge management assistant.",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        providers = list(self._available)
        last_exc: Exception | None = None
        for provider in providers:
            client, model = self._get_client_for(provider)
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM provider %s failed: %s — trying next", provider, exc)
                last_exc = exc
                continue
        raise RuntimeError(f"All LLM providers failed. Last error: {last_exc}")

    async def stream(
        self,
        prompt: str,
        system: str = "You are a helpful knowledge management assistant.",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        providers = list(self._available)
        last_exc: Exception | None = None
        for provider in providers:
            client, model = self._get_client_for(provider)
            try:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM stream provider %s failed: %s — trying next", provider, exc)
                last_exc = exc
                continue
        raise RuntimeError(f"All LLM stream providers failed. Last error: {last_exc}")


# Module-level singleton — initialized at application startup via lifespan
llm_provider = LLMProvider()
