"""
OpenAI LLM provider.

Alternative provider — GPT-4o mini at ~$35/month for 20K alerts.
"""

from __future__ import annotations

import logging
import time
from typing import List

from genai.base import LLMMessage, LLMProvider, LLMResponse
from genai.retry import with_retry

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI via the openai Python SDK."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package required: pip install openai"
            ) from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    def generate(
        self,
        messages: List[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> LLMResponse:
        start = time.perf_counter()

        oai_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        response = with_retry(
            lambda: self._client.chat.completions.create(
                model=self._model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout_seconds,
            ),
            provider_name="openai",
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice else ""

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        return LLMResponse(
            content=content or "",
            model=self._model,
            provider="openai",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(elapsed_ms, 1),
        )
