from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.domain.models import Chunk, RetrievalFilters, chunk_matches_filters
from app.utils.text import normalize_for_intent, tokenize


class LexicalIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.tokenized_chunks: list[list[str]] = []
        self.index: BM25Okapi | None = None

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = [chunk for chunk in chunks if not chunk.is_parent]
        self.tokenized_chunks = [_search_tokens(_searchable_text(chunk)) for chunk in self.chunks]
        self.index = BM25Okapi(self.tokenized_chunks) if self.tokenized_chunks else None

    def search(
        self,
        query: str,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> list[Chunk]:
        chunks = [chunk for chunk in self.chunks if chunk_matches_filters(chunk, filters)]
        if not chunks:
            return []
        tokenized_chunks = (
            self.tokenized_chunks
            if filters is None
            else [_search_tokens(_searchable_text(chunk)) for chunk in chunks]
        )
        index = self.index if filters is None else BM25Okapi(tokenized_chunks)
        if not index:
            return []
        query_tokens = _search_tokens(query)
        query_terms = set(query_tokens)
        scores = index.get_scores(query_tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda item: _combined_score(
                float(item[1]),
                tokenized_chunks[item[0]],
                query_terms,
            ),
            reverse=True,
        )[:top_k]
        results: list[Chunk] = []
        for index, score in ranked:
            score_value = _combined_score(float(score), tokenized_chunks[index], query_terms)
            if score_value <= 0:
                continue
            chunk = chunks[index]
            chunk.score = score_value
            results.append(chunk)
        return results


def _searchable_text(chunk: Chunk) -> str:
    return "\n".join(
        [
            chunk.document_name,
            chunk.section,
            " > ".join(chunk.heading_path),
            chunk.content,
        ]
    )


def _search_tokens(text: str) -> list[str]:
    return tokenize(normalize_for_intent(text))


def _combined_score(bm25_score: float, tokens: list[str], query_terms: set[str]) -> float:
    overlap_score = len(query_terms.intersection(tokens))
    return bm25_score + overlap_score
