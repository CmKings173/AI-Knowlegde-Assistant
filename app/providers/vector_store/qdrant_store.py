from __future__ import annotations

import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.config import Settings
from app.domain.exceptions import VectorStoreError
from app.domain.models import Chunk
from app.providers.vector_store.base import VectorStore


class QdrantVectorStore(VectorStore):
    def __init__(self, settings: Settings) -> None:
        self.collection = settings.qdrant_collection
        self.client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)

    async def ensure_collection(self, vector_size: int) -> None:
        if await self._collection_exists():
            return
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    async def _collection_exists(self) -> bool:
        try:
            collections = await self.client.get_collections()
        except Exception:  # noqa: BLE001
            return False
        return any(item.name == self.collection for item in collections.collections)

    async def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise VectorStoreError("Chunk and vector counts do not match")
        if not chunks:
            return
        await self.ensure_collection(len(vectors[0]))
        points = [
            models.PointStruct(
                id=str(uuid.UUID(chunk.chunk_id)),
                vector=vector,
                payload=chunk.payload(),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self.client.upsert(collection_name=self.collection, points=points)

    async def search(self, vector: list[float], top_k: int) -> list[Chunk]:
        if not await self._collection_exists():
            return []
        results = await self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            Chunk.from_payload(dict(point.payload or {}), score=float(point.score))
            for point in results
        ]

    async def delete_document(self, document_id: str) -> None:
        if not await self._collection_exists():
            return
        await self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    async def list_chunks(self, limit: int = 10_000) -> list[Chunk]:
        chunks: list[Chunk] = []
        if not await self._collection_exists():
            return chunks
        offset = None
        while len(chunks) < limit:
            records, offset = await self.client.scroll(
                collection_name=self.collection,
                limit=min(256, limit - len(chunks)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(Chunk.from_payload(dict(record.payload or {})) for record in records)
            if offset is None:
                break
        return chunks
