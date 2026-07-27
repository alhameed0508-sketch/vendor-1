"""
Google Gemini LLM provider.

Primary choice for IOB deployment:
- Indian data residency (Google Cloud Mumbai region)
- Cost: ~$35/month for 20K alerts (Gemini 2.5 Flash)
- Free tier available for demo/hackathon
"""

from __future__ import annotations

import logging
import time
from typing import List

from genai.base import LLMMessage, LLMProvider, LLMResponse
from genai.retry import with_retry

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini via google-generativeai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package required: pip install google-generativeai"
            ) from exc

        genai.configure(api_key=api_key)
        self._model_name = model
        self._model = genai.GenerativeModel(model)
        self._genai = genai

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(
        self,
        messages: List[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> LLMResponse:
        start = time.perf_counter()

        # Gemini uses a flat prompt model — combine system + user messages
        system_parts = [m.content for m in messages if m.role == "system"]
        # Build conversation content
        contents = []
        if system_parts:
            contents.append({"role": "user", "parts": ["\n".join(system_parts)]})
            contents.append(
                {
                    "role": "model",
                    "parts": ["Understood. I will follow these instructions."],
                }
            )

        for msg in messages:
            if msg.role == "system":
                continue
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [msg.content]})

        generation_config = self._genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = with_retry(
            lambda: self._model.generate_content(
                contents,
                generation_config=generation_config,
                request_options={"timeout": timeout_seconds},
            ),
            provider_name="gemini",
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Extract token counts from usage metadata
        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
            completion_tokens = getattr(
                response.usage_metadata, "candidates_token_count", 0
            )

        return LLMResponse(
            content=response.text or "",
            model=self._model_name,
            provider="gemini",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(elapsed_ms, 1),
        )
