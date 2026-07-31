from __future__ import annotations

from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalResult, RetrievalSignals
from app.rag.adaptive_retrieval import AdaptiveRetriever, parse_adaptive_rewrite
from app.rag.evidence_selector import EvidenceSelectionConfig


def _chunk(
    chunk_id: str,
    *,
    domain: str = "HR_POLICY",
    dense: float | None = 0.8,
    bm25: float | None = 2.0,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_id=None,
        document_id="doc-1",
        document_name="Nội Quy",
        document_version="1",
        knowledge_type=KnowledgeType.POLICY,
        domain=domain,
        section=chunk_id,
        heading_path=[chunk_id],
        chunk_index=0,
        content=chunk_id,
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
    def __init__(self, responses: dict[str, list[Chunk] | Exception]) -> None:
        self.responses = responses
        self.queries: list[str] = []

    async def retrieve(self, query, filters=None) -> RetrievalResult:
        self.queries.append(query)
        chunks = self.responses.get(query, [])
        if isinstance(chunks, Exception):
            raise chunks
        return RetrievalResult(chunks=chunks, candidate_count=len(chunks))


class FakeLLM:
    def __init__(self, output: str = "") -> None:
        self.output = output
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.output


def _config() -> EvidenceSelectionConfig:
    return EvidenceSelectionConfig(
        min_dense_score=0.6,
        min_bm25_score=1.0,
        coherent_domain_min_chunks=2,
    )


async def test_normal_path_does_not_call_qwen_rewrite() -> None:
    retriever = FakeRetriever(
        {
            "giờ làm việc": [
                _chunk("working-hours"),
                _chunk("work-conduct"),
            ]
        }
    )
    llm = FakeLLM()
    adaptive = AdaptiveRetriever(retriever, llm, _config())

    result = await adaptive.retrieve("giờ làm việc")

    assert retriever.queries == ["giờ làm việc"]
    assert llm.calls == []
    assert result.rewrite_used is False
    assert result.queries == ("giờ làm việc",)


async def test_weak_path_uses_same_qwen_and_keeps_original_query() -> None:
    original = _chunk("weak", dense=0.2, bm25=None)
    rewritten = _chunk("working-hours", dense=0.9, bm25=4.0)
    retriever = FakeRetriever(
        {
            "nếu tôi đi muộn có sao không": [original],
            "quy định thời gian làm việc": [rewritten],
            "xử lý vi phạm giờ làm việc": [_chunk("work-conduct", dense=0.8, bm25=3.0)],
        }
    )
    llm = FakeLLM(
        '{"queries":["quy định thời gian làm việc",'
        '"xử lý vi phạm giờ làm việc","không được dùng"]}'
    )
    adaptive = AdaptiveRetriever(retriever, llm, _config())

    result = await adaptive.retrieve(
        "nếu tôi đi muộn có sao không",
        history=[{"role": "user", "content": "Tôi đang hỏi về nội quy."}],
    )

    assert retriever.queries == [
        "nếu tôi đi muộn có sao không",
        "quy định thời gian làm việc",
        "xử lý vi phạm giờ làm việc",
    ]
    assert len(llm.calls) == 1
    assert result.rewrite_used is True
    assert result.queries == (
        "nếu tôi đi muộn có sao không",
        "quy định thời gian làm việc",
        "xử lý vi phạm giờ làm việc",
    )
    assert {chunk.chunk_id for chunk in result.retrieval.chunks} == {
        "weak",
        "working-hours",
        "work-conduct",
    }
    assert result.quality.needs_rewrite is False


async def test_invalid_rewrite_falls_back_without_second_retrieval() -> None:
    retriever = FakeRetriever({"câu khó": [_chunk("weak", dense=0.1, bm25=None)]})
    llm = FakeLLM("không phải json")
    adaptive = AdaptiveRetriever(retriever, llm, _config())

    result = await adaptive.retrieve("câu khó")

    assert retriever.queries == ["câu khó"]
    assert result.rewrite_used is False
    assert result.rewrite_error == "invalid_rewrite_output"
    assert [chunk.chunk_id for chunk in result.retrieval.chunks] == ["weak"]


async def test_rewritten_retrieval_failure_falls_back_to_original_candidates() -> None:
    original = _chunk("weak", dense=0.2, bm25=None)
    retriever = FakeRetriever(
        {
            "câu khó": [original],
            "truy vấn rõ hơn": RuntimeError("embedding unavailable"),
        }
    )
    llm = FakeLLM('{"queries":["truy vấn rõ hơn"]}')
    adaptive = AdaptiveRetriever(retriever, llm, _config())

    result = await adaptive.retrieve("câu khó")

    assert result.rewrite_used is False
    assert result.rewrite_error == "rewritten_retrieval_failed"
    assert result.queries == ("câu khó",)
    assert result.retrieval.chunks == [original]


def test_parse_adaptive_rewrite_sanitizes_deduplicates_and_limits_queries() -> None:
    output = (
        '```json\n{"queries":["  giờ làm việc  ","giờ làm việc",'
        '"xử lý vi phạm","query thứ ba"]}\n```'
    )

    assert parse_adaptive_rewrite(output, original_query="đi muộn") == (
        "giờ làm việc",
        "xử lý vi phạm",
    )
