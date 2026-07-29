from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Chunk, RetrievalFilters, chunk_matches_filters


@dataclass(frozen=True)
class SectionExpansion:
    document_id: str
    section_root: str
    chunks: list[Chunk]


def expand_section_chunks(
    anchor_chunks: list[Chunk],
    all_chunks: list[Chunk],
    filters: RetrievalFilters | None = None,
    document_id: str | None = None,
    section_root: str | None = None,
) -> SectionExpansion | None:
    if document_id and section_root:
        chunks = _matching_chunks(all_chunks, document_id, section_root, filters)
        if chunks:
            return SectionExpansion(
                document_id=document_id,
                section_root=section_root,
                chunks=chunks,
            )
        return None

    for anchor in anchor_chunks:
        root = _section_root(anchor)
        if not root:
            continue
        chunks = _matching_chunks(all_chunks, anchor.document_id, root, filters)
        if chunks:
            return SectionExpansion(
                document_id=anchor.document_id,
                section_root=root,
                chunks=chunks,
            )
    return None


def _matching_chunks(
    all_chunks: list[Chunk],
    document_id: str,
    section_root: str,
    filters: RetrievalFilters | None,
) -> list[Chunk]:
    by_id: dict[str, Chunk] = {}
    for chunk in all_chunks:
        if chunk.document_id != document_id or chunk.is_parent:
            continue
        if not chunk_matches_filters(chunk, filters):
            continue
        if _belongs_to_root(chunk, section_root):
            by_id[chunk.chunk_id] = chunk
    return sorted(by_id.values(), key=lambda chunk: chunk.chunk_index)


def _section_root(chunk: Chunk) -> str:
    if chunk.heading_path:
        return chunk.heading_path[0]
    return chunk.section


def _belongs_to_root(chunk: Chunk, section_root: str) -> bool:
    if chunk.heading_path:
        return chunk.heading_path[0] == section_root
    return chunk.section == section_root or chunk.section.startswith(f"{section_root} > ")
