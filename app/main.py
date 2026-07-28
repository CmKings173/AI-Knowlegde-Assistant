from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes_chat import router as chat_router
from app.api.routes_documents import router as documents_router
from app.api.routes_health import router as health_router
from app.config import get_settings
from app.domain.exceptions import ApplicationError
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="AI Knowledge Assistant", version="0.1.0")
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    return app


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    logging.exception("application_error")
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": exc.code, "message": exc.user_message},
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.exception("unhandled_error")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Hệ thống đang tạm thời không khả dụng.",
            },
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


app = create_app()
