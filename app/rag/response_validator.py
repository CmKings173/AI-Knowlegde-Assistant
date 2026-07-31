from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models import Citation

SOURCE_PATTERN = re.compile(r"SOURCE_\d+")
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
TIME_PATTERN = re.compile(
    r"(?<!\d)([01]?\d|2[0-3])\s*(?:h\s*:?\s*([0-5]?\d)?|:\s*([0-5]\d))(?!\d)",
    re.IGNORECASE,
)
IP_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
PORT_PATTERN = re.compile(r"\b(?:port|cổng|cong)\s*[:=]?\s*(\d{2,5})\b", re.IGNORECASE)


@dataclass(frozen=True)
class CriticalLiteralValidation:
    passed: bool
    unsupported: tuple[str, ...] = ()


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


def validate_critical_literals(
    answer: str,
    cited_context: str,
) -> CriticalLiteralValidation:
    answer_literals = _critical_literals(answer)
    context_literals = _critical_literals(cited_context)
    unsupported = tuple(sorted(answer_literals - context_literals))
    return CriticalLiteralValidation(
        passed=not unsupported,
        unsupported=unsupported,
    )


def should_refuse(candidate_count: int, best_score: float, min_score: float) -> bool:
    return candidate_count == 0 or best_score < min_score


def _critical_literals(text: str) -> set[str]:
    literals = {
        f"time:{_normalized_time(match)}"
        for match in TIME_PATTERN.finditer(text)
    }
    literals.update(
        f"ip:{value}"
        for value in IP_PATTERN.findall(text)
        if _valid_ip(value)
    )
    literals.update(
        f"port:{match.group(1)}"
        for match in PORT_PATTERN.finditer(text)
        if 0 < int(match.group(1)) <= 65535
    )
    return literals


def _normalized_time(match: re.Match[str]) -> str:
    hour = int(match.group(1))
    minute = int(match.group(2) or match.group(3) or "0")
    return f"{hour:02d}:{minute:02d}"


def _valid_ip(value: str) -> bool:
    return all(0 <= int(part) <= 255 for part in value.split("."))
