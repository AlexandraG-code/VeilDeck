"""Зависимости роутов (deny by default). Чтение сессии из Redis появится в задаче 2.2/2.5 (Диана)."""

from collections.abc import Awaitable, Callable

from app.core.exceptions import Unauthorized
from app.core.principal import Principal, Role


def require_staff(*roles: Role) -> Callable[[], Awaitable[Principal]]:
    """Возвращает зависимость, пускающую staff только с одной из ролей.

    Пока нет хранилища сессий, всегда отказывает: незащищённого пути нет.
    """

    async def dependency() -> Principal:
        raise Unauthorized()

    dependency.allowed_roles = roles  # type: ignore[attr-defined]
    dependency.is_auth_dependency = True  # type: ignore[attr-defined]
    return dependency


async def require_viewer() -> Principal:
    """Зависимость viewer-зоны; пока всегда отказывает (задача 7.2)."""
    raise Unauthorized()


require_viewer.is_auth_dependency = True  # type: ignore[attr-defined]
