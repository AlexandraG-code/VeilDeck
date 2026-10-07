"""Идентификатор запроса: генерируется на сервере, не берётся из заголовков клиента."""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Возвращает request_id текущего запроса."""
    return _request_id.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Присваивает каждому запросу UUIDv4 и возвращает его в заголовке ответа."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token = _request_id.set(str(uuid.uuid4()))
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = get_request_id()
            return response
        finally:
            _request_id.reset(token)
