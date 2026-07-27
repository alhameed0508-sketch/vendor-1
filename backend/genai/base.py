"""
LLM Provider abstraction — ABC and data models.

All providers implement LLMProvider and return LLMResponse.
Frozen dataclasses ensure immutability throughout the pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMMessage:
    """Single message in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """Immutable response from an LLM provider."""

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g. 'gemini', 'openai', 'anthropic')."""

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> LLMResponse:
        """Send messages to the LLM and return a response."""

    def health_check(self) -> bool:
        """Return True if the provider is reachable."""
        try:
            resp = self.generate(
                [LLMMessage(role="user", content="Reply with OK")],
                max_tokens=8,
                timeout_seconds=10.0,
            )
            return len(resp.content) > 0
        except Exception as exc:
            logger.warning(
                "LLM health check failed for %s: %s", self.provider_name, exc
            )
            return False


class TemplateProvider(LLMProvider):
    """
    Fallback provider that returns empty strings.
    Used when no API key is configured — callers should check
    the response and fall back to template-based narratives.
    """

    @property
    def provider_name(self) -> str:
        return "template_fallback"

    def generate(
        self,
        messages: List[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> LLMResponse:
        return LLMResponse(
            content="",
            model="template",
            provider="template_fallback",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0.0,
        )

    def health_check(self) -> bool:
        return True
