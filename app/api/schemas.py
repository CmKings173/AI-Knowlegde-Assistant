from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


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


class ChatResponse(BaseModel):
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
