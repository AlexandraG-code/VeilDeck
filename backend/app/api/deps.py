"""Зависимости роутов (deny by default): роль берётся только из серверной сессии в Redis (SR-04, SR-08)."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from redis.exceptions import RedisError

from app.api.cookies import SID_COOKIE
from app.core import sessions
from app.core.exceptions import Forbidden, ServiceUnavailable, Unauthorized
from app.core.principal import Principal, Role


def require_staff(*roles: Role) -> Callable[..., Awaitable[Principal]]:
    """Возвращает зависимость, пускающую staff только с одной из ролей: нет сессии — 401, чужая роль — 403."""
    if not roles:
        raise ValueError("Нужно явно указать допустимые роли (deny by default)")

    async def dependency(request: Request, response: Response) -> Principal:
        sid = request.cookies.get(SID_COOKIE)
        if not sid:
            raise Unauthorized()
        try:
            data = await sessions.load_and_touch(request.app.state.redis, sid)
        except RedisError:
            raise ServiceUnavailable from None
        if data is None or data.kind != sessions.KIND_STAFF:
            raise Unauthorized()
        role = Role(data.role)
        if role not in roles:
            raise Forbidden()
        response.headers["Cache-Control"] = "no-store"
        return Principal(subject_id=data.subject_id, role=role)

    dependency.allowed_roles = roles  # type: ignore[attr-defined]
    dependency.is_auth_dependency = True  # type: ignore[attr-defined]
    return dependency


async def require_viewer() -> Principal:
    """Зависимость viewer-зоны; пока всегда отказывает (задача 7.2)."""
    raise Unauthorized()


require_viewer.is_auth_dependency = True  # type: ignore[attr-defined]
