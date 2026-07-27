from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.domain.models import Chunk
from app.utils.text import tokenize


class LexicalIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.index: BM25Okapi | None = None

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = [chunk for chunk in chunks if not chunk.is_parent]
        tokenized = [tokenize(chunk.content) for chunk in self.chunks]
        self.index = BM25Okapi(tokenized) if tokenized else None

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not self.index or not self.chunks:
            return []
        scores = self.index.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)[:top_k]
        results: list[Chunk] = []
        for index, score in ranked:
            if float(score) <= 0:
                continue
            chunk = self.chunks[index]
            chunk.score = float(score)
            results.append(chunk)
        return results

