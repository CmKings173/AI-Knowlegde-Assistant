from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

