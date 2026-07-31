from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Protocol

from app.domain.models import (
    Chunk,
    RetrievalFilters,
    RetrievalResult,
    RetrievalSignals,
)
from app.rag.evidence_selector import (
    CandidateQuality,
    EvidenceSelectionConfig,
    assess_candidate_quality,
)
from app.rag.hybrid_search import reciprocal_rank_fusion
from app.rag.prompts import (
    ADAPTIVE_REWRITE_SYSTEM_PROMPT,
    build_adaptive_rewrite_prompt,
)

MAX_REWRITE_QUERIES = 2
MAX_REWRITE_QUERY_CHARS = 300


class RetrieverProtocol(Protocol):
    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult: ...


class LLMProtocol(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...


@dataclass(frozen=True)
class AdaptiveRetrievalResult:
    retrieval: RetrievalResult
    quality: CandidateQuality
    queries: tuple[str, ...]
    rewrite_used: bool = False
    rewrite_error: str | None = None


class AdaptiveRetriever:
    def __init__(
        self,
        retriever: RetrieverProtocol,
        llm_provider: LLMProtocol,
        selection_config: EvidenceSelectionConfig,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.selection_config = selection_config

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AdaptiveRetrievalResult:
        initial = await self.retriever.retrieve(query, filters)
        initial_quality = assess_candidate_quality(
            initial.chunks,
            self.selection_config,
        )
        if not initial_quality.needs_rewrite:
            return AdaptiveRetrievalResult(
                retrieval=initial,
                quality=initial_quality,
                queries=(query,),
            )

        try:
            raw_rewrite = await self.llm_provider.generate(
                ADAPTIVE_REWRITE_SYSTEM_PROMPT,
                build_adaptive_rewrite_prompt(query, history or []),
            )
        except Exception:  # noqa: BLE001
            return AdaptiveRetrievalResult(
                retrieval=initial,
                quality=initial_quality,
                queries=(query,),
                rewrite_error="rewrite_dependency_failed",
            )

        rewrites = parse_adaptive_rewrite(raw_rewrite, original_query=query)
        if not rewrites:
            return AdaptiveRetrievalResult(
                retrieval=initial,
                quality=initial_quality,
                queries=(query,),
                rewrite_error="invalid_rewrite_output",
            )

        queries = (query, *rewrites)
        retrievals = [initial]
        try:
            for rewritten_query in rewrites:
                retrievals.append(await self.retriever.retrieve(rewritten_query, filters))
        except Exception:  # noqa: BLE001
            return AdaptiveRetrievalResult(
                retrieval=initial,
                quality=initial_quality,
                queries=(query,),
                rewrite_error="rewritten_retrieval_failed",
            )
        merged = merge_retrieval_results(queries, retrievals)
        return AdaptiveRetrievalResult(
            retrieval=merged,
            quality=assess_candidate_quality(
                merged.chunks,
                self.selection_config,
            ),
            queries=queries,
            rewrite_used=True,
        )


def parse_adaptive_rewrite(
    output: str,
    original_query: str,
) -> tuple[str, ...]:
    cleaned = _strip_json_fence(output.strip())
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict) or not isinstance(payload.get("queries"), list):
        return ()

    original_key = original_query.strip().casefold()
    seen = {original_key}
    queries: list[str] = []
    for value in payload["queries"]:
        if not isinstance(value, str):
            continue
        query = " ".join(value.split())[:MAX_REWRITE_QUERY_CHARS].strip()
        key = query.casefold()
        if not query or key in seen:
            continue
        seen.add(key)
        queries.append(query)
        if len(queries) >= MAX_REWRITE_QUERIES:
            break
    return tuple(queries)


def merge_retrieval_results(
    queries: tuple[str, ...],
    retrievals: list[RetrievalResult],
) -> RetrievalResult:
    if len(queries) != len(retrievals):
        raise ValueError("queries and retrievals must have the same length")
    ranked_lists = [
        [(chunk.chunk_id, chunk.score) for chunk in result.chunks]
        for result in retrievals
    ]
    unique_count = len(
        {
            chunk.chunk_id
            for result in retrievals
            for chunk in result.chunks
        }
    )
    fused = reciprocal_rank_fusion(ranked_lists, top_k=unique_count)
    occurrences: dict[str, list[tuple[str, Chunk]]] = {}
    for query, result in zip(queries, retrievals, strict=True):
        for chunk in result.chunks:
            occurrences.setdefault(chunk.chunk_id, []).append((query, chunk))

    merged: list[Chunk] = []
    for chunk_id, rrf_score in fused:
        query_chunks = occurrences[chunk_id]
        base = query_chunks[0][1]
        merged.append(
            replace(
                base,
                score=rrf_score,
                retrieval=_merge_signals(query_chunks, rrf_score),
            )
        )
    return RetrievalResult(
        chunks=merged,
        candidate_count=len(merged),
        reranker_used=False,
    )


def _merge_signals(
    query_chunks: list[tuple[str, Chunk]],
    rrf_score: float,
) -> RetrievalSignals:
    dense_scores = [
        chunk.retrieval.dense_score
        for _, chunk in query_chunks
        if chunk.retrieval.dense_score is not None
    ]
    dense_ranks = [
        chunk.retrieval.dense_rank
        for _, chunk in query_chunks
        if chunk.retrieval.dense_rank is not None
    ]
    bm25_scores = [
        chunk.retrieval.bm25_score
        for _, chunk in query_chunks
        if chunk.retrieval.bm25_score is not None
    ]
    bm25_ranks = [
        chunk.retrieval.bm25_rank
        for _, chunk in query_chunks
        if chunk.retrieval.bm25_rank is not None
    ]
    return RetrievalSignals(
        dense_score=max(dense_scores, default=None),
        dense_rank=min(dense_ranks, default=None),
        bm25_score=max(bm25_scores, default=None),
        bm25_rank=min(bm25_ranks, default=None),
        rrf_score=rrf_score,
        matched_queries=tuple(dict.fromkeys(query for query, _ in query_chunks)),
    )


def _strip_json_fence(value: str) -> str:
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return value
