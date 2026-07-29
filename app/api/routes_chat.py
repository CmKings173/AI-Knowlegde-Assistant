from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_rag_pipeline
from app.api.schemas import ChatRequest, ChatResponse
from app.config import get_settings

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> dict[str, object]:
    settings = get_settings()
    if len(request.question) > settings.max_question_chars:
        raise HTTPException(status_code=422, detail="Question is too long")
    return await get_rag_pipeline().answer(
        request.question,
        request.retrieval_filters(),
        request.sanitized_history(settings.max_history_messages, settings.max_history_chars),
        request.continuation.model_dump() if request.continuation else None,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    settings = get_settings()
    if len(request.question) > settings.max_question_chars:
        raise HTTPException(status_code=422, detail="Question is too long")

    async def event_source() -> AsyncIterator[str]:
        history = request.sanitized_history(
            settings.max_history_messages,
            settings.max_history_chars,
        )
        try:
            async for item in get_rag_pipeline().answer_stream(
                request.question,
                request.retrieval_filters(),
                history,
                request.continuation.model_dump() if request.continuation else None,
            ):
                yield _format_sse(str(item["event"]), item["data"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat_stream_error")
            error_payload = {"message": "Không xử lý được yêu cầu hiện tại."}
            if settings.debug_endpoints_enabled:
                error_payload["detail"] = type(exc).__name__
            yield _format_sse("error", error_payload)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/debug/retrieve")
async def debug_retrieve(request: ChatRequest) -> dict[str, object]:
    settings = get_settings()
    if not settings.debug_endpoints_enabled:
        raise HTTPException(status_code=404, detail="Debug endpoint is disabled")
    pipeline = get_rag_pipeline()
    normalized = pipeline.normalizer.normalize(request.question)
    result = await pipeline.retriever.retrieve(normalized, request.retrieval_filters())
    return {
        "candidate_count": result.candidate_count,
        "candidates": [
            {"score": chunk.score, "metadata": chunk.payload()} for chunk in result.chunks
        ],
    }


def _format_sse(event: str, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
