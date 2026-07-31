from __future__ import annotations

from app.domain.models import Chunk


class Reranker:
    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        del query
        return sorted(chunks, key=lambda chunk: chunk.score, reverse=True)[:top_k]

