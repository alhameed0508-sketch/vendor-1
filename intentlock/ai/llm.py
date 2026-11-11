"""Model access. One narrow call: structured JSON out, validated by the caller.

The model never receives database credentials, never calls payment APIs and never decides a policy result.
There is no template or mock fallback: if the model is unavailable the caller gets AIUnavailable.
"""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from intentlock.settings import Settings


class AIUnavailable(Exception):
    """The model is disabled, unsupported, unreachable or returned something unusable."""


class LLM(Protocol):
    model: str

    def generate_json(self, system: str, user: str, schema: dict) -> dict: ...


class GeminiLLM:
    """Google Gemini over REST with a response schema."""

    ATTEMPTS = 2

    def __init__(self, api_key: str, model: str, timeout_s: float = 25.0, transport: httpx.BaseTransport | None = None) -> None:
        self.model = model
        self._key = api_key
        self._http = httpx.Client(base_url="https://generativelanguage.googleapis.com", timeout=timeout_s, transport=transport)

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": schema},
        }
        r, last = None, "no attempt made"
        for _attempt in range(self.ATTEMPTS):  # bounded: a slow or busy model gets one more try, then we give up
            try:
                r = self._http.post(f"/v1beta/models/{self.model}:generateContent", json=body, headers={"x-goog-api-key": self._key})
            except httpx.HTTPError as exc:
                r, last = None, f"could not be reached ({type(exc).__name__})"
                continue
            if r.status_code == 200:
                break
            last = f"returned HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        if r is None or r.status_code != 200:
            raise AIUnavailable(f"The model {last}")
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIUnavailable("The model did not return valid JSON") from exc
        if not isinstance(data, dict):
            raise AIUnavailable("The model did not return a JSON object")
        return data


def build_llm(settings: Settings) -> LLM | None:
    """Return a model client, or None when AI is not configured. Callers must handle None explicitly."""
    if not settings.ai_configured:
        return None
    if settings.genai_provider.lower() == "gemini":
        return GeminiLLM(settings.genai_api_key, settings.genai_model, settings.genai_timeout_seconds)
    return None
