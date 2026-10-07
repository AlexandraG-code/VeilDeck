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
