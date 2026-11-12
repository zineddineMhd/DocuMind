"""Schéma d'erreur homogène : {"error": {"code", "message", "request_id"}}."""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("documind")

DEFAULT_CODES = {
    400: "bad_request", 401: "unauthenticated", 403: "forbidden", 404: "not_found", 409: "conflict",
    413: "file_too_large", 415: "unsupported_media_type", 422: "validation_error", 429: "rate_limited",
    502: "upstream_error", 503: "service_unavailable",
}


class AppError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        self.status = status
        self.message = message
        self.code = code or DEFAULT_CODES.get(status, "error")


def _payload(request: Request, status: int, code: str, message: str, details=None) -> JSONResponse:
    rid = getattr(request.state, "request_id", "")
    body = {"error": {"code": code, "message": message, "request_id": rid}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status, headers={"X-Request-ID": rid})


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_mw(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return _payload(request, exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return _payload(request, exc.status_code, DEFAULT_CODES.get(exc.status_code, "error"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return _payload(request, 422, "validation_error", "Données invalides.", details)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Erreur non gérée (request_id=%s)", getattr(request.state, "request_id", ""))
        return _payload(request, 500, "internal_error", "Erreur interne du serveur.")
