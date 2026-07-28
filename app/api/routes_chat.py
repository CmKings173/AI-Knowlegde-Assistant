from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import get_rag_pipeline
from app.api.schemas import ChatRequest, ChatResponse
from app.config import get_settings

router = APIRouter(prefix="/api/v1")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> dict[str, object]:
    settings = get_settings()
    if len(request.question) > settings.max_question_chars:
        raise HTTPException(status_code=422, detail="Question is too long")
    return await get_rag_pipeline().answer(request.question, request.retrieval_filters())


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
