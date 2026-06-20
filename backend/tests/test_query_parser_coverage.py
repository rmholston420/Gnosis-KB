"""Coverage tests for gnosis/services/query_parser.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_parse_query_returns_dict():
    with patch("gnosis.services.query_parser.LLMProvider") as mock_llm_cls:
        mock_provider = AsyncMock()
        mock_provider.get_completion = AsyncMock(
            return_value='{"intent": "search", "keywords": ["python"], "filters": {}}'
        )
        mock_llm_cls.return_value = mock_provider

        from gnosis.services.query_parser import parse_query
        result = await parse_query("Find notes about python")
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_parse_query_invalid_json_returns_fallback():
    with patch("gnosis.services.query_parser.LLMProvider") as mock_llm_cls:
        mock_provider = AsyncMock()
        mock_provider.get_completion = AsyncMock(return_value="not valid json")
        mock_llm_cls.return_value = mock_provider

        from gnosis.services.query_parser import parse_query
        result = await parse_query("some query")
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_parse_query_llm_error_returns_fallback():
    with patch("gnosis.services.query_parser.LLMProvider") as mock_llm_cls:
        mock_provider = AsyncMock()
        mock_provider.get_completion = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_llm_cls.return_value = mock_provider

        from gnosis.services.query_parser import parse_query
        result = await parse_query("test query")
        assert isinstance(result, dict)


def test_build_search_context_returns_string():
    from gnosis.services.query_parser import build_search_context
    notes = [
        {"title": "Python Basics", "body": "Python is a language.", "score": 0.9},
        {"title": "ML Intro", "body": "Machine learning overview.", "score": 0.7},
    ]
    context = build_search_context(notes)
    assert isinstance(context, str)
    assert "Python Basics" in context


def test_build_search_context_empty():
    from gnosis.services.query_parser import build_search_context
    assert build_search_context([]) == ""
