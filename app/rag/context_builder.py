from __future__ import annotations

from app.domain.models import Chunk
from app.utils.text import estimate_tokens


def build_context(chunks: list[Chunk], max_tokens: int) -> tuple[str, list[Chunk]]:
    blocks: list[str] = []
    selected: list[Chunk] = []
    used_ids: set[str] = set()
    used_tokens = 0

    for index, chunk in enumerate(chunks, start=1):
        if chunk.chunk_id in used_ids:
            continue
        block = (
            f"[SOURCE_{index}]\n"
            f"Tài liệu: {chunk.document_name}\n"
            f"Mục: {chunk.section}\n"
            f"Nội dung:\n{chunk.content}"
        )
        block_tokens = estimate_tokens(block)
        if selected and used_tokens + block_tokens > max_tokens:
            break
        blocks.append(block)
        selected.append(chunk)
        used_ids.add(chunk.chunk_id)
        used_tokens += block_tokens
    return "\n\n---\n\n".join(blocks), selected

