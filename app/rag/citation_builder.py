from __future__ import annotations

from app.domain.models import Chunk, Citation
from app.utils.text import excerpt


def build_citations(
    chunks: list[Chunk],
    image_lookup: dict[str, dict[str, str]] | None = None,
) -> list[Citation]:
    image_lookup = image_lookup or {}
    citations: list[Citation] = []
    seen: set[str] = set()
    for index, chunk in enumerate(chunks, start=1):
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        citations.append(
            Citation(
                citation_id=f"SOURCE_{index}",
                document_name=chunk.document_name,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                excerpt=excerpt(chunk.content),
                images=[
                    image_lookup[image_id]
                    for image_id in chunk.image_ids
                    if image_id in image_lookup
                ],
            )
        )
    return citations
