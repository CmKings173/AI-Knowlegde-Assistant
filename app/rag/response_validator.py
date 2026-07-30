from __future__ import annotations

import re

from app.domain.models import Citation

SOURCE_PATTERN = re.compile(r"SOURCE_\d+")
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def valid_citation_ids(citations: list[Citation]) -> set[str]:
    return {citation.citation_id for citation in citations}


def filter_citation_ids(answer: str, citations: list[Citation]) -> set[str]:
    allowed = valid_citation_ids(citations)
    return {
        match.group(0)
        for match in SOURCE_PATTERN.finditer(answer)
        if match.group(0) in allowed
    }


def citation_ids_in_answer(answer: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in SOURCE_PATTERN.finditer(answer):
        citation_id = match.group(0)
        if citation_id not in seen:
            seen.add(citation_id)
            ordered.append(citation_id)
    return ordered


def remove_unknown_citations(answer: str, citations: list[Citation]) -> str:
    allowed = valid_citation_ids(citations)

    def replace(match: re.Match[str]) -> str:
        citation_id = match.group(0)
        return citation_id if citation_id in allowed else ""

    return SOURCE_PATTERN.sub(replace, answer)


def has_refusal_text(answer: str) -> bool:
    lowered = answer.lower()
    return (
        "tôi chưa tìm thấy thông tin này trong tài liệu nội bộ hiện có" in lowered
        or "câu hỏi này nằm ngoài phạm vi kho kiến thức nội bộ hiện có" in lowered
        or "không có nguồn phù hợp trong context" in lowered
    )


def contains_disallowed_cjk(text: str, max_chars: int = 0) -> bool:
    return len(CJK_PATTERN.findall(text)) > max_chars


def should_refuse(candidate_count: int, best_score: float, min_score: float) -> bool:
    return candidate_count == 0 or best_score < min_score
