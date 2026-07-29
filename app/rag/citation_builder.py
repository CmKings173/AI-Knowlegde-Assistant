from __future__ import annotations

from app.domain.models import Chunk, Citation, CitationBlock
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
        images = [
            image_lookup[image_id]
            for image_id in chunk.image_ids
            if image_id in image_lookup
        ]
        citations.append(
            Citation(
                citation_id=f"SOURCE_{index}",
                document_name=chunk.document_name,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                excerpt=excerpt(chunk.content),
                images=images,
                content=chunk.content,
                content_blocks=_content_blocks(chunk.content, images),
            )
        )
    return citations


def _content_blocks(content: str, images: list[dict[str, str]]) -> list[CitationBlock]:
    paragraphs = [paragraph.strip() for paragraph in content.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        paragraphs = [content.strip()] if content.strip() else []
    block_images: list[list[dict[str, str]]] = [[] for _ in paragraphs]
    fallback_images: list[dict[str, str]] = []
    for image in images:
        anchor = image.get("anchor_text", "").strip()
        target_index = _find_anchor_block(anchor, paragraphs) if anchor else None
        if target_index is None:
            fallback_images.append(image)
        else:
            block_images[target_index].append(image)
    if fallback_images:
        block_images.append(fallback_images)
        paragraphs.append("")
    return [
        CitationBlock(text=paragraph, images=images_for_block)
        for paragraph, images_for_block in zip(paragraphs, block_images, strict=False)
    ]


def _find_anchor_block(anchor: str, paragraphs: list[str]) -> int | None:
    normalized_anchor = anchor.lower()
    for index, paragraph in enumerate(paragraphs):
        if normalized_anchor and normalized_anchor in paragraph.lower():
            return index
    return None
