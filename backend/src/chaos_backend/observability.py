"""Structured logging configuration for the backend.

Configures structlog once per process so the dashboard, the gRPC server,
and the CLI all emit JSON lines with consistent fields:

    {"event": "request", "level": "info", "timestamp": "2026-05-19T...",
     "request_id": "rq_a1b2c3d4", "method": "POST", "path": "/play", ...}

`configure_logging(level="INFO", pretty=False)` is the public entry. The
pretty mode swaps the JSON renderer for the human-friendly console
renderer, useful for local development.

The request_id is generated per request by the FastAPI middleware in
chaos_backend.web.middleware and bound to the thread-local context
variables so any logger called inside the request handler picks it up.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def configure_logging(level: str = "INFO", *, pretty: bool = False) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        force=True,
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if pretty:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        processors=processors,
        cache_logger_on_first_use=True,
    )


def new_request_id() -> str:
    return "rq_" + secrets.token_hex(4)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Bind a request_id to the structlog contextvars, emit one access
    log per request with method, path, status, and duration_ms."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        logger = structlog.get_logger("chaos_backend.web")

        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(elapsed_ms, 2),
            )
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(elapsed_ms, 2),
        )
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response
