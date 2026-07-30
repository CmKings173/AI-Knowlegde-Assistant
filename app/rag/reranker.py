from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.domain.exceptions import RerankerError
from app.domain.models import Chunk


class Reranker:
    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        del query
        return sorted(chunks, key=lambda chunk: chunk.score, reverse=True)[:top_k]


class HttpReranker(Reranker):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.reranker_timeout_seconds)

    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        if not chunks:
            return []
        response = await self.client.post(
            f"{self.settings.reranker_url.rstrip('/')}/rerank",
            headers=self._headers(),
            json=self._payload(query, chunks, top_k),
        )
        if response.status_code >= 400:
            raise RerankerError(f"Reranker failed: {response.status_code}")
        return _rank_chunks(chunks, response.json(), top_k)

    def _headers(self) -> dict[str, str]:
        if not self.settings.reranker_api_key:
            return {}
        return {"Authorization": f"Bearer {self.settings.reranker_api_key}"}

    def _payload(self, query: str, chunks: list[Chunk], top_k: int) -> dict[str, object]:
        documents = [chunk.content for chunk in chunks]
        if self.settings.reranker_provider.lower() == "tei":
            return {
                "query": query,
                "texts": documents,
                "top_n": top_k,
            }
        return {
            "model": self.settings.reranker_model,
            "query": query,
            "documents": documents,
            "top_n": top_k,
        }


def create_reranker(settings: Settings) -> Reranker | None:
    if not settings.reranker_enabled:
        return None
    provider = settings.reranker_provider.lower()
    if provider in {"http", "tei", "infinity"}:
        return HttpReranker(settings)
    raise RerankerError(f"Unsupported reranker provider: {settings.reranker_provider}")


def _rank_chunks(chunks: list[Chunk], payload: Any, top_k: int) -> list[Chunk]:
    results = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        raise RerankerError("Reranker response missing results")
    ranked: list[Chunk] = []
    for item in results:
        index, score = _parse_result(item)
        if index < 0 or index >= len(chunks):
            continue
        chunk = chunks[index]
        chunk.score = score
        ranked.append(chunk)
    if not ranked:
        raise RerankerError("Reranker response did not contain valid chunk indexes")
    return ranked[:top_k]


def _parse_result(item: Any) -> tuple[int, float]:
    if not isinstance(item, dict):
        raise RerankerError("Invalid reranker result item")
    index = item.get("index")
    if index is None and isinstance(item.get("document"), dict):
        index = item["document"].get("index")
    score = item.get("relevance_score", item.get("score"))
    if not isinstance(index, int) or not isinstance(score, int | float):
        raise RerankerError("Invalid reranker result index or score")
    return index, float(score)
