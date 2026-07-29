from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.domain.models import Chunk, DocumentInfo, ParsedElement
from app.ingestion.classifier import classify_knowledge_type, infer_domain
from app.ingestion.cleaner import clean_text
from app.utils.hashing import sha256_text
from app.utils.text import estimate_tokens


@dataclass(frozen=True)
class ChunkingConfig:
    target_tokens: int = 350
    max_tokens: int = 550
    overlap_tokens: int = 40
    parent_max_tokens: int = 1200


@dataclass
class Section:
    heading_path: list[str]
    lines: list[str]
    image_ids: list[str] = field(default_factory=list)
    line_image_ids: list[list[str]] = field(default_factory=list)


def detect_heading(text: str, style: str = "", level: int | None = None) -> tuple[int, str] | None:
    clean = clean_text(text)
    if not clean:
        return None
    if level:
        return level, clean
    style_lower = style.lower()
    match = re.search(r"heading\s*(\d+)", style_lower)
    if match:
        return int(match.group(1)), clean
    if re.match(r"^phần\s+[ivxlcdm\d]+[:.\-\s]", clean, re.IGNORECASE):
        return 1, clean
    if re.match(r"^điều\s+\d+[:.\-\s]", clean, re.IGNORECASE):
        return 2, clean
    if re.match(r"^\d+(\.\d+){0,3}[.)]?\s+\S", clean):
        return min(clean.count(".") + 1, 4), clean
    return None


def elements_to_sections(elements: list[ParsedElement]) -> list[Section]:
    headings: list[str] = []
    sections: list[Section] = []
    current = Section(heading_path=["T\u00e0i li\u1ec7u"], lines=[])

    for element in elements:
        text = clean_text(element.text)
        if not text or text == "[IMAGE]":
            if element.image_ids:
                if current.line_image_ids:
                    current.line_image_ids[-1].extend(element.image_ids)
                else:
                    current.image_ids.extend(element.image_ids)
            continue
        heading = detect_heading(text, element.style, element.level)
        if heading:
            if current.lines:
                sections.append(current)
            level, title = heading
            headings = headings[: max(0, level - 1)]
            headings.append(title)
            current = Section(heading_path=headings.copy(), lines=[])
            continue
        current.lines.append(text)
        current.line_image_ids.append(list(element.image_ids))
        current.image_ids.extend(element.image_ids)

    if current.lines or current.image_ids:
        sections.append(current)
    return sections


def chunk_document(
    document: DocumentInfo,
    elements: list[ParsedElement],
    config: ChunkingConfig,
) -> list[Chunk]:
    sections = elements_to_sections(elements)
    chunks: list[Chunk] = []
    child_index = 0
    for section in sections:
        parent_content = _format_content(section.heading_path, section.lines)
        parent_id = _chunk_id(document.document_id, parent_content, "parent")
        parent_chunk = _build_chunk(
            document=document,
            chunk_id=parent_id,
            parent_id=None,
            section=section,
            content=parent_content,
            chunk_index=child_index,
            is_parent=True,
            image_ids=section.image_ids,
        )
        chunks.append(parent_chunk)
        child_index += 1

        for child_lines, child_image_ids in _split_section(section, config.max_tokens):
            child_content = _format_content(section.heading_path, child_lines)
            chunks.append(
                _build_chunk(
                    document=document,
                    chunk_id=_chunk_id(document.document_id, child_content, "child"),
                    parent_id=parent_id,
                    section=section,
                    content=child_content,
                    chunk_index=child_index,
                    is_parent=False,
                    image_ids=child_image_ids,
                )
            )
            child_index += 1
    return chunks


def _split_lines(lines: list[str], max_tokens: int) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for line in lines:
        line_tokens = estimate_tokens(line)
        if current and current_tokens + line_tokens > max_tokens:
            groups.append(current)
            current = [line]
            current_tokens = line_tokens
        else:
            current.append(line)
            current_tokens += line_tokens
    if current:
        groups.append(current)
    return groups


def _split_section(section: Section, max_tokens: int) -> list[tuple[list[str], list[str]]]:
    groups: list[tuple[list[str], list[str]]] = []
    current_lines: list[str] = []
    current_images: list[str] = []
    current_tokens = 0
    for index, line in enumerate(section.lines):
        line_tokens = estimate_tokens(line)
        line_images = section.line_image_ids[index] if index < len(section.line_image_ids) else []
        if current_lines and current_tokens + line_tokens > max_tokens:
            groups.append((current_lines, current_images))
            current_lines = [line]
            current_images = list(line_images)
            current_tokens = line_tokens
        else:
            current_lines.append(line)
            current_images.extend(line_images)
            current_tokens += line_tokens
    if current_lines:
        groups.append((current_lines, current_images))
    return groups


def _format_content(heading_path: list[str], lines: list[str]) -> str:
    heading = " > ".join(heading_path)
    body = "\n".join(lines)
    return clean_text(f"{heading}\n\n{body}")


def _build_chunk(
    document: DocumentInfo,
    chunk_id: str,
    parent_id: str | None,
    section: Section,
    content: str,
    chunk_index: int,
    is_parent: bool,
    image_ids: list[str] | None = None,
) -> Chunk:
    knowledge_type = classify_knowledge_type(content, section.heading_path)
    return Chunk(
        chunk_id=chunk_id,
        parent_id=parent_id,
        document_id=document.document_id,
        document_name=document.document_name,
        document_version=document.file_hash,
        knowledge_type=knowledge_type,
        domain=infer_domain(content, section.heading_path),
        section=" > ".join(section.heading_path),
        heading_path=section.heading_path,
        chunk_index=chunk_index,
        content=content,
        source_path=str(document.source_path),
        content_hash=sha256_text(content),
        image_ids=image_ids or [],
        is_parent=is_parent,
    )


def _chunk_id(document_id: str, content: str, role: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{role}:{sha256_text(content)}"))
