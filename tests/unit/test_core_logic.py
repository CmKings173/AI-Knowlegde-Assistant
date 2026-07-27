from pathlib import Path

from app.domain.enums import KnowledgeType
from app.domain.models import DocumentInfo, ParsedElement
from app.ingestion.chunker import ChunkingConfig, chunk_document, detect_heading
from app.ingestion.classifier import classify_knowledge_type
from app.rag.citation_builder import build_citations
from app.rag.hybrid_search import reciprocal_rank_fusion
from app.rag.response_validator import filter_citation_ids, remove_unknown_citations, should_refuse
from app.utils.hashing import sha256_text, stable_document_id
from app.utils.text import normalize_query


def test_normalize_query_keeps_technical_tokens() -> None:
    query = "  mở   \\\\10.10.10.200   port 465 SMTP  "
    assert normalize_query(query) == "mở \\\\10.10.10.200 port 465 SMTP"


def test_classifier_detects_policy_and_troubleshooting() -> None:
    assert (
        classify_knowledge_type("Điều 1: Nhân viên phải tuân thủ nội quy")
        == KnowledgeType.POLICY
    )
    assert (
        classify_knowledge_type("Lỗi không truy cập được NAS và cách khắc phục")
        == KnowledgeType.TROUBLESHOOTING
    )


def test_heading_detection_supports_vietnamese_policy_patterns() -> None:
    assert detect_heading("Phần I: Nội quy công ty") == (1, "Phần I: Nội quy công ty")
    assert detect_heading("Điều 1: Thời gian làm việc") == (2, "Điều 1: Thời gian làm việc")


def test_chunker_keeps_heading_path_and_parent_child_links() -> None:
    document = DocumentInfo(
        document_id=stable_document_id("Noi Quy.docx"),
        document_name="Noi Quy",
        source_path=Path("data/uploads/Noi Quy.docx"),
        file_hash=sha256_text("file"),
    )
    elements = [
        ParsedElement("Phần I: Nội quy công ty"),
        ParsedElement("Điều 1: Thời gian làm việc"),
        ParsedElement("- Làm việc từ 8:00 đến 17:30."),
        ParsedElement("- Nghỉ trưa từ 12:00 đến 13:30."),
    ]
    chunks = chunk_document(document, elements, ChunkingConfig(max_tokens=20))
    assert any(chunk.is_parent for chunk in chunks)
    child = next(chunk for chunk in chunks if not chunk.is_parent)
    assert child.parent_id is not None
    assert child.heading_path == ["Phần I: Nội quy công ty", "Điều 1: Thời gian làm việc"]
    assert "8:00" in child.content


def test_rrf_merges_duplicate_candidates() -> None:
    fused = reciprocal_rank_fusion(
        [[("a", 0.9), ("b", 0.8)], [("b", 0.7), ("c", 0.6)]],
        top_k=3,
    )
    assert [item[0] for item in fused] == ["b", "a", "c"]


def test_citation_validator_drops_unknown_source_ids() -> None:
    document = DocumentInfo(
        document_id="doc",
        document_name="Doc",
        source_path=Path("doc.docx"),
        file_hash="v1",
    )
    chunk = chunk_document(
        document,
        [ParsedElement("NAS", style="Heading 1"), ParsedElement("Nhấn Windows + R")],
        ChunkingConfig(),
    )[0]
    citations = build_citations([chunk])
    assert filter_citation_ids("Theo SOURCE_1 và SOURCE_999", citations) == {"SOURCE_1"}
    assert remove_unknown_citations("Theo SOURCE_1 và SOURCE_999", citations) == "Theo SOURCE_1 và "


def test_refusal_logic_uses_candidate_count_and_score() -> None:
    assert should_refuse(candidate_count=0, best_score=1.0, min_score=0.25)
    assert should_refuse(candidate_count=2, best_score=0.1, min_score=0.25)
    assert not should_refuse(candidate_count=2, best_score=0.5, min_score=0.25)
