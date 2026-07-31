from __future__ import annotations

from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalSignals
from app.rag.evidence_selector import (
    EvidenceSelectionConfig,
    assess_candidate_quality,
    select_evidence,
)


def _chunk(
    chunk_id: str,
    *,
    domain: str,
    content: str,
    dense: float | None,
    bm25: float | None,
    content_hash: str | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_id=None,
        document_id="hr-doc" if domain == "HR_POLICY" else "it-doc",
        document_name="Nội Quy" if domain == "HR_POLICY" else "Hướng dẫn IT",
        document_version="1",
        knowledge_type=(
            KnowledgeType.POLICY
            if domain == "HR_POLICY"
            else KnowledgeType.TECHNICAL_GUIDE
        ),
        domain=domain,
        section=content,
        heading_path=[content],
        chunk_index=0,
        content=content,
        source_path="source.docx",
        content_hash=content_hash or f"hash-{chunk_id}",
        score=0.03,
        retrieval=RetrievalSignals(
            dense_score=dense,
            dense_rank=1 if dense is not None else None,
            bm25_score=bm25,
            bm25_rank=1 if bm25 is not None else None,
            rrf_score=0.03,
            matched_queries=("original",),
        ),
    )


def _config() -> EvidenceSelectionConfig:
    return EvidenceSelectionConfig(
        min_dense_score=0.60,
        min_bm25_score=1.0,
        coherent_domain_min_chunks=2,
    )


def test_selector_removes_weak_policy_and_cross_domain_noise() -> None:
    candidates = [
        _chunk(
            "working-hours",
            domain="HR_POLICY",
            content="Điều 1: Thời gian làm việc",
            dense=0.91,
            bm25=5.0,
        ),
        _chunk(
            "assets",
            domain="HR_POLICY",
            content="Điều 4: Hàng hóa, tài sản",
            dense=0.31,
            bm25=None,
        ),
        _chunk(
            "windows",
            domain="WINDOWS",
            content="Cài đặt chế độ gập màn hình",
            dense=0.72,
            bm25=None,
        ),
        _chunk(
            "work-conduct",
            domain="HR_POLICY",
            content="Điều 2: Có mặt tại nơi làm việc",
            dense=0.76,
            bm25=2.0,
        ),
    ]

    result = select_evidence(candidates, max_chunks=4, config=_config())

    assert [chunk.chunk_id for chunk in result.selected] == [
        "working-hours",
        "work-conduct",
    ]
    assert {item.chunk.chunk_id: item.reason for item in result.rejected} == {
        "assets": "weak_signal",
        "windows": "cross_domain",
    }
    assert result.quality.needs_rewrite is False
    assert result.quality.coherent_domain == "HR_POLICY"


def test_quality_requests_rewrite_instead_of_hard_filtering_split_domains() -> None:
    candidates = [
        _chunk(
            "hr",
            domain="HR_POLICY",
            content="Thời gian làm việc",
            dense=0.82,
            bm25=2.0,
        ),
        _chunk(
            "it",
            domain="WINDOWS",
            content="Thời gian tắt màn hình",
            dense=0.80,
            bm25=2.0,
        ),
    ]

    quality = assess_candidate_quality(candidates, _config())
    result = select_evidence(candidates, max_chunks=4, config=_config())

    assert quality.needs_rewrite is True
    assert quality.reason == "cross_domain_ambiguity"
    assert quality.coherent_domain is None
    assert [chunk.chunk_id for chunk in result.selected] == ["hr", "it"]


def test_selector_deduplicates_content_and_can_return_less_than_limit() -> None:
    candidates = [
        _chunk(
            "first",
            domain="HR_POLICY",
            content="Giờ làm bắt đầu lúc 8:00",
            dense=0.90,
            bm25=3.0,
            content_hash="same",
        ),
        _chunk(
            "duplicate",
            domain="HR_POLICY",
            content="Giờ làm bắt đầu lúc 8:00",
            dense=0.85,
            bm25=2.5,
            content_hash="same",
        ),
        _chunk(
            "weak",
            domain="HR_POLICY",
            content="Nội dung không liên quan",
            dense=0.20,
            bm25=None,
        ),
    ]

    result = select_evidence(candidates, max_chunks=4, config=_config())

    assert [chunk.chunk_id for chunk in result.selected] == ["first"]
    assert {item.chunk.chunk_id: item.reason for item in result.rejected} == {
        "duplicate": "duplicate",
        "weak": "weak_signal",
    }


def test_legacy_candidates_with_only_rrf_score_remain_compatible() -> None:
    candidate = _chunk(
        "legacy",
        domain="GENERAL",
        content="Nội dung cũ",
        dense=None,
        bm25=None,
    )
    candidate.retrieval = RetrievalSignals()
    candidate.score = 0.02

    result = select_evidence([candidate], max_chunks=4, config=_config())

    assert result.selected == [candidate]
