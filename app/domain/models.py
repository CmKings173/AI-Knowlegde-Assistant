from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.domain.enums import KnowledgeType


@dataclass(frozen=True)
class ParsedElement:
    text: str
    style: str = ""
    level: int | None = None
    is_bullet: bool = False
    is_numbered: bool = False
    image_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentInfo:
    document_id: str
    document_name: str
    source_path: Path
    file_hash: str


@dataclass(frozen=True)
class ImageAsset:
    image_id: str
    file_name: str
    stored_path: str
    content_type: str
    section: str = ""
    anchor_text: str = ""


@dataclass
class Chunk:
    chunk_id: str
    parent_id: str | None
    document_id: str
    document_name: str
    document_version: str
    knowledge_type: KnowledgeType
    domain: str
    section: str
    heading_path: list[str]
    chunk_index: int
    content: str
    source_path: str
    content_hash: str
    image_ids: list[str] = field(default_factory=list)
    language: str = "vi"
    is_parent: bool = False
    score: float = 0.0

    def payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "document_version": self.document_version,
            "knowledge_type": self.knowledge_type.value,
            "domain": self.domain,
            "section": self.section,
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "source_path": self.source_path,
            "content_hash": self.content_hash,
            "image_ids": self.image_ids,
            "language": self.language,
            "is_parent": self.is_parent,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any], score: float = 0.0) -> Chunk:
        return cls(
            chunk_id=payload["chunk_id"],
            parent_id=payload.get("parent_id"),
            document_id=payload["document_id"],
            document_name=payload["document_name"],
            document_version=payload["document_version"],
            knowledge_type=KnowledgeType(payload["knowledge_type"]),
            domain=payload.get("domain", "general"),
            section=payload.get("section", ""),
            heading_path=list(payload.get("heading_path", [])),
            chunk_index=int(payload.get("chunk_index", 0)),
            content=payload["content"],
            source_path=payload.get("source_path", ""),
            content_hash=payload["content_hash"],
            image_ids=list(payload.get("image_ids", [])),
            language=payload.get("language", "vi"),
            is_parent=bool(payload.get("is_parent", False)),
            score=score,
        )


@dataclass(frozen=True)
class CitationBlock:
    text: str
    images: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Citation:
    citation_id: str
    document_name: str
    section: str
    chunk_id: str
    excerpt: str
    images: list[dict[str, str]] = field(default_factory=list)
    content: str = ""
    content_blocks: list[CitationBlock] = field(default_factory=list)


@dataclass
class RetrievalResult:
    chunks: list[Chunk] = field(default_factory=list)
    candidate_count: int = 0
    reranker_used: bool = False


@dataclass(frozen=True)
class RetrievalFilters:
    document_ids: list[str] = field(default_factory=list)
    knowledge_types: list[KnowledgeType] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    language: str | None = None
    include_parent_chunks: bool | None = None
    document_scope: Literal["all", "selected"] = "all"


def chunk_matches_filters(chunk: Chunk, filters: RetrievalFilters | None) -> bool:
    if filters is None:
        return True
    if filters_select_no_documents(filters):
        return False
    if filters.document_ids and chunk.document_id not in filters.document_ids:
        return False
    if filters.knowledge_types and chunk.knowledge_type not in filters.knowledge_types:
        return False
    if filters.domains and chunk.domain not in filters.domains:
        return False
    if filters.language and chunk.language != filters.language:
        return False
    if filters.include_parent_chunks is False and chunk.is_parent:
        return False
    return True


def filters_select_no_documents(filters: RetrievalFilters | None) -> bool:
    return bool(filters and filters.document_scope == "selected" and not filters.document_ids)
