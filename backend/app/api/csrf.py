"""CSRF (SR-05, T-04): double-submit cookie и проверка Origin на изменяющих методах; для staff ещё токен сессии."""

import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict
from redis.exceptions import RedisError

from app.api.cookies import CSRF_COOKIE, SID_COOKIE, set_csrf_cookie
from app.core import sessions
from app.core.config import get_settings
from app.core.exceptions import Forbidden, ServiceUnavailable

STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER = "X-CSRF-Token"
CSRF_TOKEN_BYTES = 32
CSRF_MESSAGE = "Недействительный CSRF-токен"

csrf_header = APIKeyHeader(name=CSRF_HEADER, auto_error=False, description="Значение из cookie __Host-csrf")
router = APIRouter(tags=["csrf"])


class CsrfOut(BaseModel):
    """Токен для заголовка X-CSRF-Token."""

    model_config = ConfigDict(extra="forbid")
    csrf_token: str


def _same(left: str | None, right: str | None) -> bool:
    """Сравнение секретов за постоянное время; пустое значение никогда не равно."""
    return bool(left) and bool(right) and hmac.compare_digest(left, right)


async def require_csrf(request: Request, token: Annotated[str | None, Depends(csrf_header)] = None) -> None:
    """Отклоняет изменяющий запрос без верного Origin, совпадающих cookie/заголовка и токена сессии (403)."""
    if request.method not in STATE_CHANGING_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    if not _same(request.headers.get("origin"), get_settings().public_origin) or not _same(token, cookie):
        raise Forbidden(CSRF_MESSAGE)
    sid = request.cookies.get(SID_COOKIE)
    if sid:
        try:
            data = await sessions.load_and_touch(request.app.state.redis, sid)
        except RedisError:
            raise ServiceUnavailable from None
        if data is not None and not _same(token, data.csrf):
            raise Forbidden(CSRF_MESSAGE)


require_csrf.is_csrf_dependency = True  # type: ignore[attr-defined]


@router.get("/csrf", response_model=CsrfOut, operation_id="getCsrfToken")
async def issue_csrf(request: Request, response: Response) -> CsrfOut:
    """Выдаёт токен и ставит cookie __Host-csrf: нужен до входа (login тоже проверяется)."""
    token = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
    sid = request.cookies.get(SID_COOKIE)
    if sid:
        try:
            data = await sessions.load_and_touch(request.app.state.redis, sid)
        except RedisError:
            raise ServiceUnavailable from None
        if data is not None:
            token = data.csrf
    set_csrf_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return CsrfOut(csrf_token=token)
