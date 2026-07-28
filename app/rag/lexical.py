from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.domain.models import Chunk, RetrievalFilters, chunk_matches_filters
from app.utils.text import tokenize


class LexicalIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.index: BM25Okapi | None = None

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = [chunk for chunk in chunks if not chunk.is_parent]
        tokenized = [tokenize(chunk.content) for chunk in self.chunks]
        self.index = BM25Okapi(tokenized) if tokenized else None

    def search(
        self,
        query: str,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> list[Chunk]:
        chunks = [chunk for chunk in self.chunks if chunk_matches_filters(chunk, filters)]
        if not chunks:
            return []
        index = (
            self.index
            if filters is None
            else BM25Okapi([tokenize(chunk.content) for chunk in chunks])
        )
        if not index:
            return []
        scores = index.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)[:top_k]
        results: list[Chunk] = []
        for index, score in ranked:
            if float(score) <= 0:
                continue
            chunk = chunks[index]
            chunk.score = float(score)
            results.append(chunk)
        return results
