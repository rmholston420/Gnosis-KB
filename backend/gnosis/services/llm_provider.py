"""Multi-provider LLM service with automatic fallback.

Provider priority: Ollama (local) → Groq → OpenAI/OpenRouter

If the primary provider is unavailable, the service automatically
falls back to the next available provider. If no provider is available,
raises LLMUnavailableError.

All providers are accessed via the OpenAI-compatible client API.
"""

import logging
from typing import AsyncGenerator, Optional

from gnosis.config import get_settings
from gnosis.core.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)


async def chat_completion(
    messages: list[dict[str, str]],
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Generate a chat completion using the best available LLM provider.

    Tries providers in order: Ollama → Groq → OpenAI.
    Returns the complete response text.

    Args:
        messages: List of {role, content} dicts.
        stream: If True, use streaming (returns full text after stream).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.

    Returns:
        Response text string.

    Raises:
        LLMUnavailableError: If no provider is available.
    """
    settings = get_settings()
    errors: list[str] = []

    # Provider 1: Ollama
    try:
        return await _ollama_chat(messages, temperature, max_tokens)
    except Exception as e:
        errors.append(f"Ollama: {e}")
        logger.debug("Ollama unavailable: %s", e)

    # Provider 2: Groq
    if settings.groq_api_key:
        try:
            return await _openai_compatible_chat(
                messages=messages,
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            errors.append(f"Groq: {e}")
            logger.debug("Groq unavailable: %s", e)

    # Provider 3: OpenAI
    if settings.openai_api_key:
        try:
            return await _openai_compatible_chat(
                messages=messages,
                base_url="https://api.openai.com/v1",
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            errors.append(f"OpenAI: {e}")
            logger.debug("OpenAI unavailable: %s", e)

    # Provider 4: OpenRouter
    if settings.openrouter_api_key:
        try:
            return await _openai_compatible_chat(
                messages=messages,
                base_url=settings.openrouter_base_url,
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    logger.error("All LLM providers failed: %s", "; ".join(errors))
    raise LLMUnavailableError()


async def stream_chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion using the best available provider.

    Yields text chunks as they arrive from the LLM.

    Args:
        messages: List of {role, content} dicts.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.

    Yields:
        Text chunk strings.
    """
    settings = get_settings()

    # Try Ollama streaming first
    try:
        async for chunk in _ollama_stream(messages, temperature, max_tokens):
            yield chunk
        return
    except Exception as e:
        logger.debug("Ollama stream unavailable: %s", e)

    # Fallback: non-streaming via other providers, yield full response
    try:
        response = await chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
        yield response
    except LLMUnavailableError:
        yield "[Error: No LLM provider available]"


async def _ollama_chat(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    """Send a chat request to the local Ollama instance."""
    import ollama  # type: ignore[import-untyped]
    from ollama import AsyncClient

    settings = get_settings()
    client = AsyncClient(host=settings.ollama_base_url)
    response = await client.chat(
        model=settings.ollama_llm_model,
        messages=messages,  # type: ignore[arg-type]
        options={"temperature": temperature, "num_predict": max_tokens},
    )
    return str(response.message.content)


async def _ollama_stream(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> AsyncGenerator[str, None]:
    """Stream chat chunks from the local Ollama instance."""
    from ollama import AsyncClient

    settings = get_settings()
    client = AsyncClient(host=settings.ollama_base_url)
    async for chunk in await client.chat(
        model=settings.ollama_llm_model,
        messages=messages,  # type: ignore[arg-type]
        stream=True,
        options={"temperature": temperature, "num_predict": max_tokens},
    ):
        if chunk.message and chunk.message.content:
            yield chunk.message.content


async def _openai_compatible_chat(
    messages: list[dict[str, str]],
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Send a chat request to any OpenAI-compatible API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    return str(content) if content else ""
