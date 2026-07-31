from __future__ import annotations

from pathlib import Path

from app.api.schemas import RouteTrace
from app.config import Settings
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalResult
from app.rag.pipeline import GENERATION_FAILED_RESPONSE, RAGPipeline
from app.rag.response_validator import validate_critical_literals


def _chunk(content: str) -> Chunk:
    return Chunk(
        chunk_id="chunk-1",
        parent_id=None,
        document_id="doc-1",
        document_name="Nội Quy",
        document_version="1",
        knowledge_type=KnowledgeType.POLICY,
        domain="HR_POLICY",
        section="Điều 1: Thời gian làm việc",
        heading_path=["Điều 1: Thời gian làm việc"],
        chunk_index=0,
        content=content,
        source_path="source.docx",
        content_hash="hash-1",
        score=0.8,
    )


class FakeRetriever:
    def __init__(self, content: str) -> None:
        self.content = content

    async def retrieve(self, query, filters=None) -> RetrievalResult:
        return RetrievalResult(chunks=[_chunk(self.content)], candidate_count=1)


class FakeLLM:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self.outputs.pop(0)


def test_critical_literal_validator_normalizes_time_formats_without_heading_false_positive(
) -> None:
    result = validate_critical_literals(
        "Giờ làm kết thúc lúc 17:30. [SOURCE_1]",
        "Điều 1: Thời gian làm việc. Giờ làm từ 8h00 đến 17h:30.",
    )

    assert result.passed is True
    assert result.unsupported == ()


def test_critical_literal_validator_rejects_unsupported_ip_and_port() -> None:
    result = validate_critical_literals(
        "Kết nối 10.10.12.99 qua port 8443. [SOURCE_1]",
        "Máy chủ có địa chỉ 10.10.12.10 và sử dụng port 443.",
    )

    assert result.passed is False
    assert result.unsupported == ("ip:10.10.12.99", "port:8443")


def test_route_trace_contract_keeps_retrieval_v2_diagnostics() -> None:
    trace = RouteTrace.model_validate(
        {
            "retrieval_first": True,
            "adaptive_rewrite_used": True,
            "retrieval_queries": ["xin nghỉ hẳn", "quy trình nghỉ việc"],
            "candidate_quality": "coherent_domain",
            "selected_chunk_ids": ["chunk-1"],
            "rejected_chunks": {"chunk-2": "cross_domain"},
            "literal_validation_error": None,
        }
    )

    assert trace.retrieval_queries == ["xin nghỉ hẳn", "quy trình nghỉ việc"]
    assert trace.rejected_chunks == {"chunk-2": "cross_domain"}


async def test_grounded_time_format_is_not_blocked_by_heuristic_guard(
    tmp_path: Path,
) -> None:
    llm = FakeLLM(
        [
            (
                '{"status":"answered",'
                '"answer":"Thời gian làm việc kết thúc lúc 17:30. [SOURCE_1]",'
                '"sources":["SOURCE_1"]}'
            )
        ]
    )
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever("Thời gian làm việc từ 8h00 đến 17h:30."),
        llm,
    )

    result = await pipeline.answer("giờ làm việc")

    assert result["status"] == "answered"
    assert llm.calls == 1
    assert result["trace"]["literal_validation_error"] is None


async def test_unsupported_critical_literal_returns_generation_failed(
    tmp_path: Path,
) -> None:
    llm = FakeLLM(
        [
            (
                '{"status":"answered",'
                '"answer":"Máy chủ sử dụng port 8443. [SOURCE_1]",'
                '"sources":["SOURCE_1"]}'
            )
        ]
    )
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever("Máy chủ sử dụng port 443."),
        llm,
    )

    result = await pipeline.answer("port máy chủ")

    assert result["status"] == "generation_failed"
    assert result["answer"] == GENERATION_FAILED_RESPONSE
    assert result["trace"]["literal_validation_error"] == "unsupported_literal:port:8443"
    assert llm.calls == 1


async def test_invalid_generation_after_retry_is_not_reported_as_missing_document(
    tmp_path: Path,
) -> None:
    llm = FakeLLM(["not-json", "still-not-json"])
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever("Có tài liệu liên quan."),
        llm,
    )

    result = await pipeline.answer("quy định bảo mật")

    assert result["status"] == "generation_failed"
    assert result["answer"] == GENERATION_FAILED_RESPONSE
    assert result["trace"]["parse_error"] == "invalid_json"
