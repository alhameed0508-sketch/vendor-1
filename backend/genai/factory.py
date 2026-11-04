"""
LLM Provider factory — reads config and returns the appropriate provider.

Provider selection order:
1. GENAI_PROVIDER env var (gemini | openai | anthropic)
2. Falls back to TemplateProvider if no API key or GenAI disabled
"""

from __future__ import annotations

import logging
from typing import Optional

from genai.base import LLMProvider, TemplateProvider

logger = logging.getLogger(__name__)


def create_llm_provider(settings) -> Optional[LLMProvider]:
    """
    Create an LLM provider based on application settings.

    Returns None if GenAI is disabled. Returns TemplateProvider if
    enabled but no API key is set. Otherwise returns the configured provider.
    """
    if not getattr(settings, "genai_enabled", False):
        logger.info("GenAI disabled — no provider created")
        return None

    api_key = getattr(settings, "genai_api_key", "")
    if not api_key:
        logger.warning("GenAI enabled but no API key — using template fallback")
        return TemplateProvider()

    provider_name = getattr(settings, "genai_provider", "gemini").lower()
    model = getattr(settings, "genai_model", "")

    if provider_name == "gemini":
        from genai.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=api_key,
            model=model or "gemini-2.5-flash",
        )

    if provider_name == "openai":
        from genai.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o-mini",
        )

    if provider_name == "anthropic":
        from genai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=api_key,
            model=model or "claude-haiku-4-5-20250514",
        )

    logger.error("Unknown GenAI provider '%s' — using template fallback", provider_name)
    return TemplateProvider()
