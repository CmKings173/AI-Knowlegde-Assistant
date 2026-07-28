from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import KnowledgeType
from app.domain.models import RetrievalFilters


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str


class ChatFilters(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    knowledge_types: list[KnowledgeType] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    language: str | None = None
    include_parent_chunks: bool | None = None

    def to_retrieval_filters(self) -> RetrievalFilters:
        return RetrievalFilters(
            document_ids=self.document_ids,
            knowledge_types=self.knowledge_types,
            domains=self.domains,
            language=self.language,
            include_parent_chunks=self.include_parent_chunks,
        )


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    filters: ChatFilters | None = None

    def retrieval_filters(self) -> RetrievalFilters | None:
        if self.filters is None:
            return None
        return self.filters.to_retrieval_filters()


class CitationResponse(BaseModel):
    citation_id: str
    document_name: str
    section: str
    chunk_id: str
    excerpt: str
    images: list[dict[str, str]] = []


class RetrievalMeta(BaseModel):
    candidate_count: int
    context_count: int
    reranker_used: bool


ResponseStatus = Literal[
    "answered",
    "partial",
    "insufficient_context",
    "out_of_scope",
    "conflict",
]


class ChatResponse(BaseModel):
    status: ResponseStatus
    answer: str
    citations: list[CitationResponse]
    retrieval: RetrievalMeta
    timing_ms: dict[str, int]


class DocumentResponse(BaseModel):
    document_id: str
    original_name: str
    file_name: str
    stored_name: str
    file_hash: str
    status: str
    chunk_count: int
    parent_chunks: int
    child_chunks: int
    image_count: int
    vector_index_status: str
    created_at: str
    updated_at: str
    uploaded_at: str
    source_path: str


class DocumentsResponse(BaseModel):
    documents: list[DocumentResponse]
