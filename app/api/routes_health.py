from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_embedding_provider, get_vector_store
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    qdrant_status = "configured"
    try:
        await get_vector_store().client.get_collections()
        qdrant_status = "connected"
    except Exception:  # noqa: BLE001
        qdrant_status = "unavailable"
    return {
        "status": "ok",
        "qdrant": qdrant_status,
        "llm_provider": settings.llm_provider,
        "embedding_provider": type(get_embedding_provider()).__name__,
    }

