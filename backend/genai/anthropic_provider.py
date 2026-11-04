"""
Anthropic LLM provider.

Alternative provider — Claude Haiku 4.5 at ~$211/month for 20K alerts.
"""

from __future__ import annotations

import logging
import time
from typing import List

from genai.base import LLMMessage, LLMProvider, LLMResponse
from genai.retry import with_retry

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic via the anthropic Python SDK."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20250514"):
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError("anthropic package required: pip install anthropic") from exc

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def generate(
        self,
        messages: List[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> LLMResponse:
        start = time.perf_counter()

        # Anthropic separates system from conversation messages
        system_text = "\n\n".join(m.content for m in messages if m.role == "system")
        conversation = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        kwargs = {
            "model": self._model,
            "messages": conversation,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout_seconds,
        }
        if system_text:
            kwargs["system"] = system_text

        response = with_retry(
            lambda: self._client.messages.create(**kwargs),
            provider_name="anthropic",
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        content = ""
        if response.content:
            content = response.content[0].text

        prompt_tokens = getattr(response.usage, "input_tokens", 0)
        completion_tokens = getattr(response.usage, "output_tokens", 0)

        return LLMResponse(
            content=content,
            model=self._model,
            provider="anthropic",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(elapsed_ms, 1),
        )
