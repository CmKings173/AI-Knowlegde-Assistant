from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.utils.text import normalize_for_intent

DAY_ALIASES: dict[str, tuple[str, ...]] = {
    "MON": ("thu 2", "thu hai", "t2", "th2"),
    "TUE": ("thu 3", "thu ba", "t3", "th3"),
    "WED": ("thu 4", "thu tu", "t4", "th4"),
    "THU": ("thu 5", "thu nam", "t5", "th5"),
    "FRI": ("thu 6", "thu sau", "t6", "th6"),
    "SAT": ("thu 7", "thu bay", "t7", "th7"),
    "SUN": ("chu nhat", "cn"),
}

TIME_PATTERN = re.compile(
    r"(?<!\d)(\d{1,2})\s*(?:h|:|gio)\s*(\d{1,2})?(?:\s*(sang|chieu|toi))?",
    re.IGNORECASE,
)
SUPPORT_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "NAS_MOBILE": (
        "app mobile",
        "mobile",
        "ung dung di dong",
        "dien thoai",
        "thiet bi di dong",
        "appstore",
        "ch play",
        "webaccess",
    ),
    "NAS_INTERNAL_NETWORK": (
        "mang noi bo",
        "wifi tai cong ty",
        "windows r",
        "\\\\10.10.10.200",
    ),
}


@dataclass(frozen=True)
class ExtractedFacts:
    days: set[str] = field(default_factory=set)
    times: set[str] = field(default_factory=set)
    support_terms: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class FactValidationResult:
    passed: bool
    reason: str | None = None
    answer_facts: ExtractedFacts = field(default_factory=ExtractedFacts)
    context_facts: ExtractedFacts = field(default_factory=ExtractedFacts)


def extract_facts(text: str) -> ExtractedFacts:
    normalized = normalize_for_intent(text)
    return ExtractedFacts(
        days=_extract_days(normalized),
        times=_extract_times(normalized),
        support_terms=_extract_support_terms(normalized),
    )


def validate_fact_consistency(answer: str, cited_context: str) -> FactValidationResult:
    answer_facts = extract_facts(answer)
    context_facts = extract_facts(cited_context)
    extra_days = answer_facts.days - context_facts.days
    if extra_days:
        return FactValidationResult(
            passed=False,
            reason=f"unsupported_day:{','.join(sorted(extra_days))}",
            answer_facts=answer_facts,
            context_facts=context_facts,
        )
    extra_times = answer_facts.times - context_facts.times
    if extra_times:
        return FactValidationResult(
            passed=False,
            reason=f"unsupported_time:{','.join(sorted(extra_times))}",
            answer_facts=answer_facts,
            context_facts=context_facts,
        )
    extra_support_terms = answer_facts.support_terms - context_facts.support_terms
    if extra_support_terms:
        return FactValidationResult(
            passed=False,
            reason=f"unsupported_support_term:{','.join(sorted(extra_support_terms))}",
            answer_facts=answer_facts,
            context_facts=context_facts,
        )
    return FactValidationResult(
        passed=True,
        answer_facts=answer_facts,
        context_facts=context_facts,
    )


def describe_fact_guard_retry_error(result: FactValidationResult) -> str:
    answer_days = ", ".join(sorted(result.answer_facts.days)) or "none"
    context_days = ", ".join(sorted(result.context_facts.days)) or "none"
    answer_times = ", ".join(sorted(result.answer_facts.times)) or "none"
    context_times = ", ".join(sorted(result.context_facts.times)) or "none"
    answer_support_terms = ", ".join(sorted(result.answer_facts.support_terms)) or "none"
    context_support_terms = ", ".join(sorted(result.context_facts.support_terms)) or "none"
    return (
        f"fact_guard_failed:{result.reason}; "
        f"answer_days={answer_days}; context_days={context_days}; "
        f"answer_times={answer_times}; context_times={context_times}; "
        f"answer_support_terms={answer_support_terms}; "
        f"context_support_terms={context_support_terms}"
    )


def _extract_days(text: str) -> set[str]:
    found: set[str] = set()
    for code, aliases in DAY_ALIASES.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            found.add(code)
    return found


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) is not None


def _extract_times(text: str) -> set[str]:
    times: set[str] = set()
    for match in TIME_PATTERN.finditer(text):
        hour = int(match.group(1))
        minute = int(match.group(2) or "0")
        period = match.group(3)
        if hour > 23 or minute > 59:
            continue
        if period in {"chieu", "toi"} and 1 <= hour <= 11:
            hour += 12
        times.add(f"{hour:02d}:{minute:02d}")
    return times


def _extract_support_terms(text: str) -> set[str]:
    found: set[str] = set()
    for code, aliases in SUPPORT_TERM_ALIASES.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            found.add(code)
    return found
