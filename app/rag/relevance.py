from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.models import Chunk
from app.utils.text import normalize_for_intent

MIN_IMPORTANT_TERM_COVERAGE = 0.6
MIN_IMPORTANT_TERMS = 2

EVIDENCE_GATE_QUERY_TERMS = (
    "chinh sach",
    "duoc phep",
    "phe duyet",
    "quy dinh",
    "quy trinh",
    "thu tuc",
    "xin",
    "xin phep",
)

STOP_TERMS = {
    "anh",
    "ban",
    "cach",
    "can",
    "chi",
    "cho",
    "cong",
    "cong ty",
    "cua",
    "duoc",
    "em",
    "gi",
    "dan",
    "dinh",
    "han",
    "huong dan",
    "lam",
    "lam sao",
    "minh",
    "muon",
    "nao",
    "noi",
    "noi bo",
    "phai",
    "quy",
    "quy dinh",
    "quy trinh",
    "sao",
    "thi",
    "the nao",
    "nhu",
    "trinh",
    "tuc",
    "thu",
    "thu tuc",
    "toi",
    "ve",
}


@dataclass(frozen=True)
class RelevanceDecision:
    passed: bool
    reason: str | None = None
    important_terms: set[str] = field(default_factory=set)
    matched_terms: set[str] = field(default_factory=set)
    coverage: float = 1.0


def validate_context_relevance(query: str, chunks: list[Chunk]) -> RelevanceDecision:
    if not should_apply_evidence_gate(query):
        return RelevanceDecision(passed=True)
    important_terms = _important_terms(query)
    if len(important_terms) < MIN_IMPORTANT_TERMS:
        return RelevanceDecision(passed=True, important_terms=important_terms)
    context = normalize_for_intent(
        " ".join(f"{chunk.section} {chunk.content}" for chunk in chunks)
    )
    matched_terms = {term for term in important_terms if _contains_term(context, term)}
    coverage = len(matched_terms) / len(important_terms)
    if coverage < MIN_IMPORTANT_TERM_COVERAGE:
        return RelevanceDecision(
            passed=False,
            reason="insufficient_query_term_coverage",
            important_terms=important_terms,
            matched_terms=matched_terms,
            coverage=coverage,
        )
    return RelevanceDecision(
        passed=True,
        important_terms=important_terms,
        matched_terms=matched_terms,
        coverage=coverage,
    )


def should_apply_evidence_gate(query: str) -> bool:
    normalized = normalize_for_intent(query)
    return any(_contains_term(normalized, term) for term in EVIDENCE_GATE_QUERY_TERMS)


def _important_terms(query: str) -> set[str]:
    normalized = normalize_for_intent(query)
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) >= 3 and token not in STOP_TERMS
    }
    phrases = {
        phrase
        for phrase in _candidate_phrases(normalized)
        if phrase not in STOP_TERMS and not all(token in STOP_TERMS for token in phrase.split())
    }
    return tokens | phrases


def _candidate_phrases(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text)
    phrases: set[str] = set()
    for index in range(0, max(0, len(words) - 1)):
        first, second = words[index], words[index + 1]
        if first in STOP_TERMS:
            continue
        phrase = f"{first} {second}"
        if len(phrase) >= 5:
            phrases.add(phrase)
    return phrases


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None
