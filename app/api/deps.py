from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.documents.manifest import ManifestStore
from app.ingestion.pipeline import IngestionPipeline
from app.providers.embeddings.api_provider import create_embedding_provider
from app.providers.llm.factory import create_llm_provider
from app.providers.vector_store.qdrant_store import QdrantVectorStore
from app.rag.pipeline import RAGPipeline
from app.rag.retriever import Retriever


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(get_settings())


@lru_cache
def get_embedding_provider():
    return create_embedding_provider(get_settings())


@lru_cache
def get_manifest_store() -> ManifestStore:
    settings = get_settings()
    return ManifestStore(settings.processed_dir, settings.documents_dir)


@lru_cache
def get_retriever() -> Retriever:
    settings = get_settings()
    return Retriever(settings, get_embedding_provider(), get_vector_store())


@lru_cache
def get_rag_pipeline() -> RAGPipeline:
    settings = get_settings()
    return RAGPipeline(settings, get_retriever(), create_llm_provider(settings))


def get_ingestion_pipeline() -> IngestionPipeline:
    settings: Settings = get_settings()
    return IngestionPipeline(
        settings,
        get_embedding_provider(),
        get_vector_store(),
        get_manifest_store(),
    )
