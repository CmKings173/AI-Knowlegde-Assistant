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
    document_scope: Literal["all", "selected"] = "all"

    def to_retrieval_filters(self) -> RetrievalFilters:
        return RetrievalFilters(
            document_ids=self.document_ids,
            knowledge_types=self.knowledge_types,
            domains=self.domains,
            language=self.language,
            include_parent_chunks=self.include_parent_chunks,
            document_scope=self.document_scope,
        )


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatContinuation(BaseModel):
    mode: Literal["broad_section"]
    document_id: str = Field(min_length=1, max_length=200)
    section_root: str = Field(min_length=1, max_length=500)
    next_offset: int = Field(ge=0)
    source_question: str = Field(min_length=1, max_length=2000)
    token: str = Field(min_length=32, max_length=200)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryMessage] = Field(default_factory=list)
    continuation: ChatContinuation | None = None
    filters: ChatFilters | None = None

    def retrieval_filters(self) -> RetrievalFilters | None:
        if self.filters is None:
            return None
        return self.filters.to_retrieval_filters()

    def sanitized_history(self, max_messages: int, max_chars: int) -> list[dict[str, str]]:
        selected = self.history[-max_messages:]
        remaining_chars = max_chars
        sanitized: list[dict[str, str]] = []
        for message in reversed(selected):
            content = message.content.strip()
            if not content or remaining_chars <= 0:
                continue
            content = content[-remaining_chars:]
            remaining_chars -= len(content)
            sanitized.append({"role": message.role, "content": content})
        return list(reversed(sanitized))


class CitationBlockResponse(BaseModel):
    text: str
    images: list[dict[str, str]] = []


class CitationResponse(BaseModel):
    citation_id: str
    document_name: str
    section: str
    chunk_id: str
    excerpt: str
    images: list[dict[str, str]] = []
    content: str = ""
    content_blocks: list[CitationBlockResponse] = []


class RetrievalMeta(BaseModel):
    candidate_count: int
    context_count: int
    reranker_used: bool


class RouteTrace(BaseModel):
    intent: str | None = None
    subtype: str | None = None
    confidence: float | None = None
    reason: str | None = None
    branch: str | None = None
    candidate_count: int | None = None
    context_count: int | None = None
    best_score: float | None = None
    parse_error: str | None = None
    literal_validation_error: str | None = None
    # Deprecated compatibility field. RAG V2 no longer runs the heuristic fact guard.
    fact_guard_error: str | None = None
    rewrite_used: bool = False
    llm_router_used: bool = False
    retrieval_first: bool = False
    adaptive_rewrite_used: bool = False
    adaptive_rewrite_error: str | None = None
    retrieval_queries: list[str] = []
    candidate_quality: str | None = None
    selected_chunk_ids: list[str] = []
    rejected_chunks: dict[str, str] = {}


class ContinuationResponse(BaseModel):
    has_more: bool
    mode: Literal["broad_section"]
    document_id: str
    section_root: str
    next_offset: int
    source_question: str
    token: str


ResponseStatus = Literal[
    "answered",
    "partial",
    "insufficient_context",
    "out_of_scope",
    "conversational",
    "clarify",
    "generation_failed",
    "conflict",
]


class ChatResponse(BaseModel):
    status: ResponseStatus
    answer: str
    citations: list[CitationResponse]
    retrieval: RetrievalMeta
    timing_ms: dict[str, int]
    continuation: ContinuationResponse | None = None
    trace: RouteTrace | None = None


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
