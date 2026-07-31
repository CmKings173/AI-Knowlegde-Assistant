from __future__ import annotations

from pathlib import Path

import pytest

from app.api.schemas import ChatRequest
from app.config import Settings
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalResult, RetrievalSignals
from app.rag.pipeline import RAGPipeline
from app.rag.routing.models import (
    Capability,
    CapabilityDecision,
    RequestIntent,
    RouteAffinity,
    RouteClassification,
    RoutingDecision,
    TurnKind,
    TurnResolution,
)


class FakeMultiStageRouter:
    def __init__(self, decision: RoutingDecision) -> None:
        self.decision = decision
        self.calls: list[tuple[str, list[dict[str, str]], bool]] = []

    async def route(
        self,
        question: str,
        history: list[dict[str, str]],
        *,
        has_continuation: bool,
    ) -> RoutingDecision:
        self.calls.append((question, history, has_continuation))
        return self.decision


class FailRetriever:
    async def retrieve(self, query, filters=None):
        del query, filters
        raise AssertionError("retriever must not be called")


class FakeRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.queries: list[str] = []

    async def retrieve(self, query, filters=None) -> RetrievalResult:
        del filters
        self.queries.append(query)
        return RetrievalResult(
            chunks=self.chunks,
            candidate_count=len(self.chunks),
            reranker_used=False,
        )


class FailLLM:
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        del system_prompt, user_prompt
        raise AssertionError("LLM must not be called")


class FakeLLM:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.output


class StreamingLLM(FailLLM):
    async def stream_generate(self, system_prompt: str, user_prompt: str):
        del system_prompt, user_prompt
        yield "Mình sẽ giải thích lại rõ hơn."


def _decision(
    *,
    intent: RequestIntent,
    affinity: RouteAffinity,
    capability: Capability,
    turn_kind: TurnKind = TurnKind.INDEPENDENT,
) -> RoutingDecision:
    return RoutingDecision(
        turn=TurnResolution(
            kind=turn_kind,
            resolved_query="",
            confidence=1.0,
            reason="test_turn",
        ),
        classification=RouteClassification(
            intent=intent,
            affinity=affinity,
            confidence=0.95,
            reason="test_classification",
            subject="test subject",
            is_confident=True,
            classifier="embedding",
            turn_kind=turn_kind,
        ),
        capability=CapabilityDecision(
            capability=capability,
            confidence=0.95,
            reason="test_capability",
        ),
        qwen_used=False,
    )


def _chunk() -> Chunk:
    return Chunk(
        chunk_id="chunk-1",
        parent_id=None,
        document_id="doc-1",
        document_name="Nội quy công ty",
        document_version="1",
        knowledge_type=KnowledgeType.POLICY,
        domain="HR_POLICY",
        section="Thời gian làm việc",
        heading_path=["Nội quy", "Thời gian làm việc"],
        chunk_index=0,
        content="Thời gian làm việc được quy định trong tài liệu.",
        source_path="source.docx",
        content_hash="hash-1",
        score=0.03,
        retrieval=RetrievalSignals(
            dense_score=0.91,
            dense_rank=1,
            bm25_score=4.0,
            bm25_rank=1,
            rrf_score=0.03,
            matched_queries=("original",),
        ),
    )


@pytest.mark.asyncio
async def test_external_instruction_is_rejected_without_retrieval_or_llm(
    tmp_path: Path,
) -> None:
    router = FakeMultiStageRouter(
        _decision(
            intent=RequestIntent.REQUEST_INSTRUCTION,
            affinity=RouteAffinity.EXTERNAL,
            capability=Capability.UNSUPPORTED,
        )
    )
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path),
        FailRetriever(),
        FailLLM(),
        route_orchestrator=router,
    )

    result = await pipeline.answer("hướng dẫn tôi dùng github đi")

    assert result["status"] == "out_of_scope"
    assert result["retrieval"]["candidate_count"] == 0
    assert result["trace"]["capability"] == "unsupported"
    assert result["trace"]["route_classifier"] == "embedding"
    assert len(router.calls) == 1


@pytest.mark.asyncio
async def test_conversation_repair_uses_history_without_retrieval(tmp_path: Path) -> None:
    router = FakeMultiStageRouter(
        _decision(
            intent=RequestIntent.CONVERSATION_REPAIR,
            affinity=RouteAffinity.CONVERSATION,
            capability=Capability.CONVERSATION,
            turn_kind=TurnKind.REPAIR,
        )
    )
    llm = FakeLLM(
        '{"status":"conversational",'
        '"answer":"Mình xin giải thích lại câu trả lời trước.",'
        '"sources":[]}'
    )
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path),
        FailRetriever(),
        llm,
        route_orchestrator=router,
    )
    history = [
        {
            "role": "assistant",
            "content": "Tôi chưa thể tổng hợp câu trả lời.",
            "status": "generation_failed",
            "capability": "rag",
        }
    ]

    result = await pipeline.answer("bạn nói gì thế", history=history)

    assert result["status"] == "conversational"
    assert result["trace"]["branch"] == "conversation_llm"
    assert result["trace"]["turn_kind"] == "repair"
    assert len(llm.calls) == 1
    assert "generation_failed" in llm.calls[0][1]


@pytest.mark.asyncio
async def test_conversation_stream_routes_once_and_preserves_delta(tmp_path: Path) -> None:
    router = FakeMultiStageRouter(
        _decision(
            intent=RequestIntent.CONVERSATION_REPAIR,
            affinity=RouteAffinity.CONVERSATION,
            capability=Capability.CONVERSATION,
            turn_kind=TurnKind.REPAIR,
        )
    )
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path),
        FailRetriever(),
        StreamingLLM(),
        route_orchestrator=router,
    )

    events = [
        event
        async for event in pipeline.answer_stream(
            "bạn nói gì thế",
            history=[{"role": "assistant", "content": "Câu trả lời trước."}],
        )
    ]

    assert len(router.calls) == 1
    assert [event["event"] for event in events] == ["progress", "progress", "delta", "final"]
    assert events[-1]["data"]["status"] == "conversational"
    assert events[-1]["data"]["trace"]["capability"] == "conversation"


@pytest.mark.asyncio
async def test_non_conversation_stream_reuses_routing_decision(tmp_path: Path) -> None:
    router = FakeMultiStageRouter(
        _decision(
            intent=RequestIntent.REQUEST_INSTRUCTION,
            affinity=RouteAffinity.EXTERNAL,
            capability=Capability.UNSUPPORTED,
        )
    )
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path),
        FailRetriever(),
        FailLLM(),
        route_orchestrator=router,
    )

    events = [
        event
        async for event in pipeline.answer_stream("hướng dẫn tôi dùng github đi")
    ]

    assert len(router.calls) == 1
    assert events[-1]["event"] == "final"
    assert events[-1]["data"]["status"] == "out_of_scope"


@pytest.mark.asyncio
async def test_internal_knowledge_still_runs_existing_rag_branch(tmp_path: Path) -> None:
    router = FakeMultiStageRouter(
        _decision(
            intent=RequestIntent.ASK_INFORMATION,
            affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
            capability=Capability.RAG,
        )
    )
    retriever = FakeRetriever([_chunk()])
    llm = FakeLLM(
        '{"status":"answered",'
        '"answer":"Thông tin được quy định trong tài liệu. [SOURCE_1]",'
        '"sources":["SOURCE_1"]}'
    )
    pipeline = RAGPipeline(
        Settings(
            documents_dir=tmp_path,
            evidence_min_dense_score=0.5,
            evidence_min_bm25_score=1.0,
        ),
        retriever,
        llm,
        route_orchestrator=router,
    )

    result = await pipeline.answer("công ty quy định thời gian làm việc thế nào")

    assert result["status"] == "answered"
    assert retriever.queries == ["công ty quy định thời gian làm việc thế nào"]
    assert result["trace"]["capability"] == "rag"
    assert result["trace"]["branch"] == "knowledge"


def test_chat_history_preserves_structured_routing_state() -> None:
    request = ChatRequest.model_validate(
        {
            "question": "bạn nói gì thế",
            "history": [
                {
                    "role": "assistant",
                    "content": "Tôi chưa thể tổng hợp câu trả lời.",
                    "status": "generation_failed",
                    "capability": "rag",
                    "subject": "quy định công ty",
                    "turn_kind": "independent",
                }
            ],
        }
    )

    assert request.sanitized_history(6, 4000) == [
        {
            "role": "assistant",
            "content": "Tôi chưa thể tổng hợp câu trả lời.",
            "status": "generation_failed",
            "capability": "rag",
            "subject": "quy định công ty",
            "turn_kind": "independent",
        }
    ]
