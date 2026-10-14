"""auth: вход, выход и текущий сотрудник; cookie ставит роутер, логика — в service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import SID_COOKIE, clear_session_cookies, set_session_cookies
from app.api.database import get_session
from app.api.deps import require_staff
from app.auth import service
from app.auth.schemas import LoginIn, LoginOut, MeOut
from app.core import sessions
from app.core.exceptions import ServiceUnavailable
from app.core.principal import Principal, Role

router = APIRouter(tags=["auth"])
STAFF = (Role.ADMIN, Role.REVIEWER)


@router.post("/login", response_model=LoginOut, operation_id="staffLogin")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginOut:
    """Пароль + TOTP → новая сессия; присланный до входа SID удаляется (защита от фиксации, TC-AUTH-05)."""
    redis = request.app.state.redis
    try:
        old_sid = request.cookies.get(SID_COOKIE)
        if old_sid:
            await sessions.destroy(redis, old_sid)
        sid, csrf, role = await service.login(session, redis, body.email, body.password, body.totp)
    except RedisError:
        raise ServiceUnavailable from None
    set_session_cookies(response, sid, csrf)
    response.headers["Cache-Control"] = "no-store"
    return LoginOut(csrf_token=csrf, role=role)


@router.post("/logout", status_code=204, operation_id="staffLogout")
async def logout(request: Request, response: Response, _: Annotated[Principal, Depends(require_staff(*STAFF))]) -> None:
    """Удаляет сессию на сервере и затирает cookie (TC-AUTH-04)."""
    sid = request.cookies.get(SID_COOKIE)
    if sid:
        await sessions.destroy(request.app.state.redis, sid)
    clear_session_cookies(response)


@router.get("/me", response_model=MeOut, operation_id="staffMe")
async def me(
    request: Request,
    principal: Annotated[Principal, Depends(require_staff(*STAFF))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeOut:
    """Текущий сотрудник и CSRF-токен его сессии (нужен Swagger/SPA после перезагрузки страницы)."""
    user = await service.get_user(session, principal.subject_id)
    data = await sessions.load_and_touch(request.app.state.redis, request.cookies[SID_COOKIE])
    return MeOut(id=str(user.id), email=user.email, role=user.role, csrf_token=data.csrf if data else "")
