from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.config import Settings
from app.domain.exceptions import LLMProviderError
from app.providers.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = await self.client.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
        except httpx.HTTPError as exc:
            raise LLMProviderError(str(exc)) from exc
        if response.status_code >= 400:
            raise LLMProviderError(f"Ollama failed: {response.status_code}")
        return response.json()["message"]["content"]

    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        try:
            async with self.client.stream(
                "POST",
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            ) as response:
                if response.status_code >= 400:
                    raise LLMProviderError(f"Ollama failed: {response.status_code}")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise LLMProviderError("Ollama returned invalid stream JSON") from exc
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield str(content)
        except httpx.HTTPError as exc:
            raise LLMProviderError(str(exc)) from exc
