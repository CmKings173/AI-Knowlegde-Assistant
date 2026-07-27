from __future__ import annotations

import re

from app.domain.models import Citation

SOURCE_PATTERN = re.compile(r"SOURCE_\d+")


def valid_citation_ids(citations: list[Citation]) -> set[str]:
    return {citation.citation_id for citation in citations}


def filter_citation_ids(answer: str, citations: list[Citation]) -> set[str]:
    allowed = valid_citation_ids(citations)
    return {
        match.group(0)
        for match in SOURCE_PATTERN.finditer(answer)
        if match.group(0) in allowed
    }


def remove_unknown_citations(answer: str, citations: list[Citation]) -> str:
    allowed = valid_citation_ids(citations)

    def replace(match: re.Match[str]) -> str:
        citation_id = match.group(0)
        return citation_id if citation_id in allowed else ""

    return SOURCE_PATTERN.sub(replace, answer)


def has_refusal_text(answer: str) -> bool:
    lowered = answer.lower()
    return "tôi chưa tìm thấy thông tin" in lowered or "không phải câu hỏi liên quan" in lowered


def should_refuse(candidate_count: int, best_score: float, min_score: float) -> bool:
    return candidate_count == 0 or best_score < min_score
