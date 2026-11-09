from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llm_gateway.api.routes import chat_completions, health, models, responses, usage
from llm_gateway.core.config import load_gateway_config
from llm_gateway.core.errors import GatewayError
from llm_gateway.core.runtime import build_runtime, mount_runtime, unmount_runtime


def create_app(
    *,
    config_path: str | Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config = load_gateway_config(config_path)
        http = httpx.AsyncClient(transport=transport) if transport else None
        runtime = await build_runtime(config, http_client=http)
        mount_runtime(app, runtime)
        try:
            yield
        finally:
            await runtime.close()
            unmount_runtime(app)

    app = FastAPI(
        title="LLM Gateway",
        version="0.1.0",
        description=(
            "Text-only OpenAI-compatible gateway with ordered provider fallback, "
            "API-key identity, SQLite usage records, and structured traces."
        ),
        lifespan=lifespan,
    )
    config = load_gateway_config(config_path)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any):
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.message,
                    "type": "gateway_error",
                    "code": exc.code,
                    "request_id": getattr(request.state, "request_id", None),
                    "details": exc.details,
                }
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            {
                "loc": list(error.get("loc", [])),
                "message": error.get("msg"),
                "type": error.get("type"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "request validation failed",
                    "type": "validation_error",
                    "code": "invalid_request",
                    "request_id": getattr(request.state, "request_id", None),
                    "details": {"errors": errors},
                }
            },
        )

    app.include_router(chat_completions.router)
    app.include_router(responses.router)
    app.include_router(models.router)
    app.include_router(usage.router)
    app.include_router(health.router)
    return app


app = create_app()
