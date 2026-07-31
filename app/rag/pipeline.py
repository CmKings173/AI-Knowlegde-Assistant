from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from enum import StrEnum

from app.config import Settings
from app.documents.images import load_image_lookup
from app.domain.models import Chunk, Citation, RetrievalFilters, filters_select_no_documents
from app.providers.llm.base import LLMProvider
from app.rag.adaptive_retrieval import AdaptiveRetriever
from app.rag.citation_builder import build_citations
from app.rag.context_builder import build_context
from app.rag.evidence_selector import (
    EvidenceSelectionConfig,
    select_evidence,
)
from app.rag.intent_router import FollowUpSubtype, Intent, IntentDecision, IntentRouter
from app.rag.prompts import (
    CONVERSATIONAL_STREAM_SYSTEM_PROMPT,
    CONVERSATIONAL_SYSTEM_PROMPT,
    QUERY_REWRITE_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_broad_retry_prompt,
    build_broad_user_prompt,
    build_conversation_prompt,
    build_conversation_stream_prompt,
    build_query_rewrite_prompt,
    build_retry_prompt,
    build_router_prompt,
    build_user_prompt,
)
from app.rag.query_normalizer import QueryNormalizer
from app.rag.response_validator import (
    CriticalLiteralValidation,
    citation_ids_in_answer,
    contains_disallowed_cjk,
    should_refuse,
    validate_critical_literals,
)
from app.rag.retriever import Retriever
from app.rag.routing.models import (
    Capability,
    RequestIntent,
    RoutingDecision,
    TurnKind,
)
from app.rag.routing.router import MultiStageRouter
from app.rag.section_expander import expand_section_chunks
from app.utils.text import normalize_for_intent
from app.utils.timing import measure_ms

logger = logging.getLogger(__name__)

REFUSAL = (
    "T\u00f4i ch\u01b0a t\u00ecm th\u1ea5y th\u00f4ng tin n\u00e0y "
    "trong t\u00e0i li\u1ec7u n\u1ed9i b\u1ed9 hi\u1ec7n c\u00f3."
)
CONVERSATIONAL_RESPONSE = (
    "Ch\u00e0o b\u1ea1n, m\u00ecnh l\u00e0 Tr\u1ee3 l\u00fd Ki\u1ebfn th\u1ee9c "
    "N\u1ed9i b\u1ed9 Vi\u1ec7t Th\u00e1i D\u01b0\u01a1ng. "
    "M\u00ecnh c\u00f3 th\u1ec3 h\u1ed7 tr\u1ee3 tra c\u1ee9u n\u1ed9i quy, "
    "ch\u00ednh s\u00e1ch, SOP, NAS, Outlook, "
    "email, Windows v\u00e0 troubleshooting."
)
CLARIFY_RESPONSE = (
    "B\u1ea1n \u0111ang g\u1eb7p v\u1ea5n \u0111\u1ec1 v\u1edbi ph\u1ea7n n\u00e0o: "
    "NAS, Outlook, email, Windows hay m\u1ed9t quy tr\u00ecnh n\u1ed9i b\u1ed9? "
    "N\u00f3i r\u00f5 th\u00eam gi\u00fap m\u00ecnh \u0111\u1ec3 "
    "tra c\u1ee9u \u0111\u00fang t\u00e0i li\u1ec7u."
)
DEEPER_CLARIFY_RESPONSE = (
    "B\u1ea1n mu\u1ed1n tra c\u1ee9u n\u1ed9i dung c\u1ee5 th\u1ec3 n\u00e0o "
    "trong nh\u00f3m n\u00e0y? N\u00f3i r\u00f5 t\u00ean quy tr\u00ecnh, "
    "v\u1ea5n \u0111\u1ec1 ho\u1eb7c t\u00ecnh hu\u1ed1ng \u0111ang g\u1eb7p "
    "\u0111\u1ec3 m\u00ecnh tra c\u1ee9u \u0111\u00fang t\u00e0i li\u1ec7u."
)
OUT_OF_SCOPE_RESPONSE = (
    "C\u00e2u h\u1ecfi n\u00e0y n\u1eb1m ngo\u00e0i ph\u1ea1m vi "
    "kho ki\u1ebfn th\u1ee9c n\u1ed9i b\u1ed9 hi\u1ec7n c\u00f3. "
    "M\u00ecnh c\u00f3 th\u1ec3 h\u1ed7 tr\u1ee3 b\u1ea1n tra c\u1ee9u "
    "n\u1ed9i quy, ch\u00ednh s\u00e1ch, SOP, NAS, Outlook, email, "
    "Windows v\u00e0 troubleshooting trong t\u00e0i li\u1ec7u n\u1ed9i b\u1ed9."
)
OUT_OF_SCOPE_EMOTION_RESPONSE = (
    "M\u00ecnh nghe b\u1ea1n \u0111ang kh\u00f4ng tho\u1ea3i m\u00e1i. "
    "M\u00ecnh kh\u00f4ng ph\u1ea3i tr\u1ee3 l\u00fd t\u01b0 v\u1ea5n c\u00e1 nh\u00e2n, "
    "nh\u01b0ng m\u00ecnh c\u00f3 th\u1ec3 h\u1ed7 tr\u1ee3 b\u1ea1n tra c\u1ee9u "
    "v\u0103n h\u00f3a c\u00f4ng ty, n\u1ed9i quy, ch\u00ednh s\u00e1ch ho\u1eb7c SOP "
    "n\u1ebfu \u0111i\u1ec1u \u0111\u00f3 li\u00ean quan \u0111\u1ebfn c\u00f4ng vi\u1ec7c."
)
OUT_OF_SCOPE_LEISURE_RESPONSE = (
    "M\u00ecnh ch\u01b0a h\u1ed7 tr\u1ee3 l\u00ean k\u1ebf ho\u1ea1ch c\u00e1 nh\u00e2n "
    "ho\u1eb7c \u0111i ch\u01a1i. N\u1ebfu b\u1ea1n c\u1ea7n tra c\u1ee9u th\u00f4ng tin "
    "n\u1ed9i b\u1ed9 nh\u01b0 n\u1ed9i quy, v\u0103n h\u00f3a c\u00f4ng ty, SOP, "
    "NAS, Outlook, email ho\u1eb7c Windows th\u00ec m\u00ecnh h\u1ed7 tr\u1ee3 \u0111\u01b0\u1ee3c."
)
REPEATED_OUT_OF_SCOPE_RESPONSE = (
    "M\u00ecnh \u0111ang nh\u1eadn nhi\u1ec1u c\u00e2u h\u1ecfi ngo\u00e0i ph\u1ea1m vi "
    "tr\u1ee3 l\u00fd ki\u1ebfn th\u1ee9c n\u1ed9i b\u1ed9. \u0110\u1ec3 m\u00ecnh h\u1eefu "
    "\u00edch h\u01a1n, b\u1ea1n c\u00f3 th\u1ec3 h\u1ecfi v\u00ed d\u1ee5: "
    "'n\u1ed9i quy c\u00f4ng ty g\u1ed3m nh\u1eefng g\u00ec?', "
    "'v\u0103n h\u00f3a c\u00f4ng ty nh\u01b0 th\u1ebf n\u00e0o?' "
    "ho\u1eb7c 'c\u00e1ch x\u1eed l\u00fd l\u1ed7i Outlook'."
)
NO_DOCUMENTS_SELECTED_RESPONSE = (
    "B\u1ea1n ch\u01b0a ch\u1ecdn t\u00e0i li\u1ec7u n\u00e0o \u0111\u1ec3 tra c\u1ee9u. "
    "H\u00e3y ch\u1ecdn \u00edt nh\u1ea5t m\u1ed9t t\u00e0i li\u1ec7u \u1edf thanh b\u00ean "
    "tr\u00e1i, ho\u1eb7c ch\u1ecdn t\u1ea5t c\u1ea3 t\u00e0i li\u1ec7u."
)
GENERATION_FAILED_RESPONSE = (
    "T\u00f4i t\u00ecm th\u1ea5y t\u00e0i li\u1ec7u li\u00ean quan "
    "nh\u01b0ng ch\u01b0a th\u1ec3 t\u1ed5ng h\u1ee3p c\u00e2u tr\u1ea3 l\u1eddi "
    "\u0111\u00e1ng tin c\u1eady t\u1eeb ngu\u1ed3n hi\u1ec7n c\u00f3."
)
FALLBACK_STATUS = "insufficient_context"
VALID_STATUSES = {
    "answered",
    "partial",
    "insufficient_context",
    "out_of_scope",
    "conversational",
    "clarify",
    "generation_failed",
    "conflict",
}
RAG_STATUSES = {"answered", "partial", "insufficient_context", "conflict"}
CONVERSATIONAL_STATUSES = {"conversational"}
SOURCE_REQUIRED_STATUSES = {"answered", "partial", "conflict"}
SOURCE_EMPTY_STATUSES = {
    "insufficient_context",
    "out_of_scope",
    "conversational",
    "clarify",
    "generation_failed",
}
REQUIRED_OUTPUT_FIELDS = {"status", "answer", "sources"}
CONTINUATION_FIELDS = ("mode", "document_id", "section_root", "next_offset", "source_question")

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
        *,
        route_orchestrator: MultiStageRouter | None = None,
    ) -> None:
        self.settings = settings
        self.normalizer = QueryNormalizer(settings)
        self.intent_router = IntentRouter()
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.route_orchestrator = route_orchestrator
        self.evidence_config = EvidenceSelectionConfig(
            min_dense_score=settings.evidence_min_dense_score,
            min_bm25_score=settings.evidence_min_bm25_score,
            coherent_domain_min_chunks=settings.evidence_coherent_domain_min_chunks,
        )
        self.adaptive_retriever = AdaptiveRetriever(
            retriever,
            llm_provider,
            self.evidence_config,
        )

    async def answer(
        self,
        question: str,
        filters: RetrievalFilters | None = None,
        history: list[dict[str, str]] | None = None,
        continuation: dict[str, object] | None = None,
        _routing_decision: RoutingDecision | None = None,
    ) -> dict[str, object]:
        total_start = time.perf_counter()
        timing: dict[str, int] = {
            "router": 0,
            "rewrite": 0,
            "retrieval": 0,
            "rerank": 0,
            "llm": 0,
            "total": 0,
        }
        normalized = self.normalizer.normalize(question)
        history = history or []
        trace: dict[str, object] = {}
        if _is_category_only_after_clarify(normalized, history):
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            _trace(
                "rag_response",
                branch="clarify_deeper",
                status="clarify",
                total_ms=timing["total"],
            )
            return _response(
                status="clarify",
                answer=DEEPER_CLARIFY_RESPONSE,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={
                    "intent": Intent.CLARIFY,
                    "branch": "clarify_deeper",
                    "reason": "category_only_after_clarify",
                },
            )
        if continuation and _is_continue_request(normalized):
            if not self.verify_continuation(continuation):
                _trace(
                    "rag_continuation_rejected",
                    has_history=bool(history),
                    question_chars=len(question),
                    reason="invalid_token",
                )
                timing["total"] = int((time.perf_counter() - total_start) * 1000)
                return _response(
                    status=FALLBACK_STATUS,
                    answer=REFUSAL,
                    citations=[],
                    candidate_count=0,
                    context_count=0,
                    reranker_used=False,
                    timing=timing,
                    trace={
                        "intent": Intent.FOLLOW_UP,
                        "subtype": FollowUpSubtype.CONTINUATION,
                        "branch": "continuation_rejected",
                    },
                )
            _trace(
                "rag_branch",
                branch="continuation",
                has_history=bool(history),
                next_offset=continuation.get("next_offset"),
                question_chars=len(question),
            )
            return await self._answer_broad_section(
                question=str(continuation.get("source_question") or normalized),
                filters=filters,
                timing=timing,
                total_start=total_start,
                continuation=continuation,
                trace={
                    "intent": Intent.FOLLOW_UP,
                    "subtype": FollowUpSubtype.CONTINUATION,
                    "branch": "continuation",
                },
            )
        if self.route_orchestrator is not None:
            routing = _routing_decision
            if routing is None:
                with measure_ms(timing, "router"):
                    routing = await self.route_orchestrator.route(
                        normalized,
                        history,
                        has_continuation=bool(continuation),
                    )
            intent = _intent_from_multistage(routing)
            retrieval_first = False
            trace.update(_routing_trace(routing))
        else:
            intent = self.intent_router.classify(normalized, has_history=bool(history))
            retrieval_first = _should_retrieve_before_routing(intent)
            if intent.intent == Intent.AMBIGUOUS and not retrieval_first:
                with measure_ms(timing, "router"):
                    intent = await self._route_with_llm(normalized, history, intent)
            trace.update(_intent_trace(intent))
        trace["retrieval_first"] = retrieval_first
        _trace(
            "rag_intent",
            intent=intent.intent,
            confidence=round(intent.confidence, 3),
            reason=intent.reason,
            subtype=intent.subtype,
            llm_router_used=intent.llm_router_used,
            has_history=bool(history),
            has_continuation=bool(continuation),
            question_chars=len(question),
        )
        if retrieval_first:
            intent = IntentDecision(
                Intent.KNOWLEDGE_QUERY,
                intent.confidence,
                f"retrieval_first:{intent.reason}",
                intent.subtype,
                intent.llm_router_used,
            )
        if intent.intent == Intent.CONVERSATIONAL:
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            _trace(
                "rag_response",
                branch="conversational_static",
                status="conversational",
                total_ms=timing["total"],
            )
            return _response(
                status="conversational",
                answer=CONVERSATIONAL_RESPONSE,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**trace, "branch": "conversational_static"},
            )
        if intent.intent in {Intent.CONVERSATIONAL_LLM, Intent.FOLLOW_UP}:
            if (
                intent.intent == Intent.FOLLOW_UP
                and intent.subtype == FollowUpSubtype.KNOWLEDGE_FOLLOW_UP
            ):
                rewrite_query = await self._rewrite_follow_up_query(normalized, history, timing)
                if not rewrite_query:
                    timing["total"] = int((time.perf_counter() - total_start) * 1000)
                    return _response(
                        status="clarify",
                        answer=CLARIFY_RESPONSE,
                        citations=[],
                        candidate_count=0,
                        context_count=0,
                        reranker_used=False,
                        timing=timing,
                        trace={**trace, "branch": "clarify", "rewrite_used": True},
                    )
                normalized = rewrite_query
                trace["rewrite_used"] = True
            else:
                return await self._answer_conversation(
                    normalized,
                    history,
                    timing,
                    total_start,
                    trace,
                    intent,
                )
        if intent.intent == Intent.CLARIFY:
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            _trace(
                "rag_response",
                branch="clarify",
                status="clarify",
                total_ms=timing["total"],
            )
            return _response(
                status="clarify",
                answer=CLARIFY_RESPONSE,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**trace, "branch": "clarify"},
            )
        if intent.intent == Intent.AMBIGUOUS:
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            _trace(
                "rag_response",
                branch="clarify",
                status="clarify",
                total_ms=timing["total"],
            )
            return _response(
                status="clarify",
                answer=CLARIFY_RESPONSE,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**trace, "branch": "clarify"},
            )
        if intent.intent == Intent.OUT_OF_SCOPE:
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            answer = _out_of_scope_response(normalized, history)
            _trace(
                "rag_response",
                branch="out_of_scope",
                status="out_of_scope",
                total_ms=timing["total"],
            )
            return _response(
                status="out_of_scope",
                answer=answer,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**trace, "branch": "out_of_scope"},
            )
        if filters_select_no_documents(filters):
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            _trace(
                "rag_response",
                branch="no_documents_selected",
                status="clarify",
                total_ms=timing["total"],
            )
            return _response(
                status="clarify",
                answer=NO_DOCUMENTS_SELECTED_RESPONSE,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**trace, "branch": "no_documents_selected"},
            )
        if intent.intent == Intent.BROAD_SECTION_QUERY:
            with measure_ms(timing, "retrieval"):
                retrieval = await self.retriever.retrieve(normalized, filters)
            best_score = retrieval.chunks[0].score if retrieval.chunks else 0.0
            _trace(
                "rag_retrieval",
                branch="broad_section",
                candidate_count=retrieval.candidate_count,
                best_score=round(best_score, 6),
                retrieval_ms=timing["retrieval"],
            )
            if should_refuse(
                retrieval.candidate_count,
                best_score,
                self.settings.min_retrieval_score,
            ):
                timing["total"] = int((time.perf_counter() - total_start) * 1000)
                return _response(
                    status=FALLBACK_STATUS,
                    answer=REFUSAL,
                    citations=[],
                    candidate_count=retrieval.candidate_count,
                    context_count=0,
                    reranker_used=False,
                    timing=timing,
                    trace={
                        **trace,
                        "branch": "broad_section_refusal",
                        "candidate_count": retrieval.candidate_count,
                        "context_count": 0,
                        "best_score": round(best_score, 6),
                    },
                )
            expansion = expand_section_chunks(
                retrieval.chunks,
                await self._expansion_source_chunks(retrieval.chunks),
                filters,
            )
            if expansion:
                return await self._answer_broad_section(
                    question=normalized,
                    filters=filters,
                    timing=timing,
                    total_start=total_start,
                    expansion_chunks=expansion.chunks,
                    document_id=expansion.document_id,
                    section_root=expansion.section_root,
                    candidate_count=retrieval.candidate_count,
                    trace={**trace, "branch": "broad_section"},
                )
        with measure_ms(timing, "retrieval"):
            adaptive = await self.adaptive_retriever.retrieve(
                normalized,
                filters,
                history,
            )
        retrieval = adaptive.retrieval
        best_score = retrieval.chunks[0].score if retrieval.chunks else 0.0
        selection = select_evidence(
            retrieval.chunks,
            self.settings.final_context_top_n,
            self.evidence_config,
            allow_cross_domain_ambiguity=False,
        )
        selected_chunk_ids = [chunk.chunk_id for chunk in selection.selected]
        rejected_chunks = {
            item.chunk.chunk_id: item.reason for item in selection.rejected
        }
        trace.update(
            {
                "adaptive_rewrite_used": adaptive.rewrite_used,
                "adaptive_rewrite_error": adaptive.rewrite_error,
                "retrieval_queries": list(adaptive.queries),
                "candidate_quality": selection.quality.reason,
                "selected_chunk_ids": selected_chunk_ids,
                "rejected_chunks": rejected_chunks,
            }
        )
        _trace(
            "rag_retrieval",
            branch="knowledge",
            candidate_count=retrieval.candidate_count,
            best_score=round(best_score, 6),
            retrieval_ms=timing["retrieval"],
            adaptive_rewrite_used=adaptive.rewrite_used,
            adaptive_rewrite_error=adaptive.rewrite_error,
            retrieval_queries=list(adaptive.queries),
            candidate_quality=selection.quality.reason,
        )
        if not selection.selected:
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            status = "clarify" if retrieval_first else FALLBACK_STATUS
            answer = CLARIFY_RESPONSE if retrieval_first else REFUSAL
            branch = "retrieval_first_clarify" if retrieval_first else "knowledge_refusal"
            _trace(
                "rag_response",
                branch=branch,
                status=status,
                candidate_count=retrieval.candidate_count,
                best_score=round(best_score, 6),
                total_ms=timing["total"],
            )
            return _response(
                status=status,
                answer=answer,
                citations=[],
                candidate_count=retrieval.candidate_count,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={
                    **trace,
                    "branch": branch,
                    "candidate_count": retrieval.candidate_count,
                    "context_count": 0,
                    "best_score": round(best_score, 6),
                },
            )

        context, selected = build_context(
            selection.selected,
            self.settings.max_context_tokens,
        )
        image_lookup = load_image_lookup(
            self.settings.documents_dir,
            {chunk.document_id for chunk in selected},
        )
        citations = build_citations(selected, image_lookup)
        available_sources = {citation.citation_id for citation in citations}
        _log_context_evidence("knowledge", normalized, retrieval.chunks, selected)
        literal_result: CriticalLiteralValidation | None = None
        with measure_ms(timing, "llm"):
            user_prompt = build_user_prompt(normalized, context, history)
            raw_answer = await self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
            _trace("rag_llm_raw", branch="knowledge", output=raw_answer[:2000])
            parsed = parse_model_output(
                raw_answer,
                available_sources,
                allowed_statuses=RAG_STATUSES,
            )
            if not parsed.is_valid:
                retry_prompt = build_retry_prompt(
                    normalized,
                    context,
                    parsed.error or "invalid_output",
                    history,
                )
                raw_answer = await self.llm_provider.generate(SYSTEM_PROMPT, retry_prompt)
                _trace("rag_llm_raw", branch="knowledge_retry", output=raw_answer[:2000])
                parsed = parse_model_output(
                    raw_answer,
                    available_sources,
                    allowed_statuses=RAG_STATUSES,
                )
            literal_result = _validate_literal_support(parsed, citations)

        if literal_result and not literal_result.passed:
            status = "generation_failed"
            answer = GENERATION_FAILED_RESPONSE
            response_citations = _citations_for_sources(citations, parsed.sources)
        elif parsed.is_valid:
            status = parsed.status
            answer = parsed.answer
            response_citations = _citations_for_sources(citations, parsed.sources)
        else:
            status = "generation_failed"
            answer = GENERATION_FAILED_RESPONSE
            response_citations = []

        timing["total"] = int((time.perf_counter() - total_start) * 1000)
        _trace(
            "rag_response",
            branch="knowledge",
            status=status,
            candidate_count=retrieval.candidate_count,
            context_count=len(selected),
            citation_count=len(response_citations),
            llm_ms=timing["llm"],
            total_ms=timing["total"],
            parse_error=parsed.error,
            literal_validation_error=_literal_validation_error(literal_result),
        )
        return _response(
            status=status,
            answer=answer,
            citations=response_citations,
            candidate_count=retrieval.candidate_count,
            context_count=len(selected),
            reranker_used=retrieval.reranker_used,
            timing=timing,
            trace={
                **trace,
                "branch": "knowledge",
                "candidate_count": retrieval.candidate_count,
                "context_count": len(selected),
                "best_score": round(best_score, 6),
                "parse_error": parsed.error,
                "adaptive_rewrite_used": adaptive.rewrite_used,
                "adaptive_rewrite_error": adaptive.rewrite_error,
                "retrieval_queries": list(adaptive.queries),
                "candidate_quality": selection.quality.reason,
                "selected_chunk_ids": selected_chunk_ids,
                "rejected_chunks": rejected_chunks,
                "literal_validation_error": _literal_validation_error(literal_result),
            },
        )

    async def answer_stream(
        self,
        question: str,
        filters: RetrievalFilters | None = None,
        history: list[dict[str, str]] | None = None,
        continuation: dict[str, object] | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        history = history or []
        normalized = self.normalizer.normalize(question)
        yield _stream_event("progress", {"stage": "routing", "message": "Đang phân loại câu hỏi."})
        if _is_category_only_after_clarify(normalized, history):
            response = await self.answer(question, filters, history, continuation)
            yield _stream_event("final", response)
            return

        if continuation and _is_continue_request(normalized):
            yield _stream_event(
                "progress",
                {"stage": "retrieval", "message": "Đang lấy phần nội dung tiếp theo."},
            )
            response = await self.answer(question, filters, history, continuation)
            yield _stream_event("final", response)
            return

        if self.route_orchestrator is not None:
            routing = await self.route_orchestrator.route(
                normalized,
                history,
                has_continuation=bool(continuation),
            )
            intent = _intent_from_multistage(routing)
            if _is_streamable_conversation_intent(intent):
                timing: dict[str, int] = {
                    "router": 0,
                    "rewrite": 0,
                    "retrieval": 0,
                    "rerank": 0,
                    "llm": 0,
                    "total": 0,
                }
                total_start = time.perf_counter()
                trace = {
                    **_routing_trace(routing),
                    "retrieval_first": False,
                    "branch": "conversation_stream",
                }
                answer_parts: list[str] = []
                yield _stream_event(
                    "progress",
                    {"stage": "generation", "message": "Đang tạo câu trả lời."},
                )
                with measure_ms(timing, "llm"):
                    user_prompt = build_conversation_stream_prompt(normalized, history)
                    async for token in self.llm_provider.stream_generate(
                        CONVERSATIONAL_STREAM_SYSTEM_PROMPT,
                        user_prompt,
                    ):
                        answer_parts.append(token)
                answer = "".join(answer_parts).strip() or CONVERSATIONAL_RESPONSE
                if contains_disallowed_cjk(answer):
                    answer = OUT_OF_SCOPE_RESPONSE
                yield _stream_event("delta", {"text": answer})
                timing["total"] = int((time.perf_counter() - total_start) * 1000)
                yield _stream_event(
                    "final",
                    _response(
                        status="conversational",
                        answer=answer,
                        citations=[],
                        candidate_count=0,
                        context_count=0,
                        reranker_used=False,
                        timing=timing,
                        trace=trace,
                    ),
                )
                return
            progress = _progress_for_non_streamed_intent(intent)
            if progress:
                yield _stream_event("progress", progress)
            response = await self.answer(
                question,
                filters,
                history,
                continuation,
                _routing_decision=routing,
            )
            yield _stream_event("final", response)
            return

        intent = self.intent_router.classify(normalized, has_history=bool(history))
        if filters_select_no_documents(filters) and intent.intent in {
            Intent.BROAD_SECTION_QUERY,
            Intent.KNOWLEDGE_QUERY,
        }:
            response = await self.answer(question, filters, history, continuation)
            yield _stream_event("final", response)
            return
        if _is_streamable_conversation_intent(intent):
            timing: dict[str, int] = {
                "router": 0,
                "rewrite": 0,
                "retrieval": 0,
                "rerank": 0,
                "llm": 0,
                "total": 0,
            }
            total_start = time.perf_counter()
            trace = {**_intent_trace(intent), "branch": "conversation_stream"}
            answer_parts: list[str] = []
            yield _stream_event(
                "progress",
                {"stage": "generation", "message": "Đang tạo câu trả lời."},
            )
            with measure_ms(timing, "llm"):
                user_prompt = build_conversation_stream_prompt(normalized, history)
                async for token in self.llm_provider.stream_generate(
                    CONVERSATIONAL_STREAM_SYSTEM_PROMPT,
                    user_prompt,
                ):
                    answer_parts.append(token)
            answer = "".join(answer_parts).strip() or CONVERSATIONAL_RESPONSE
            if contains_disallowed_cjk(answer):
                answer = OUT_OF_SCOPE_RESPONSE
            yield _stream_event("delta", {"text": answer})
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            yield _stream_event(
                "final",
                _response(
                    status="conversational",
                    answer=answer,
                    citations=[],
                    candidate_count=0,
                    context_count=0,
                    reranker_used=False,
                    timing=timing,
                    trace=trace,
                ),
            )
            return

        progress = _progress_for_non_streamed_intent(intent)
        if progress:
            yield _stream_event("progress", progress)
        response = await self.answer(question, filters, history, continuation)
        yield _stream_event("final", response)

    async def _answer_conversation(
        self,
        question: str,
        history: list[dict[str, str]],
        timing: dict[str, int],
        total_start: float,
        trace: dict[str, object],
        intent: IntentDecision,
    ) -> dict[str, object]:
        _trace("rag_branch", branch="conversation_llm", intent=intent.intent)
        with measure_ms(timing, "llm"):
            user_prompt = build_conversation_prompt(question, history)
            raw_answer = await self.llm_provider.generate(
                CONVERSATIONAL_SYSTEM_PROMPT,
                user_prompt,
            )
            parsed = parse_model_output(
                raw_answer,
                set(),
                allowed_statuses=CONVERSATIONAL_STATUSES,
            )
            if not parsed.is_valid:
                retry_prompt = (
                    f"{user_prompt}\n\nLan tra loi truoc khong hop le vi: "
                    f"{parsed.error or 'invalid_output'}. "
                    "Hay tra loi lai chi bang JSON hop le."
                )
                raw_answer = await self.llm_provider.generate(
                    CONVERSATIONAL_SYSTEM_PROMPT,
                    retry_prompt,
                )
                parsed = parse_model_output(
                    raw_answer,
                    set(),
                    allowed_statuses=CONVERSATIONAL_STATUSES,
                )
        timing["total"] = int((time.perf_counter() - total_start) * 1000)
        if parsed.is_valid:
            _trace(
                "rag_response",
                branch="conversation_llm",
                status=parsed.status,
                parse_error=None,
                llm_ms=timing["llm"],
                total_ms=timing["total"],
            )
            return _response(
                status=parsed.status,
                answer=parsed.answer,
                citations=[],
                candidate_count=0,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**trace, "branch": "conversation_llm"},
            )
        _trace(
            "rag_response",
            branch="conversation_llm",
            status="conversational",
            parse_error=parsed.error,
            llm_ms=timing["llm"],
            total_ms=timing["total"],
        )
        return _response(
            status="conversational",
            answer=(
                "Minh chi co the chac trong pham vi tai lieu noi bo va nguon da duoc trich dan. "
                "Hien minh chua du ngu canh hoi thoai de doi chieu chi tiet."
            ),
            citations=[],
            candidate_count=0,
            context_count=0,
            reranker_used=False,
            timing=timing,
            trace={**trace, "branch": "conversation_llm", "parse_error": parsed.error},
        )

    async def _route_with_llm(
        self,
        question: str,
        history: list[dict[str, str]],
        fallback: IntentDecision,
    ) -> IntentDecision:
        try:
            raw_answer = await self.llm_provider.generate(
                ROUTER_SYSTEM_PROMPT,
                build_router_prompt(question, history),
            )
        except Exception:  # noqa: BLE001
            return fallback
        routed = parse_router_output(raw_answer)
        if routed is None:
            return IntentDecision(
                Intent.CLARIFY,
                0.5,
                "llm_router_invalid_output",
                llm_router_used=True,
            )
        return routed

    async def _rewrite_follow_up_query(
        self,
        question: str,
        history: list[dict[str, str]],
        timing: dict[str, int],
    ) -> str:
        with measure_ms(timing, "rewrite"):
            try:
                raw_answer = await self.llm_provider.generate(
                    QUERY_REWRITE_SYSTEM_PROMPT,
                    build_query_rewrite_prompt(question, history),
                )
            except Exception:  # noqa: BLE001
                return ""
        return parse_query_rewrite_output(raw_answer)

    async def _expansion_source_chunks(
        self,
        anchor_chunks: list[Chunk],
        document_id: str | None = None,
    ) -> list[Chunk]:
        target_document_id = document_id or (anchor_chunks[0].document_id if anchor_chunks else "")
        if target_document_id and hasattr(self.retriever, "document_chunks"):
            return await self.retriever.document_chunks(target_document_id)
        return await self.retriever.all_chunks()

    async def _answer_broad_section(
        self,
        question: str,
        filters: RetrievalFilters | None,
        timing: dict[str, int],
        total_start: float,
        trace: dict[str, object] | None = None,
        expansion_chunks: list[Chunk] | None = None,
        document_id: str | None = None,
        section_root: str | None = None,
        candidate_count: int = 0,
        continuation: dict[str, object] | None = None,
    ) -> dict[str, object]:
        offset = 0
        if continuation:
            document_id = str(continuation.get("document_id") or "")
            section_root = str(continuation.get("section_root") or "")
            offset = int(continuation.get("next_offset") or 0)
            with measure_ms(timing, "retrieval"):
                expansion = expand_section_chunks(
                    [],
                    await self._expansion_source_chunks([], document_id=document_id),
                    filters,
                    document_id=document_id,
                    section_root=section_root,
                )
            if not expansion:
                timing["total"] = int((time.perf_counter() - total_start) * 1000)
                return _response(
                    status=FALLBACK_STATUS,
                    answer=REFUSAL,
                    citations=[],
                    candidate_count=0,
                    context_count=0,
                    reranker_used=False,
                    timing=timing,
                    trace={**(trace or {}), "branch": "broad_section_refusal"},
                )
            expansion_chunks = expansion.chunks
            document_id = expansion.document_id
            section_root = expansion.section_root

        if not expansion_chunks or not document_id or not section_root:
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            return _response(
                status=FALLBACK_STATUS,
                answer=REFUSAL,
                citations=[],
                candidate_count=candidate_count,
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={**(trace or {}), "branch": "broad_section_refusal"},
            )

        if offset >= len(expansion_chunks):
            timing["total"] = int((time.perf_counter() - total_start) * 1000)
            _trace(
                "rag_response",
                branch="broad_section_exhausted",
                status="conversational",
                total_chunks=len(expansion_chunks),
                offset=offset,
                total_ms=timing["total"],
            )
            return _response(
                status="conversational",
                answer="Da het noi dung de hien thi tiep.",
                citations=[],
                candidate_count=candidate_count or len(expansion_chunks),
                context_count=0,
                reranker_used=False,
                timing=timing,
                trace={
                    **(trace or {}),
                    "branch": "broad_section_exhausted",
                    "candidate_count": candidate_count or len(expansion_chunks),
                    "context_count": 0,
                },
            )

        context, selected = build_context(
            expansion_chunks[offset:],
            self.settings.broad_max_context_tokens,
        )
        has_more = offset + len(selected) < len(expansion_chunks)
        _trace(
            "rag_context",
            branch="broad_section",
            total_chunks=len(expansion_chunks),
            selected_chunks=len(selected),
            offset=offset,
            has_more=has_more,
        )
        image_lookup = load_image_lookup(
            self.settings.documents_dir,
            {chunk.document_id for chunk in selected},
        )
        citations = build_citations(selected, image_lookup)
        available_sources = {citation.citation_id for citation in citations}
        _log_context_evidence("broad_section", question, expansion_chunks, selected)
        literal_result: CriticalLiteralValidation | None = None
        with measure_ms(timing, "llm"):
            user_prompt = build_broad_user_prompt(question, context, has_more)
            raw_answer = await self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
            _trace("rag_llm_raw", branch="broad_section", output=raw_answer[:2000])
            parsed = parse_model_output(
                raw_answer,
                available_sources,
                allowed_statuses=RAG_STATUSES,
            )
            if not parsed.is_valid:
                retry_prompt = build_broad_retry_prompt(
                    question,
                    context,
                    has_more,
                    parsed.error or "invalid_output",
                )
                raw_answer = await self.llm_provider.generate(SYSTEM_PROMPT, retry_prompt)
                _trace("rag_llm_raw", branch="broad_section_retry", output=raw_answer[:2000])
                parsed = parse_model_output(
                    raw_answer,
                    available_sources,
                    allowed_statuses=RAG_STATUSES,
                )
            literal_result = _validate_literal_support(parsed, citations)

        if literal_result and not literal_result.passed:
            status = "generation_failed"
            answer = GENERATION_FAILED_RESPONSE
            response_citations = _citations_for_sources(citations, parsed.sources)
        elif parsed.is_valid:
            status = parsed.status
            answer = parsed.answer
            response_citations = _citations_for_sources(citations, parsed.sources)
        else:
            status = "generation_failed"
            answer = GENERATION_FAILED_RESPONSE
            response_citations = []

        next_continuation = None
        if has_more and parsed.is_valid and status != "generation_failed":
            next_continuation = {
                "has_more": True,
                "mode": "broad_section",
                "document_id": document_id,
                "section_root": section_root,
                "next_offset": offset + len(selected),
                "source_question": question,
            }
            next_continuation["token"] = self.sign_continuation(next_continuation)
        timing["total"] = int((time.perf_counter() - total_start) * 1000)
        _trace(
            "rag_response",
            branch="broad_section",
            status=status,
            context_count=len(selected),
            citation_count=len(response_citations),
            has_more=bool(next_continuation),
            llm_ms=timing["llm"],
            total_ms=timing["total"],
            parse_error=parsed.error,
            literal_validation_error=_literal_validation_error(literal_result),
        )
        return _response(
            status=status,
            answer=answer,
            citations=response_citations,
            candidate_count=candidate_count or len(expansion_chunks),
            context_count=len(selected),
            reranker_used=False,
            timing=timing,
            continuation=next_continuation,
            trace={
                **(trace or {}),
                "branch": "broad_section",
                "candidate_count": candidate_count or len(expansion_chunks),
                "context_count": len(selected),
                "parse_error": parsed.error,
                "literal_validation_error": _literal_validation_error(literal_result),
            },
        )

    def sign_continuation(self, continuation: dict[str, object]) -> str:
        payload = _continuation_payload(continuation)
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hmac.new(
            self.settings.continuation_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify_continuation(self, continuation: dict[str, object]) -> bool:
        token = continuation.get("token")
        if not isinstance(token, str) or not token:
            return False
        expected = self.sign_continuation(continuation)
        return hmac.compare_digest(token, expected)


def parse_model_output(
    output: str,
    available_sources: set[str] | None = None,
    allowed_statuses: set[str] | None = None,
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
    statuses = allowed_statuses or VALID_STATUSES
    if not isinstance(status, str) or status not in statuses:
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
    if contains_disallowed_cjk(answer):
        return _invalid("disallowed_language")

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


def parse_router_output(output: str) -> IntentDecision | None:
    cleaned = _strip_json_fence(output.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    intent_value = data.get("intent")
    if not isinstance(intent_value, str):
        return None
    intent_map = {
        "conversational_llm": Intent.CONVERSATIONAL_LLM,
        "follow_up": Intent.FOLLOW_UP,
        "broad_section_query": Intent.BROAD_SECTION_QUERY,
        "knowledge_query": Intent.KNOWLEDGE_QUERY,
        "out_of_scope": Intent.OUT_OF_SCOPE,
        "clarify": Intent.CLARIFY,
    }
    intent = intent_map.get(intent_value)
    if intent is None:
        return None

    subtype = _parse_follow_up_subtype(data.get("subtype"))
    confidence = data.get("confidence")
    if not isinstance(confidence, int | float):
        confidence = 0.55
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "llm_router"
    return IntentDecision(
        intent=intent,
        confidence=max(0.0, min(1.0, float(confidence))),
        reason=reason[:120],
        subtype=subtype,
        llm_router_used=True,
    )


def parse_query_rewrite_output(output: str) -> str:
    cleaned = _strip_json_fence(output.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    query = data.get("query")
    if not isinstance(query, str):
        return ""
    return query.strip()[:500]


def _invalid(error: str) -> ParsedModelOutput:
    return ParsedModelOutput(
        status=FALLBACK_STATUS,
        answer="",
        sources=[],
        is_valid=False,
        error=error,
    )


def _parse_follow_up_subtype(value: object) -> FollowUpSubtype:
    if not isinstance(value, str):
        return FollowUpSubtype.NONE
    try:
        return FollowUpSubtype(value)
    except ValueError:
        return FollowUpSubtype.NONE


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


def _validate_literal_support(
    parsed: ParsedModelOutput,
    citations: list[Citation],
) -> CriticalLiteralValidation | None:
    if not parsed.is_valid or parsed.status not in SOURCE_REQUIRED_STATUSES:
        return None
    cited_context = _cited_context(citations, parsed.sources)
    if not cited_context:
        return None
    return validate_critical_literals(parsed.answer, cited_context)


def _literal_validation_error(
    result: CriticalLiteralValidation | None,
) -> str | None:
    if result is None or result.passed:
        return None
    return f"unsupported_literal:{','.join(result.unsupported)}"


def _cited_context(citations: list[Citation], sources: list[str]) -> str:
    return "\n\n".join(citation.content for citation in _citations_for_sources(citations, sources))


def _log_context_evidence(
    branch: str,
    query: str,
    retrieved_chunks: list[Chunk],
    selected_chunks: list[Chunk],
) -> None:
    _trace(
        "rag_context_evidence",
        branch=branch,
        query=query,
        retrieved=[
            _chunk_evidence(chunk)
            for chunk in retrieved_chunks[:5]
        ],
        selected=[_chunk_evidence(chunk) for chunk in selected_chunks],
    )


def _chunk_evidence(chunk: Chunk) -> dict[str, object]:
    signals = chunk.retrieval
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "domain": chunk.domain,
        "section": chunk.section,
        "score": round(chunk.score, 6),
        "dense_score": (
            round(signals.dense_score, 6)
            if signals.dense_score is not None
            else None
        ),
        "dense_rank": signals.dense_rank,
        "bm25_score": (
            round(signals.bm25_score, 6)
            if signals.bm25_score is not None
            else None
        ),
        "bm25_rank": signals.bm25_rank,
        "rrf_score": (
            round(signals.rrf_score, 6)
            if signals.rrf_score is not None
            else None
        ),
        "matched_queries": list(signals.matched_queries),
        "excerpt": _shorten(chunk.content, 500),
    }


def _shorten(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


def _is_continue_request(question: str) -> bool:
    normalized = normalize_for_intent(question)
    return normalized in {
        "tiep",
        "xem tiep",
        "tiep di",
        "noi tiep",
        "tiep nhe",
        "xem tiep nhe",
        "noi tiep di",
        "continue",
        "next",
    }


def _is_category_only_after_clarify(question: str, history: list[dict[str, str]]) -> bool:
    if not _last_assistant_was_clarify(history):
        return False
    normalized = normalize_for_intent(question)
    normalized = _strip_polite_suffix(normalized)
    return normalized in {
        "nas",
        "outlook",
        "email",
        "mail",
        "windows",
        "sop",
        "faq",
        "quy trinh",
        "quy trinh noi bo",
    }


def _last_assistant_was_clarify(history: list[dict[str, str]]) -> bool:
    for message in reversed(history):
        if message.get("role") != "assistant":
            continue
        content = normalize_for_intent(str(message.get("content", "")))
        return (
            "ban dang gap van de voi phan nao" in content
            or "ban muon tra cuu noi dung cu the nao" in content
        )
    return False


def _strip_polite_suffix(value: str) -> str:
    tokens = value.split()
    while tokens and tokens[-1] in {"nhe", "nha", "di", "voi", "a"}:
        tokens.pop()
    return " ".join(tokens)


def _out_of_scope_response(question: str, history: list[dict[str, str]]) -> str:
    normalized = normalize_for_intent(question)
    if _recent_out_of_scope_count(history) >= 2:
        return REPEATED_OUT_OF_SCOPE_RESPONSE
    if _is_personal_emotion_query(normalized):
        return OUT_OF_SCOPE_EMOTION_RESPONSE
    if _is_personal_leisure_query(normalized):
        return OUT_OF_SCOPE_LEISURE_RESPONSE
    return OUT_OF_SCOPE_RESPONSE


def _recent_out_of_scope_count(history: list[dict[str, str]]) -> int:
    count = 0
    for message in reversed(history[-6:]):
        if message.get("role") != "assistant":
            continue
        content = normalize_for_intent(str(message.get("content", "")))
        if _looks_like_out_of_scope_response(content):
            count += 1
    return count


def _looks_like_out_of_scope_response(content: str) -> bool:
    return (
        "ngoai pham vi" in content
        or "khong phai tro ly tu van ca nhan" in content
        or "chua ho tro len ke hoach ca nhan" in content
        or "nhieu cau hoi ngoai pham vi" in content
    )


def _is_personal_emotion_query(normalized: str) -> bool:
    return any(
        term in normalized
        for term in {
            "toi buon",
            "minh buon",
            "em buon",
            "anh buon",
            "chi buon",
            "toi chan",
            "minh chan",
            "em chan",
            "toi met",
            "minh met",
            "toi stress",
            "minh stress",
            "toi co don",
            "minh co don",
            "tam su",
            "an ui",
            "tu van tam ly",
        }
    )


def _is_personal_leisure_query(normalized: str) -> bool:
    return any(
        term in normalized
        for term in {
            "di choi",
            "di du lich",
            "du lich",
            "di da nang",
            "len plan",
            "lich trinh",
            "khach san",
            "tour",
            "ve may bay",
        }
    )


def _is_streamable_conversation_intent(intent: IntentDecision) -> bool:
    return intent.intent == Intent.FOLLOW_UP and intent.subtype in {
        FollowUpSubtype.SOURCE_CHALLENGE,
        FollowUpSubtype.CONTINUATION,
        FollowUpSubtype.CASUAL_FOLLOW_UP,
    }


def _should_retrieve_before_routing(intent: IntentDecision) -> bool:
    if intent.intent == Intent.AMBIGUOUS:
        return True
    if intent.intent == Intent.OUT_OF_SCOPE:
        return intent.reason == "non_domain_statement" and intent.confidence <= 0.6
    if intent.intent == Intent.CONVERSATIONAL_LLM:
        return intent.reason == "follow_up_term_without_history"
    return False


def _progress_for_non_streamed_intent(intent: IntentDecision) -> dict[str, str] | None:
    if intent.intent in {Intent.KNOWLEDGE_QUERY, Intent.BROAD_SECTION_QUERY}:
        return {
            "stage": "retrieval",
            "message": (
                "\u0110ang tra c\u1ee9u v\u00e0 "
                "\u0111\u1ed1i chi\u1ebfu t\u00e0i li\u1ec7u."
            ),
        }
    if intent.intent == Intent.FOLLOW_UP and intent.subtype == FollowUpSubtype.KNOWLEDGE_FOLLOW_UP:
        return {
            "stage": "retrieval",
            "message": (
                "\u0110ang vi\u1ebft l\u1ea1i c\u00e2u h\u1ecfi "
                "v\u00e0 tra c\u1ee9u t\u00e0i li\u1ec7u."
            ),
        }
    if intent.intent == Intent.AMBIGUOUS:
        return {
            "stage": "routing",
            "message": (
                "\u0110ang ph\u00e2n lo\u1ea1i th\u00eam "
                "ng\u1eef c\u1ea3nh c\u00e2u h\u1ecfi."
            ),
        }
    return None


def _stream_event(event: str, data: dict[str, object]) -> dict[str, object]:
    return {"event": event, "data": data}


def _continuation_payload(continuation: dict[str, object]) -> dict[str, object]:
    return {field: continuation.get(field) for field in CONTINUATION_FIELDS}


def _intent_trace(intent: IntentDecision) -> dict[str, object]:
    return {
        "intent": intent.intent,
        "subtype": intent.subtype,
        "confidence": round(intent.confidence, 3),
        "reason": intent.reason,
        "llm_router_used": intent.llm_router_used,
    }


def _intent_from_multistage(routing: RoutingDecision) -> IntentDecision:
    classification = routing.classification
    capability = routing.capability.capability
    if capability == Capability.RAG:
        if classification.intent == RequestIntent.SUMMARIZE_SECTION:
            intent = Intent.BROAD_SECTION_QUERY
            subtype = FollowUpSubtype.NONE
        elif classification.turn_kind == TurnKind.FOLLOW_UP:
            intent = Intent.FOLLOW_UP
            subtype = FollowUpSubtype.KNOWLEDGE_FOLLOW_UP
        else:
            intent = Intent.KNOWLEDGE_QUERY
            subtype = FollowUpSubtype.NONE
    elif capability == Capability.CONVERSATION:
        if classification.intent == RequestIntent.CONVERSATION_REPAIR:
            intent = Intent.FOLLOW_UP
            subtype = FollowUpSubtype.CASUAL_FOLLOW_UP
        elif classification.intent == RequestIntent.CONTINUE_PREVIOUS:
            intent = Intent.FOLLOW_UP
            subtype = FollowUpSubtype.CONTINUATION
        else:
            intent = Intent.CONVERSATIONAL_LLM
            subtype = FollowUpSubtype.NONE
    elif capability == Capability.UNSUPPORTED:
        intent = Intent.OUT_OF_SCOPE
        subtype = FollowUpSubtype.NONE
    else:
        intent = Intent.CLARIFY
        subtype = FollowUpSubtype.NONE
    return IntentDecision(
        intent=intent,
        confidence=routing.capability.confidence,
        reason=f"multistage:{routing.capability.reason}",
        subtype=subtype,
        llm_router_used=routing.qwen_used,
    )


def _routing_trace(routing: RoutingDecision) -> dict[str, object]:
    classification = routing.classification
    return {
        "intent": classification.intent,
        "subtype": classification.turn_kind,
        "confidence": round(classification.confidence, 3),
        "reason": classification.reason,
        "llm_router_used": routing.qwen_used,
        "turn_kind": routing.turn.kind,
        "turn_reason": routing.turn.reason,
        "route_affinity": classification.affinity,
        "route_classifier": classification.classifier,
        "route_top_score": classification.top_score,
        "route_margin": classification.margin,
        "route_subject": classification.subject,
        "capability": routing.capability.capability,
        "capability_reason": routing.capability.reason,
    }


def _trace(event: str, **fields: object) -> None:
    logger.info("%s %s", event, json.dumps(fields, ensure_ascii=False, default=str))


def _response(
    status: str,
    answer: str,
    citations: list[Citation],
    candidate_count: int,
    context_count: int,
    reranker_used: bool,
    timing: dict[str, int],
    continuation: dict[str, object] | None = None,
    trace: dict[str, object] | None = None,
) -> dict[str, object]:
    response: dict[str, object] = {
        "status": status,
        "answer": answer,
        "citations": [asdict(citation) for citation in citations],
        "retrieval": {
            "candidate_count": candidate_count,
            "context_count": context_count,
            "reranker_used": reranker_used,
        },
        "timing_ms": timing,
    }
    if continuation:
        response["continuation"] = continuation
    if trace:
        response["trace"] = _clean_trace(trace)
    return response


def _clean_trace(trace: dict[str, object]) -> dict[str, object]:
    allowed = {
        "intent",
        "subtype",
        "confidence",
        "reason",
        "branch",
        "turn_kind",
        "turn_reason",
        "route_affinity",
        "route_classifier",
        "route_top_score",
        "route_margin",
        "route_subject",
        "capability",
        "capability_reason",
        "candidate_count",
        "context_count",
        "best_score",
        "parse_error",
        "literal_validation_error",
        "rewrite_used",
        "llm_router_used",
        "retrieval_first",
        "adaptive_rewrite_used",
        "adaptive_rewrite_error",
        "retrieval_queries",
        "candidate_quality",
        "selected_chunk_ids",
        "rejected_chunks",
    }
    cleaned: dict[str, object] = {}
    for key in allowed:
        value = trace.get(key)
        if isinstance(value, StrEnum):
            cleaned[key] = value.value
        elif isinstance(value, int | float | str | bool) or value is None:
            cleaned[key] = value
        elif key in {"retrieval_queries", "selected_chunk_ids"} and isinstance(value, list):
            cleaned[key] = [item for item in value if isinstance(item, str)]
        elif key == "rejected_chunks" and isinstance(value, dict):
            cleaned[key] = {
                str(chunk_id): str(reason)
                for chunk_id, reason in value.items()
                if isinstance(chunk_id, str) and isinstance(reason, str)
            }
    return cleaned
