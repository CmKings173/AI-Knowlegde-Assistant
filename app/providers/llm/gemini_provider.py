from __future__ import annotations

import httpx

from app.config import Settings
from app.domain.exceptions import LLMProviderError
from app.providers.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=90)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.gemini_api_key:
            raise LLMProviderError("GEMINI_API_KEY is required")
        response = await self.client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent",
            params={"key": self.settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.1},
            },
        )
        if response.status_code >= 400:
            raise LLMProviderError(f"Gemini LLM failed: {response.status_code}")
        candidates = response.json().get("candidates", [])
        if not candidates:
            raise LLMProviderError("Gemini returned no candidates")
        return candidates[0]["content"]["parts"][0]["text"]

