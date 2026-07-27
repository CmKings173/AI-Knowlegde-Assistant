from __future__ import annotations

from app.config import Settings
from app.domain.models import Chunk, RetrievalResult
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

    async def retrieve(self, query: str) -> RetrievalResult:
        if not self._loaded:
            await self.reload()
        query_vector = (await self.embedding_provider.embed_texts([query]))[0]
        dense = await self.vector_store.search(query_vector, self.settings.dense_top_k)
        lexical = self.lexical_index.search(query, self.settings.lexical_top_k)
        by_id: dict[str, Chunk] = {chunk.chunk_id: chunk for chunk in [*dense, *lexical]}
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
            chunk.score = score
            ranked.append(chunk)
        return RetrievalResult(chunks=ranked, candidate_count=len(ranked), reranker_used=False)

