"""Публичная отправка запроса доступа (5.2): TC-API-02, TC-API-03, TC-RL-01, TC-LEAK-05, единообразие ответа."""

import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.audit.service import verify_chain
from app.core.crypto import hmac_hex
from tests.test_auth import (
    api,  # noqa: F401 — фикстура приложения (Postgres + Redis + https-клиент)
    csrf,
    post,
    run_async,
    secrets_by_role,  # noqa: F401 — миграции и базовые аккаунты (зависимость фикстуры api)
)

pytestmark = pytest.mark.skipif(
    not all(os.getenv(k) for k in ("TEST_DATABASE_OWNER_URL", "TEST_APP_RW_PASSWORD", "TEST_REDIS_URL")),
    reason="нужны PostgreSQL/Redis из TEST_*",
)
PUBLISHED = "5a2e0000-0000-4000-8000-000000000001"
DRAFT = "5a2e0000-0000-4000-8000-000000000002"
MISSING = "5a2e0000-0000-4000-8000-0000000000ff"
ORG = "ZZTEST Requests Holding"
EMAIL = "Requester.Five@Example.Test"
FORM = {
    "email": EMAIL,
    "display_name": "Иван Петров-Сидоров",
    "purpose": "Хочу изучить возможность партнёрства.",
    "consent": True,
}
RECEIVED = {"status": "received"}


def path(card_id: str) -> str:
    """URL отправки запроса по карточке."""
    return f"/api/v1/cards/{card_id}/access-requests"


async def owner_rows(statement: str) -> list[tuple]:
    """SQL под владельцем с возвратом строк (проверка состояния БД)."""
    engine = create_async_engine(os.environ["TEST_DATABASE_OWNER_URL"], hide_parameters=True)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement))
            return [tuple(row) for row in result.fetchall()] if result.returns_rows else []
    finally:
        await engine.dispose()


def rows(statement: str) -> list[tuple]:
    """Синхронная обёртка над owner_rows."""
    return asyncio.run(owner_rows(statement))


def audit_actions(since_id: int) -> list[str]:
    """Действия аудита, добавленные после since_id."""
    return [r[0] for r in rows(f"SELECT action FROM audit_events WHERE id > {since_id} ORDER BY id")]


def last_audit_id() -> int:
    """Текущий максимальный id аудита (аудит append-only, тестовые записи не удаляются)."""
    return rows("SELECT COALESCE(max(id), 0) FROM audit_events")[0][0]


def request_count() -> int:
    """Число запросов доступа к тестовым карточкам."""
    return rows(f"SELECT count(*) FROM access_requests WHERE card_id IN ('{PUBLISHED}', '{DRAFT}')")[0][0]


@pytest.fixture
def cards(secrets_by_role):  # noqa: F811, ARG001 — гарантирует миграции из test_auth
    """Опубликованная и черновая карточки; запросы к ним очищаются до и после теста."""
    clean_requests = f"DELETE FROM access_requests WHERE card_id IN ('{PUBLISHED}', '{DRAFT}')"
    run_async(owner_rows(clean_requests))
    run_async(owner_rows(f"DELETE FROM cards WHERE id IN ('{PUBLISHED}', '{DRAFT}')"))
    for card_id, status in ((PUBLISHED, "published"), (DRAFT, "draft")):
        published_at = "now()" if status == "published" else "NULL"
        run_async(
            owner_rows(
                "INSERT INTO cards (id, status, title_generic, industry, region_macro, size_band, revenue_band, "
                "deal_type, teaser_text, org_name, org_aliases, full_description, published_at) VALUES "
                f"('{card_id}', '{status}', 'Тестовая карточка', 'manufacturing', 'europe', '50_to_249', "
                f"'10m_to_50m', 'equity', 'SYNTHETIC teaser', '{ORG}', '{{}}', 'SYNTHETIC', {published_at})"
            )
        )
    yield
    run_async(owner_rows(clean_requests))
    run_async(owner_rows(f"DELETE FROM cards WHERE id IN ('{PUBLISHED}', '{DRAFT}')"))


def submit(api, card=PUBLISHED, **overrides):  # noqa: F811
    """Отправка формы с CSRF-токеном и Origin, как делает браузер."""
    body = {**FORM, **overrides}
    return post(api, path(card), csrf(api), body)


def test_created_request_is_pending_with_encrypted_email(api, cards):  # noqa: F811
    """Успех: 202, pending, e-mail только как Fernet + HMAC (TC-LEAK-05), событие request.created."""
    before = last_audit_id()
    response = submit(api)
    assert response.status_code == 202 and response.json() == RECEIVED
    [(status, enc, email_hash, name)] = rows(
        f"SELECT status, email_enc, email_hash, display_name FROM access_requests WHERE card_id = '{PUBLISHED}'"
    )
    assert status == "pending" and name == FORM["display_name"]
    assert EMAIL.lower() not in enc and "example.test" not in enc
    assert email_hash == hmac_hex(EMAIL.lower())
    assert audit_actions(before) == ["request.created"]
    assert "example.test" not in str(rows(f"SELECT details, actor_ref FROM audit_events WHERE id > {before}"))
    assert run_async(_verify())


async def _verify() -> bool:
    """Проверка hash-цепочки под app_rw не нужна: достаточно владельца БД."""
    engine = create_async_engine(os.environ["TEST_DATABASE_OWNER_URL"], hide_parameters=True)
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(engine) as session:
            return await verify_chain(session)
    finally:
        await engine.dispose()


@pytest.mark.parametrize("extra", [{"status": "approved"}, {"card_id": MISSING}, {"id": MISSING}])
def test_tc_api_02_mass_assignment_rejected(api, cards, extra):  # noqa: F811
    """Лишние поля (status, card_id) → 422, запрос не создаётся."""
    assert submit(api, **extra).status_code == 422
    assert request_count() == 0


def test_tc_api_03_xss_is_stored_as_text(api, cards):  # noqa: F811
    """<script> в purpose сохраняется как текст без изменений (экранирование — при выводе)."""
    payload = "<script>alert(1)</script>"
    assert submit(api, purpose=payload).status_code == 202
    assert rows("SELECT purpose FROM access_requests ORDER BY created_at DESC LIMIT 1")[0][0] == payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"email": "a b@example.test"},
        {"display_name": "<b>Иван</b>"},
        {"display_name": "x" * 61},
        {"purpose": "p" * 1001},
        {"purpose": "   "},
        {"consent": False},
    ],
)
def test_invalid_form_is_422(api, cards, overrides):  # noqa: F811
    """Валидация по allowlist и длинам на сервере (SR-18); согласие обязательно."""
    assert submit(api, **overrides).status_code == 422
    assert request_count() == 0


def test_response_is_uniform_for_every_outcome(api, cards):  # noqa: F811
    """Новый, дубль, черновик, несуществующая и неверный UUID дают один и тот же ответ (T-02); дубль не плодит строк."""
    before = last_audit_id()
    responses = [
        submit(api),
        submit(api),
        submit(api, DRAFT),
        submit(api, MISSING),
        submit(api, "not-a-uuid"),
    ]
    assert {(r.status_code, r.text) for r in responses} == {(202, '{"status":"received"}')}
    assert request_count() == 1
    assert audit_actions(before) == ["request.created", "request.duplicate"]


def test_honeypot_creates_nothing(api, cards):  # noqa: F811
    """Заполненный honeypot → тот же 202 без создания запроса."""
    response = submit(api, website="https://spam.example")
    assert (response.status_code, response.json()) == (202, RECEIVED)
    assert request_count() == 0


@pytest.mark.parametrize(
    "overrides",
    [{"email": "broken", "consent": False}, {"website": "x" * 5000}, {"purpose": "p" * 5000}, {"unknown": 1}],
)
def test_honeypot_response_does_not_depend_on_other_fields(api, cards, overrides):  # noqa: F811
    """Заполненный honeypot даёт 202 даже при невалидных остальных полях и очень длинном значении."""
    body = {"website": "https://spam.example", **overrides}
    response = submit(api, **body)
    assert (response.status_code, response.json()) == (202, RECEIVED)
    assert request_count() == 0


def test_tc_rl_01_sixth_request_from_ip_gets_429(api, cards):  # noqa: F811
    """6-й запрос за час с одного IP → 429 + Retry-After; в аудите одна запись request.rate_limited."""
    before = last_audit_id()
    statuses = [submit(api, email=f"user{i}@example.test").status_code for i in range(5)]
    assert statuses == [202] * 5
    sixth = submit(api, email="user6@example.test")
    assert sixth.status_code == 429 and int(sixth.headers["Retry-After"]) > 0
    assert submit(api, email="user7@example.test").status_code == 429
    assert audit_actions(before).count("request.rate_limited") == 1
    assert request_count() == 5


def test_email_limit_is_silent_and_audited(api, cards):  # noqa: F811
    """Четвёртая попытка с тем же e-mail за сутки: тот же 202, запрос не создаётся, аудит scope=email."""
    before = last_audit_id()
    results = [submit(api) for _ in range(4)]
    assert {(r.status_code, r.text) for r in results} == {(202, '{"status":"received"}')}
    assert audit_actions(before).count("request.rate_limited") == 1
    assert request_count() == 1
