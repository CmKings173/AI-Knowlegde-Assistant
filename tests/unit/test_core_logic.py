from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.schemas import ChatResponse
from app.config import Settings
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, DocumentInfo, ParsedElement, RetrievalResult
from app.ingestion.chunker import ChunkingConfig, chunk_document, detect_heading
from app.ingestion.classifier import classify_knowledge_type
from app.rag.citation_builder import build_citations
from app.rag.hybrid_search import reciprocal_rank_fusion
from app.rag.pipeline import RAGPipeline, parse_model_output
from app.rag.prompts import SYSTEM_PROMPT, build_user_prompt
from app.rag.response_validator import (
    filter_citation_ids,
    has_refusal_text,
    remove_unknown_citations,
    should_refuse,
)
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


def test_system_prompt_matches_current_context_format() -> None:
    assert "[SOURCE_X]" in SYSTEM_PROMPT
    assert "Tài liệu:" in SYSTEM_PROMPT
    assert "Mục:" in SYSTEM_PROMPT
    assert "Nội dung:" in SYSTEM_PROMPT
    assert "tối đa 150 từ" in SYSTEM_PROMPT
    assert "JSON object hợp lệ" in SYSTEM_PROMPT
    assert '"status"' in SYSTEM_PROMPT
    assert '"answer"' in SYSTEM_PROMPT
    assert '"sources"' in SYSTEM_PROMPT
    assert "answered" in SYSTEM_PROMPT
    assert "partial" in SYSTEM_PROMPT
    assert "insufficient_context" in SYSTEM_PROMPT
    assert "out_of_scope" in SYSTEM_PROMPT
    assert "conflict" in SYSTEM_PROMPT
    assert "escape đúng theo chuẩn JSON" in SYSTEM_PROMPT
    assert "sources giữ thứ tự xuất hiện lần đầu" in SYSTEM_PROMPT
    assert "không phải nguồn nghiệp vụ thật" in SYSTEM_PROMPT
    assert "Ví dụ 1" in SYSTEM_PROMPT
    assert "Ví dụ 2" in SYSTEM_PROMPT
    assert "Ví dụ 3" in SYSTEM_PROMPT
    assert "Knowledge type:" not in SYSTEM_PROMPT

    user_prompt = build_user_prompt("NAS là gì?", "[SOURCE_1]\nTài liệu: Doc\nMục: NAS")
    assert "CONTEXT:" in user_prompt
    assert "CÂU HỎI:" in user_prompt
    assert "JSON hợp lệ" in user_prompt
    assert "NAS là gì?" in user_prompt


def test_refusal_detection_uses_current_vietnamese_messages() -> None:
    assert has_refusal_text("Tôi chưa tìm thấy thông tin này trong tài liệu nội bộ hiện có.")
    assert has_refusal_text("Câu hỏi này nằm ngoài phạm vi kho kiến thức nội bộ hiện có.")


def test_parse_model_output_accepts_json_and_sources() -> None:
    parsed = parse_model_output(
        (
            '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
            '"sources": ["SOURCE_1"]}'
        ),
        {"SOURCE_1"},
    )

    assert parsed.is_valid
    assert parsed.status == "answered"
    assert parsed.answer == "Mở File Explorer. [SOURCE_1]"
    assert parsed.sources == ["SOURCE_1"]


def test_parse_model_output_rejects_text_when_not_json() -> None:
    parsed = parse_model_output("Mở File Explorer. SOURCE_1", {"SOURCE_1"})

    assert not parsed.is_valid
    assert parsed.error == "invalid_json"


def test_parse_model_output_rejects_source_mismatch() -> None:
    parsed = parse_model_output(
        (
            '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
            '"sources": ["SOURCE_2"]}'
        ),
        {"SOURCE_1", "SOURCE_2"},
    )

    assert not parsed.is_valid
    assert parsed.error == "source_mismatch"


def test_parse_model_output_rejects_duplicate_or_unavailable_sources() -> None:
    duplicate = parse_model_output(
        (
            '{"status": "answered", "answer": "Theo [SOURCE_1]. [SOURCE_1]", '
            '"sources": ["SOURCE_1", "SOURCE_1"]}'
        ),
        {"SOURCE_1"},
    )
    unavailable = parse_model_output(
        (
            '{"status": "answered", "answer": "Theo [SOURCE_999].", '
            '"sources": ["SOURCE_999"]}'
        ),
        {"SOURCE_1"},
    )

    assert not duplicate.is_valid
    assert duplicate.error == "duplicate_sources"
    assert not unavailable.is_valid
    assert unavailable.error == "unknown_source"


def test_parse_model_output_preserves_escaped_windows_path() -> None:
    parsed = parse_model_output(
        (
            r'{"status": "answered", '
            r'"answer": "Mở C:\\Users\\Admin\\AppData. [SOURCE_1]", '
            r'"sources": ["SOURCE_1"]}'
        ),
        {"SOURCE_1"},
    )

    assert parsed.is_valid
    assert parsed.answer == r"Mở C:\Users\Admin\AppData. [SOURCE_1]"


def test_chat_response_requires_status() -> None:
    response = ChatResponse(
        status="answered",
        answer="Mở File Explorer. [SOURCE_1]",
        citations=[
            {
                "citation_id": "SOURCE_1",
                "document_name": "Doc",
                "section": "NAS",
                "chunk_id": "chunk-a",
                "excerpt": "Mở File Explorer.",
                "images": [],
            }
        ],
        retrieval={"candidate_count": 1, "context_count": 1, "reranker_used": False},
        timing_ms={"total": 1},
    )

    assert response.status == "answered"

    try:
        ChatResponse(
            answer="Mở File Explorer. [SOURCE_1]",
            citations=[],
            retrieval={"candidate_count": 1, "context_count": 1, "reranker_used": False},
            timing_ms={"total": 1},
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("ChatResponse must require status")


@pytest.mark.asyncio
async def test_pipeline_retries_invalid_json_once(tmp_path: Path) -> None:
    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk("Mở File Explorer.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.outputs = [
                (
                    '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
                    '"sources": ["SOURCE_2"]}'
                ),
                (
                    '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
                    '"sources": ["SOURCE_1"]}'
                ),
            ]

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return self.outputs.pop(0)

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("Cách mở NAS?")

    assert len(llm.calls) == 2
    assert "không hợp lệ" in llm.calls[1]
    assert result["status"] == "answered"
    assert result["answer"] == "Mở File Explorer. [SOURCE_1]"
    assert [citation["citation_id"] for citation in result["citations"]] == ["SOURCE_1"]


@pytest.mark.asyncio
async def test_pipeline_returns_safe_fallback_after_retry_failure(tmp_path: Path) -> None:
    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk("Mở File Explorer.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls += 1
            return "not json"

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("Cách mở NAS?")

    assert llm.calls == 2
    assert result["status"] == "insufficient_context"
    assert result["answer"] == "Tôi chưa tìm thấy thông tin này trong tài liệu nội bộ hiện có."
    assert result["citations"] == []


def _chunk(content: str) -> Chunk:
    return Chunk(
        chunk_id="chunk-a",
        parent_id=None,
        document_id="doc-a",
        document_name="Doc",
        document_version="v1",
        knowledge_type=KnowledgeType.TECHNICAL_GUIDE,
        domain="it",
        section="NAS",
        heading_path=["NAS"],
        chunk_index=0,
        content=content,
        source_path="doc.md",
        content_hash="hash-a",
        score=0.8,
    )
