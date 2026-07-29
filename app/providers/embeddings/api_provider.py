from __future__ import annotations

import hashlib
import math

import httpx

from app.config import Settings
from app.domain.exceptions import EmbeddingError
from app.providers.embeddings.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required for OpenAI embeddings")
        response = await self.client.post(
            f"{self.settings.openai_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json={"model": self.settings.openai_embedding_model, "input": texts},
        )
        if response.status_code >= 400:
            raise EmbeddingError(f"OpenAI embedding failed: {response.status_code}")
        data = response.json()
        return [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.settings.gemini_api_key:
            raise EmbeddingError("GEMINI_API_KEY is required for Gemini embeddings")
        vectors: list[list[float]] = []
        model = self.settings.gemini_embedding_model
        for text in texts:
            response = await self.client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent",
                params={"key": self.settings.gemini_api_key},
                json={"content": {"parts": [{"text": text}]}},
            )
            if response.status_code >= 400:
                raise EmbeddingError(f"Gemini embedding failed: {response.status_code}")
            vectors.append(response.json()["embedding"]["values"])
        return vectors


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.post(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/embed",
            json={"model": self.settings.ollama_embedding_model, "input": texts},
        )
        if response.status_code >= 400:
            raise EmbeddingError(f"Ollama embedding failed: {response.status_code}")
        data = response.json()
        vectors = data.get("embeddings")
        if not isinstance(vectors, list):
            raise EmbeddingError("Ollama embedding response missing embeddings")
        if len(vectors) != len(texts):
            raise EmbeddingError("Ollama embedding count mismatch")
        return vectors


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding for tests and offline smoke checks."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            values[index] += sign
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    if provider == "gemini":
        return GeminiEmbeddingProvider(settings)
    if provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    if provider == "hash":
        return HashEmbeddingProvider()
    raise EmbeddingError(f"Unsupported embedding provider: {settings.embedding_provider}")
