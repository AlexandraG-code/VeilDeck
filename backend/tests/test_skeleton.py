"""Каркас: healthz, формат ошибок, fail-fast конфига (SR-32)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_healthz_ok(client):
    """healthz отвечает 200 и request_id в заголовке."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_unknown_route_has_unified_error(client):
    """Несуществующий путь отдаёт единый формат ошибки без стек-трейса."""
    response = client.get("/nope")
    body = response.json()
    assert response.status_code == 404
    assert set(body["error"]) == {"code", "message", "request_id"}


@pytest.mark.parametrize("missing", ["FERNET_KEY", "HMAC_KEY", "WM_KEY", "SESSION_SECRET"])
def test_settings_fail_without_secret(monkeypatch, missing):
    """Приложение не стартует без секрета."""
    monkeypatch.delenv(missing)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("bad", ["changeme", "short", ""])
def test_settings_reject_default_secret(monkeypatch, bad):
    """Дефолтное, короткое и пустое значение секрета отклоняется."""
    monkeypatch.setenv("FERNET_KEY", bad)
    with pytest.raises(ValidationError):
        Settings()


def test_domain_errors_map_to_http():
    """Доменные исключения превращаются в коды и единый формат только в обработчике."""
    from fastapi import APIRouter
    from fastapi.testclient import TestClient

    from app.core.exceptions import Conflict, Gone, NotFound, RateLimited
    from app.main import create_app

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    probe = APIRouter()
    for path, exc in {"/_nf": NotFound(), "/_gone": Gone(), "/_conf": Conflict(), "/_rl": RateLimited(30)}.items():

        def make(e):
            async def endpoint():
                raise e

            return endpoint

        probe.add_api_route(path, make(exc))
    app.include_router(probe)
    assert client.get("/_nf").status_code == 404
    assert client.get("/_gone").status_code == 410
    assert client.get("/_conf").status_code == 409
    rate = client.get("/_rl")
    assert rate.status_code == 429
    assert rate.headers["Retry-After"] == "30"
