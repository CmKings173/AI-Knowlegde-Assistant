from __future__ import annotations

import httpx

from app.config import Settings
from app.domain.exceptions import LLMProviderError
from app.providers.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=90)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.openai_api_key or not self.settings.openai_model:
            raise LLMProviderError("OpenAI-compatible LLM needs OPENAI_API_KEY and OPENAI_MODEL")
        response = await self.client.post(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json={
                "model": self.settings.openai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            },
        )
        if response.status_code >= 400:
            raise LLMProviderError(f"OpenAI-compatible LLM failed: {response.status_code}")
        return response.json()["choices"][0]["message"]["content"]

