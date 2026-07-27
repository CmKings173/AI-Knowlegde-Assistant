from __future__ import annotations

import time

from app.config import Settings
from app.documents.images import load_image_lookup
from app.domain.models import Citation
from app.providers.llm.base import LLMProvider
from app.rag.citation_builder import build_citations
from app.rag.context_builder import build_context
from app.rag.prompts import SYSTEM_PROMPT, build_user_prompt
from app.rag.query_normalizer import QueryNormalizer
from app.rag.response_validator import (
    filter_citation_ids,
    has_refusal_text,
    remove_unknown_citations,
    should_refuse,
)
from app.rag.retriever import Retriever
from app.utils.timing import measure_ms

REFUSAL = (
    "Tôi chưa tìm thấy thông tin này trong tài liệu nội bộ hiện có. "
    "Bạn có thể hỏi lại bằng từ khóa cụ thể hơn hoặc liên hệ người phụ trách."
)


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

    async def answer(self, question: str) -> dict[str, object]:
        total_start = time.perf_counter()
        timing: dict[str, int] = {"retrieval": 0, "rerank": 0, "llm": 0, "total": 0}
        normalized = self.normalizer.normalize(question)
        with measure_ms(timing, "retrieval"):
            retrieval = await self.retriever.retrieve(normalized)
        best_score = retrieval.chunks[0].score if retrieval.chunks else 0.0
        if should_refuse(retrieval.candidate_count, best_score, self.settings.min_retrieval_score):
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            return _response(
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
        with measure_ms(timing, "llm"):
            user_prompt = build_user_prompt(normalized, context)
            answer = await self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
        answer = remove_unknown_citations(answer, citations)
        used_citations = filter_citation_ids(answer, citations)
        if citations and not used_citations and not has_refusal_text(answer):
            answer = answer.rstrip() + "\n\nNguồn: " + ", ".join(
                citation.citation_id for citation in citations
            )
        elif "Nguồn" not in answer and not has_refusal_text(answer):
            answer = f"{answer.rstrip()}\n\nNguồn: " + ", ".join(c.citation_id for c in citations)
        timing["total"] = int((time.perf_counter() - total_start) * 1000)
        return _response(
            answer=answer,
            citations=citations,
            candidate_count=retrieval.candidate_count,
            context_count=len(selected),
            reranker_used=retrieval.reranker_used,
            timing=timing,
        )


def _response(
    answer: str,
    citations: list[Citation],
    candidate_count: int,
    context_count: int,
    reranker_used: bool,
    timing: dict[str, int],
) -> dict[str, object]:
    return {
        "answer": answer,
        "citations": [citation.__dict__ for citation in citations],
        "retrieval": {
            "candidate_count": candidate_count,
            "context_count": context_count,
            "reranker_used": reranker_used,
        },
        "timing_ms": timing,
    }
