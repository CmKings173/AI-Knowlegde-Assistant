from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import Chunk


class VectorStore(ABC):
    @abstractmethod
    async def ensure_collection(self, vector_size: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, vector: list[float], top_k: int) -> list[Chunk]:
        raise NotImplementedError

    @abstractmethod
    async def delete_document(self, document_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_chunks(self, limit: int = 10_000) -> list[Chunk]:
        raise NotImplementedError

