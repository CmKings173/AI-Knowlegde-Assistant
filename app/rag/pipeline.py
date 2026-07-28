from __future__ import annotations

import json
import time
from dataclasses import dataclass

from app.config import Settings
from app.documents.images import load_image_lookup
from app.domain.models import Citation, RetrievalFilters
from app.providers.llm.base import LLMProvider
from app.rag.citation_builder import build_citations
from app.rag.context_builder import build_context
from app.rag.prompts import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt
from app.rag.query_normalizer import QueryNormalizer
from app.rag.response_validator import (
    citation_ids_in_answer,
    should_refuse,
)
from app.rag.retriever import Retriever
from app.utils.timing import measure_ms

REFUSAL = "Tôi chưa tìm thấy thông tin này trong tài liệu nội bộ hiện có."
FALLBACK_STATUS = "insufficient_context"
VALID_STATUSES = {
    "answered",
    "partial",
    "insufficient_context",
    "out_of_scope",
    "conflict",
}
SOURCE_REQUIRED_STATUSES = {"answered", "partial", "conflict"}
SOURCE_EMPTY_STATUSES = {"insufficient_context", "out_of_scope"}
REQUIRED_OUTPUT_FIELDS = {"status", "answer", "sources"}


@dataclass(frozen=True)
class ParsedModelOutput:
    status: str
    answer: str
    sources: list[str]
    is_valid: bool
    error: str | None = None


class RAGPipeline:
    def __init__(
        self,
        settings: Settings,
        retriever: Retriever,
        llm_provider: LLMProvider,
    ) -> None:
        self.settings = settings
        self.normalizer = QueryNormalizer(settings)
        self.retriever = retriever
        self.llm_provider = llm_provider

    async def answer(
        self,
        question: str,
        filters: RetrievalFilters | None = None,
    ) -> dict[str, object]:
        total_start = time.perf_counter()
        timing: dict[str, int] = {"retrieval": 0, "rerank": 0, "llm": 0, "total": 0}
        normalized = self.normalizer.normalize(question)
        with measure_ms(timing, "retrieval"):
            retrieval = await self.retriever.retrieve(normalized, filters)
        best_score = retrieval.chunks[0].score if retrieval.chunks else 0.0
        if should_refuse(retrieval.candidate_count, best_score, self.settings.min_retrieval_score):
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            return _response(
                status=FALLBACK_STATUS,
                answer=REFUSAL,
                citations=[],
                candidate_count=retrieval.candidate_count,
                context_count=0,
                reranker_used=False,
                timing=timing,
            )

        context, selected = build_context(
            retrieval.chunks[: self.settings.final_context_top_n],
            self.settings.max_context_tokens,
        )
        image_lookup = load_image_lookup(
            self.settings.documents_dir,
            {chunk.document_id for chunk in selected},
        )
        citations = build_citations(selected, image_lookup)
        available_sources = {citation.citation_id for citation in citations}
        with measure_ms(timing, "llm"):
            user_prompt = build_user_prompt(normalized, context)
            raw_answer = await self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
            parsed = parse_model_output(raw_answer, available_sources)
            if not parsed.is_valid:
                retry_prompt = build_retry_prompt(
                    normalized,
                    context,
                    parsed.error or "invalid_output",
                )
                raw_answer = await self.llm_provider.generate(SYSTEM_PROMPT, retry_prompt)
                parsed = parse_model_output(raw_answer, available_sources)

        if parsed.is_valid:
            status = parsed.status
            answer = parsed.answer
            response_citations = _citations_for_sources(citations, parsed.sources)
        else:
            status = FALLBACK_STATUS
            answer = REFUSAL
            response_citations = []

        timing["total"] = int((time.perf_counter() - total_start) * 1000)
        return _response(
            status=status,
            answer=answer,
            citations=response_citations,
            candidate_count=retrieval.candidate_count,
            context_count=len(selected),
            reranker_used=retrieval.reranker_used,
            timing=timing,
        )


def parse_model_output(
    output: str,
    available_sources: set[str] | None = None,
) -> ParsedModelOutput:
    cleaned = _strip_json_fence(output.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return _invalid("invalid_json")
    if not isinstance(data, dict):
        return _invalid("invalid_schema")

    if set(data) != REQUIRED_OUTPUT_FIELDS:
        return _invalid("invalid_schema")

    status = data.get("status")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        return _invalid("invalid_status")

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return _invalid("invalid_answer")

    raw_sources = data.get("sources", [])
    if not isinstance(raw_sources, list) or not all(
        isinstance(source, str) for source in raw_sources
    ):
        return _invalid("invalid_sources")

    sources = list(raw_sources)
    if len(sources) != len(set(sources)):
        return _invalid("duplicate_sources")

    if available_sources is not None and any(source not in available_sources for source in sources):
        return _invalid("unknown_source")

    answer = answer.strip()
    answer_sources = citation_ids_in_answer(answer)
    if answer_sources != sources:
        return _invalid("source_mismatch")

    if status in SOURCE_EMPTY_STATUSES and sources:
        return _invalid("source_mismatch")

    if status in SOURCE_REQUIRED_STATUSES and not sources:
        return _invalid("missing_sources")

    return ParsedModelOutput(
        status=status,
        answer=answer,
        sources=sources,
        is_valid=True,
    )


def _invalid(error: str) -> ParsedModelOutput:
    return ParsedModelOutput(
        status=FALLBACK_STATUS,
        answer="",
        sources=[],
        is_valid=False,
        error=error,
    )


def _strip_json_fence(output: str) -> str:
    if not output.startswith("```"):
        return output
    lines = output.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return output


def _citations_for_sources(
    citations: list[Citation],
    sources: list[str],
) -> list[Citation]:
    citation_by_id = {citation.citation_id: citation for citation in citations}
    return [citation_by_id[source] for source in sources if source in citation_by_id]


def _response(
    status: str,
    answer: str,
    citations: list[Citation],
    candidate_count: int,
    context_count: int,
    reranker_used: bool,
    timing: dict[str, int],
) -> dict[str, object]:
    return {
        "status": status,
        "answer": answer,
        "citations": [citation.__dict__ for citation in citations],
        "retrieval": {
            "candidate_count": candidate_count,
            "context_count": context_count,
            "reranker_used": reranker_used,
        },
        "timing_ms": timing,
    }
