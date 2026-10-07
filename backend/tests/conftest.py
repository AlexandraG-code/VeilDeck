"""Тестовое окружение: секреты задаются до импорта приложения."""

import os

import pytest

TEST_ENV = {
    "ENV": "test",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "SESSION_SECRET": "s" * 40,
    "FERNET_KEY": "f" * 40,
    "HMAC_KEY": "h" * 40,
    "WM_KEY": "w" * 40,
}
os.environ.update(TEST_ENV)


@pytest.fixture
def client():
    """HTTP-клиент поверх приложения без сети."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app, raise_server_exceptions=False)
