"""应用异常与全局异常处理。"""

from __future__ import annotations

import math

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from backend.logging_config import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """业务异常基类，携带 HTTP 状态码与错误码。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, resource: str, item_id: str) -> None:
        super().__init__(
            status_code=404,
            code="not_found",
            message=f"{resource} 不存在: {item_id}",
        )


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(status_code=409, code="conflict", message=message)


def _json_safe(value):
    """Validation context can contain exceptions or non-finite input values."""
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return jsonable_encoder(value)


def _error_response(status: int, code: str, message: str, details=None, headers=None):
    return JSONResponse(status_code=status, headers=headers, content={"error": {
        "code": code, "message": message, "details": _json_safe(details or {}),
    }})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(422, "validation_error", "Request validation failed",
                               {"violations": exc.errors()})

    @app.exception_handler(HTTPException)
    async def handle_http(request: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 409: "conflict"}.get(
            exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "HTTP request failed"
        return _error_response(exc.status_code, code, message,
                               {} if isinstance(exc.detail, str) else {"detail": exc.detail},
                               exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常: %s %s", request.method, request.url.path)
        return _error_response(500, "internal_error", "服务器内部错误")
