"""Архитектурные правила: deny by default на роутах, extra="forbid" в схемах, ошибки без HTTP."""

import importlib
import inspect
import pkgutil

from fastapi.routing import APIRoute
from pydantic import BaseModel

import app
from app.main import app as fastapi_app

# Роуты без проверки роли: только явный allowlist (и каждая запись объясняется).
PUBLIC_ROUTES = {
    ("GET", "/healthz"),  # проверка живости
}
PUBLIC_PREFIXES = (
    "/api/v1/cards",  # публичный каталог и запрос доступа (rate limit обязателен — задачи 5.1, 5.2)
    "/api/v1/access/redeem",  # обмен одноразовой ссылки на сессию viewer (задача 7.1)
)
DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def _has_auth_dependency(route: APIRoute) -> bool:
    """Есть ли в дереве зависимостей роута require_staff / require_viewer."""
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if getattr(dep.call, "is_auth_dependency", False):
            return True
        stack.extend(dep.dependencies)
    return False


def test_every_route_has_auth_or_is_allowlisted():
    """TC-RBAC: нет роутов без проверки роли, кроме явно разрешённых публичных."""
    unprotected = []
    for route in fastapi_app.routes:
        if not isinstance(route, APIRoute) or route.path in DOCS_PATHS:
            continue
        methods = route.methods or set()
        public = any((m, route.path) in PUBLIC_ROUTES for m in methods) or route.path.startswith(PUBLIC_PREFIXES)
        if not public and not _has_auth_dependency(route):
            unprotected.append((sorted(methods), route.path))
    assert not unprotected, f"Роуты без проверки роли: {unprotected}"


def test_all_schemas_forbid_extra_fields():
    """Pydantic-схемы доменов запрещают лишние поля."""
    violations = []
    for module_info in pkgutil.walk_packages(app.__path__, prefix="app."):
        if not module_info.name.endswith(".schemas"):
            continue
        module = importlib.import_module(module_info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseModel) and cls.__module__ == module.__name__:
                if cls.model_config.get("extra") != "forbid":
                    violations.append(f"{module.__name__}.{cls.__name__}")
    assert not violations, f"Схемы без extra='forbid': {violations}"


def test_unauthorized_by_default():
    """Зависимость require_staff без хранилища сессий всегда отказывает с 401 в едином формате."""
    from typing import Annotated

    from fastapi import APIRouter, Depends
    from fastapi.testclient import TestClient

    from app.api.deps import require_staff
    from app.core.principal import Role
    from app.main import create_app

    probe_app = create_app()
    probe = APIRouter()

    @probe.get("/_probe")
    async def _probe(_: Annotated[object, Depends(require_staff(Role.ADMIN))]):
        return {}

    probe_app.include_router(probe)
    response = TestClient(probe_app, raise_server_exceptions=False).get("/_probe")
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "request_id"}
