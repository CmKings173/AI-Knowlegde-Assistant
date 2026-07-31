from __future__ import annotations

from dataclasses import replace

from app.config import Settings
from app.domain.models import (
    Chunk,
    RetrievalFilters,
    RetrievalResult,
    RetrievalSignals,
    filters_select_no_documents,
)
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.vector_store.base import VectorStore
from app.rag.hybrid_search import reciprocal_rank_fusion
from app.rag.lexical import LexicalIndex


class Retriever:
    def __init__(
        self,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.lexical_index = LexicalIndex()
        self._loaded = False

    async def reload(self) -> None:
        chunks = await self.vector_store.list_chunks()
        self.lexical_index.build(chunks)
        self._loaded = True

    async def all_chunks(self) -> list[Chunk]:
        if not self._loaded:
            await self.reload()
        return list(self.lexical_index.chunks)

    async def document_chunks(self, document_id: str) -> list[Chunk]:
        chunks = await self.vector_store.list_document_chunks(document_id)
        if chunks:
            return chunks
        return [chunk for chunk in await self.all_chunks() if chunk.document_id == document_id]

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        if filters_select_no_documents(filters):
            return RetrievalResult(chunks=[], candidate_count=0, reranker_used=False)
        if not self._loaded:
            await self.reload()
        query_vector = (await self.embedding_provider.embed_texts([query]))[0]
        dense = await self.vector_store.search(query_vector, self.settings.dense_top_k, filters)
        lexical = self.lexical_index.search(query, self.settings.lexical_top_k, filters)
        dense_by_id = {
            chunk.chunk_id: (rank, chunk.score)
            for rank, chunk in enumerate(dense, start=1)
        }
        lexical_by_id = {
            chunk.chunk_id: (rank, chunk.score)
            for rank, chunk in enumerate(lexical, start=1)
        }
        by_id: dict[str, Chunk] = {
            chunk.chunk_id: chunk for chunk in [*lexical, *dense]
        }
        fused = reciprocal_rank_fusion(
            [
                [(chunk.chunk_id, chunk.score) for chunk in dense],
                [(chunk.chunk_id, chunk.score) for chunk in lexical],
            ],
            top_k=self.settings.fusion_top_k,
        )
        ranked: list[Chunk] = []
        for chunk_id, score in fused:
            chunk = by_id[chunk_id]
            dense_signal = dense_by_id.get(chunk_id)
            lexical_signal = lexical_by_id.get(chunk_id)
            ranked.append(
                replace(
                    chunk,
                    score=score,
                    retrieval=RetrievalSignals(
                        dense_score=dense_signal[1] if dense_signal else None,
                        dense_rank=dense_signal[0] if dense_signal else None,
                        bm25_score=lexical_signal[1] if lexical_signal else None,
                        bm25_rank=lexical_signal[0] if lexical_signal else None,
                        rrf_score=score,
                        matched_queries=("original",),
                    ),
                )
            )
        return RetrievalResult(chunks=ranked, candidate_count=len(ranked), reranker_used=False)
