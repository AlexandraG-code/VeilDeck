"""Единый формат ошибок {"error": {"code", "message", "request_id"}} без стек-трейсов."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import get_request_id

HTTP_INTERNAL_ERROR = 500
VALIDATION_STATUS = 422


class AppError(Exception):
    """Доменная ошибка с кодом, понятным клиенту."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Собирает ответ об ошибке в едином формате."""
    body = {"error": {"code": code, "message": message, "request_id": get_request_id()}}
    return JSONResponse(status_code=status_code, content=body)


def register_error_handlers(app: FastAPI) -> None:
    """Подключает обработчики, скрывающие внутренние детали."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, f"http_{exc.status_code}", "Ошибка запроса")

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return error_response(VALIDATION_STATUS, "validation_error", "Некорректные данные запроса")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, __: Exception) -> JSONResponse:
        return error_response(HTTP_INTERNAL_ERROR, "internal_error", "Внутренняя ошибка")
