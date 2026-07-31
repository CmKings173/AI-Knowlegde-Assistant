from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalResult, RetrievalSignals
from app.rag.pipeline import RAGPipeline


def _chunk(
    chunk_id: str,
    *,
    domain: str,
    content: str,
    dense: float | None,
    bm25: float | None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_id=None,
        document_id="hr-doc" if domain == "HR_POLICY" else "it-doc",
        document_name="Nội Quy" if domain == "HR_POLICY" else "Hướng dẫn Windows",
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
        content_hash=f"hash-{chunk_id}",
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


class FakeRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.queries: list[str] = []

    async def retrieve(self, query, filters=None) -> RetrievalResult:
        self.queries.append(query)
        return RetrievalResult(chunks=self.chunks, candidate_count=len(self.chunks))


class FakeLLM:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.outputs.pop(0)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        documents_dir=tmp_path,
        final_context_top_n=4,
        evidence_min_dense_score=0.6,
        evidence_min_bm25_score=1.0,
        evidence_coherent_domain_min_chunks=2,
    )


async def test_pipeline_excludes_weak_and_cross_domain_chunks_from_context(
    tmp_path: Path,
) -> None:
    retriever = FakeRetriever(
        [
            _chunk(
                "working-hours",
                domain="HR_POLICY",
                content="Thời gian làm việc bắt đầu lúc 8:00.",
                dense=0.91,
                bm25=5.0,
            ),
            _chunk(
                "assets",
                domain="HR_POLICY",
                content="Hàng hóa phải xuất qua thủ kho.",
                dense=0.30,
                bm25=None,
            ),
            _chunk(
                "windows",
                domain="WINDOWS",
                content="Windows có chế độ Sleep.",
                dense=0.72,
                bm25=None,
            ),
            _chunk(
                "work-conduct",
                domain="HR_POLICY",
                content="Nhân viên phải có mặt tại nơi làm việc.",
                dense=0.78,
                bm25=2.0,
            ),
        ]
    )
    llm = FakeLLM(
        [
            (
                '{"status":"answered",'
                '"answer":"Giờ làm bắt đầu lúc 8:00. [SOURCE_1]",'
                '"sources":["SOURCE_1"]}'
            )
        ]
    )
    pipeline = RAGPipeline(_settings(tmp_path), retriever, llm)

    result = await pipeline.answer("giờ làm việc của công ty")

    answer_prompt = llm.calls[0][1]
    assert result["status"] == "answered"
    assert result["retrieval"]["context_count"] == 2
    assert "Windows có chế độ Sleep" not in answer_prompt
    assert "Hàng hóa phải xuất qua thủ kho" not in answer_prompt
    assert result["trace"]["selected_chunk_ids"] == [
        "working-hours",
        "work-conduct",
    ]
    assert result["trace"]["rejected_chunks"] == {
        "assets": "weak_signal",
        "windows": "cross_domain",
    }


async def test_ambiguous_internal_wording_uses_retrieval_before_llm_routing(
    tmp_path: Path,
) -> None:
    retriever = FakeRetriever(
        [
            _chunk(
                "working-hours",
                domain="HR_POLICY",
                content="Thời gian làm việc bắt đầu lúc 8:00.",
                dense=0.89,
                bm25=3.0,
            ),
            _chunk(
                "work-conduct",
                domain="HR_POLICY",
                content="Nhân viên phải có mặt tại nơi làm việc.",
                dense=0.80,
                bm25=2.0,
            ),
        ]
    )
    llm = FakeLLM(
        [
            (
                '{"status":"answered",'
                '"answer":"Nhân viên phải có mặt đúng giờ làm việc. [SOURCE_1][SOURCE_2]",'
                '"sources":["SOURCE_1","SOURCE_2"]}'
            )
        ]
    )
    pipeline = RAGPipeline(_settings(tmp_path), retriever, llm)

    result = await pipeline.answer("nếu tôi tới trễ thì bị gì")

    assert result["status"] == "answered"
    assert retriever.queries == ["nếu tôi tới trễ thì bị gì"]
    assert len(llm.calls) == 1
    assert result["trace"]["retrieval_first"] is True
    assert result["trace"]["adaptive_rewrite_used"] is False


async def test_ambiguous_query_with_no_evidence_clarifies_after_retrieval(
    tmp_path: Path,
) -> None:
    retriever = FakeRetriever([])
    llm = FakeLLM(['{"queries":[]}'])
    pipeline = RAGPipeline(_settings(tmp_path), retriever, llm)

    result = await pipeline.answer("cái đó xử lý sao")

    assert retriever.queries == ["cái đó xử lý sao"]
    assert result["status"] == "clarify"
    assert result["retrieval"]["candidate_count"] == 0
    assert result["trace"]["branch"] == "retrieval_first_clarify"
