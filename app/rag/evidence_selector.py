from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.domain.models import Chunk

GENERAL_DOMAINS = {"", "GENERAL"}


@dataclass(frozen=True)
class EvidenceSelectionConfig:
    min_dense_score: float
    min_bm25_score: float
    coherent_domain_min_chunks: int = 2


@dataclass(frozen=True)
class CandidateQuality:
    needs_rewrite: bool
    reason: str
    coherent_domain: str | None = None
    strong_candidate_count: int = 0


@dataclass(frozen=True)
class RejectedEvidence:
    chunk: Chunk
    reason: str


@dataclass
class EvidenceSelectionResult:
    selected: list[Chunk] = field(default_factory=list)
    rejected: list[RejectedEvidence] = field(default_factory=list)
    quality: CandidateQuality = field(
        default_factory=lambda: CandidateQuality(True, "no_candidates")
    )


def assess_candidate_quality(
    candidates: list[Chunk],
    config: EvidenceSelectionConfig,
) -> CandidateQuality:
    strong = [chunk for chunk in candidates if _is_strong(chunk, config)]
    if not strong:
        return CandidateQuality(
            needs_rewrite=True,
            reason="weak_evidence",
            strong_candidate_count=0,
        )

    domain_counts = Counter(
        chunk.domain.upper()
        for chunk in strong
        if chunk.domain.upper() not in GENERAL_DOMAINS
    )
    coherent_domain = _coherent_domain(domain_counts, config.coherent_domain_min_chunks)
    if coherent_domain:
        return CandidateQuality(
            needs_rewrite=False,
            reason="coherent_evidence",
            coherent_domain=coherent_domain,
            strong_candidate_count=len(strong),
        )
    if len(domain_counts) > 1:
        return CandidateQuality(
            needs_rewrite=True,
            reason="cross_domain_ambiguity",
            strong_candidate_count=len(strong),
        )
    return CandidateQuality(
        needs_rewrite=False,
        reason="usable_evidence",
        strong_candidate_count=len(strong),
    )


def select_evidence(
    candidates: list[Chunk],
    max_chunks: int,
    config: EvidenceSelectionConfig,
) -> EvidenceSelectionResult:
    if max_chunks < 1:
        raise ValueError("max_chunks must be positive")

    quality = assess_candidate_quality(candidates, config)
    selected: list[Chunk] = []
    rejected: list[RejectedEvidence] = []
    seen_hashes: set[str] = set()

    for chunk in candidates:
        if chunk.content_hash in seen_hashes:
            rejected.append(RejectedEvidence(chunk, "duplicate"))
            continue
        seen_hashes.add(chunk.content_hash)

        if not _is_strong(chunk, config):
            rejected.append(RejectedEvidence(chunk, "weak_signal"))
            continue
        if (
            quality.coherent_domain
            and chunk.domain.upper() not in {quality.coherent_domain, *GENERAL_DOMAINS}
        ):
            rejected.append(RejectedEvidence(chunk, "cross_domain"))
            continue
        if len(selected) >= max_chunks:
            rejected.append(RejectedEvidence(chunk, "context_limit"))
            continue
        selected.append(chunk)

    return EvidenceSelectionResult(
        selected=selected,
        rejected=rejected,
        quality=quality,
    )


def _is_strong(chunk: Chunk, config: EvidenceSelectionConfig) -> bool:
    signals = chunk.retrieval
    has_dense = signals.dense_score is not None
    has_bm25 = signals.bm25_score is not None
    if not has_dense and not has_bm25:
        return chunk.score > 0
    agreement = has_dense and has_bm25
    dense_passed = has_dense and signals.dense_score >= config.min_dense_score
    bm25_passed = has_bm25 and signals.bm25_score >= config.min_bm25_score
    return agreement or dense_passed or bm25_passed


def _coherent_domain(
    domain_counts: Counter[str],
    minimum_chunks: int,
) -> str | None:
    if not domain_counts:
        return None
    domain, count = domain_counts.most_common(1)[0]
    if count < minimum_chunks:
        return None
    tied = sum(candidate_count == count for candidate_count in domain_counts.values()) > 1
    return None if tied else domain
