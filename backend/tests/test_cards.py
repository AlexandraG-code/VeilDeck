"""Staff-API карточек: создание, чтение, публикация (4.1); TC-RBAC-02, TC-CARD, TC-CAT-02, TC-API-02, аудит."""

import os
import re

import pytest
from sqlalchemy import event

from app.audit.service import verify_chain
from tests.test_auth import (
    LOGIN,
    PASSWORD,
    api,  # noqa: F401 — фикстура приложения (Postgres + Redis + https-клиент)
    csrf,
    make_user,
    owner_sql,
    post,
    run_async,
    secrets_by_role,  # noqa: F401 — миграции и базовые аккаунты (зависимость фикстуры api)
    totp_code,
)

pytestmark = pytest.mark.skipif(
    not all(os.getenv(k) for k in ("TEST_DATABASE_OWNER_URL", "TEST_APP_RW_PASSWORD", "TEST_REDIS_URL")),
    reason="нужны PostgreSQL/Redis из TEST_*",
)
CARDS = "/api/v1/staff/cards"
PUBLIC = "/api/v1/cards"
CARD_ADMIN = "admin-cards-test@example.test"
CARD_REVIEWER = "reviewer-cards-test@example.test"
ORG = "ZZTEST Nordlicht Holding"
PUBLIC_FIELDS = {
    "id", "title_generic", "industry", "region_macro", "size_band",
    "revenue_band", "deal_type", "teaser_text", "published_at",
}  # fmt: skip
CARD = {
    "title_generic": "Производитель компонентов",
    "industry": "manufacturing",
    "region_macro": "europe",
    "size_band": "50_to_249",
    "revenue_band": "10m_to_50m",
    "deal_type": "equity",
    "teaser_text": "Региональный производитель с устойчивой выручкой и экспортом.",
    "org_name": ORG,
    "org_aliases": ["ZZTEST Nordlicht"],
    "full_description": "Подробное описание только для одобренных получателей.",
}


@pytest.fixture(scope="module")
def staff(secrets_by_role):  # noqa: F811, ARG001 — гарантирует миграции из test_auth
    """Два аккаунта для этого модуля; после модуля удаляются они и созданные тестами карточки."""
    cleanup = [
        f"DELETE FROM staff_users WHERE email IN ('{CARD_ADMIN}', '{CARD_REVIEWER}')",
    ]
    wipe_cards = "DELETE FROM cards WHERE org_name LIKE 'ZZTEST%'"
    run_async(owner_sql(wipe_cards))
    run_async(owner_sql(cleanup[0]))
    secrets = {
        "admin": run_async(make_user(CARD_ADMIN, "admin")),
        "reviewer": run_async(make_user(CARD_REVIEWER, "reviewer")),
    }
    yield secrets
    run_async(owner_sql(wipe_cards))
    run_async(owner_sql(cleanup[0]))


def sign_in(client, staff, role):
    """Вход с очисткой счётчика повтора TOTP; возвращает CSRF-токен сессии."""
    email = CARD_ADMIN if role == "admin" else CARD_REVIEWER
    run_async(owner_sql(f"UPDATE staff_users SET totp_last_step = NULL, failed_logins = 0 WHERE email = '{email}'"))
    client.cookies.clear()
    body = {"email": email, "password": PASSWORD, "totp": totp_code(staff[role])}
    response = post(client, LOGIN, csrf(client), body)
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def create(client, token, **overrides):
    """Создаёт карточку от имени текущей сессии."""
    return post(client, CARDS, token, {**CARD, **overrides})


def test_anonymous_and_missing_csrf(api):  # noqa: F811
    """Без CSRF — 403, с CSRF но без сессии — 401 (TC-RBAC-05, TC-API-04)."""
    assert api.post(CARDS, json=CARD).status_code == 403
    assert post(api, CARDS, csrf(api), CARD).status_code == 401
    assert api.get(f"{CARDS}/00000000-0000-4000-8000-000000000000").status_code == 401


def test_admin_creates_draft_with_server_side_fields(api, staff):  # noqa: F811
    """Создание: 201, draft, created_by из сессии, в ответе есть конфиденциальные поля; лишние поля — 422."""
    token = sign_in(api, staff, "admin")
    created = create(api, token)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "draft" and body["published_at"] is None
    assert body["org_name"] == ORG and body["created_by"]
    assert api.get(f"{CARDS}/{body['id']}").json() == body
    for extra in ({"status": "published"}, {"created_by": "00000000-0000-4000-8000-000000000001"}, {"id": body["id"]}):
        assert create(api, token, **extra).status_code == 422
    assert create(api, token, teaser_text="   ").status_code == 422
    assert create(api, token, industry="not_an_industry").status_code == 422


def test_reviewer_cannot_create_or_publish_but_can_read(api, staff):  # noqa: F811
    """TC-RBAC-02: reviewer получает 403 на создание и публикацию, чтение разрешено."""
    admin_token = sign_in(api, staff, "admin")
    card_id = create(api, admin_token).json()["id"]
    reviewer_token = sign_in(api, staff, "reviewer")
    assert create(api, reviewer_token).status_code == 403
    assert post(api, f"{CARDS}/{card_id}/publish", reviewer_token).status_code == 403
    assert api.get(f"{CARDS}/{card_id}").status_code == 200


def test_tc_cat_02_same_404_for_bad_and_unknown_id(api, staff):  # noqa: F811
    """Неверный и несуществующий ID дают одинаковый ответ (кроме request_id), как и в публичном каталоге."""
    sign_in(api, staff, "admin")
    bodies = []
    for identifier in ("123", "00000000-0000-4000-8000-0000000000aa"):
        response = api.get(f"{CARDS}/{identifier}")
        assert response.status_code == 404
        error = response.json()["error"]
        bodies.append((error["code"], error["message"]))
    assert bodies[0] == bodies[1]


def test_publish_makes_card_public_with_nine_fields_only(api, staff):  # noqa: F811
    """Черновик в каталоге отсутствует; после публикации виден ровно с 9 teaser-полями; повтор — 409."""
    token = sign_in(api, staff, "admin")
    card_id = create(api, token).json()["id"]
    assert api.get(f"{PUBLIC}/{card_id}").status_code == 404
    published = post(api, f"{CARDS}/{card_id}/publish", token)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published" and published.json()["published_at"]
    public = api.get(f"{PUBLIC}/{card_id}")
    assert public.status_code == 200 and set(public.json()) == PUBLIC_FIELDS
    assert ORG not in public.text and "Подробное описание" not in public.text
    assert post(api, f"{CARDS}/{card_id}/publish", token).status_code == 409


@pytest.mark.parametrize(
    "teaser",
    [
        "Компания ZZTEST Nordlicht Holding ищет партнёра.",
        "Компания ZZTEST Nordlіcht ищет партнёра.",  # кириллическая «і» вместо латинской
        "Свяжитесь через info@example.test для деталей.",
    ],
)
def test_tc_card_leaking_teaser_is_rejected_and_stays_draft(api, staff, teaser):  # noqa: F811
    """TC-CARD-04: утечка → 422 teaser_leak с кодами и полями, но без текста; карточка остаётся draft."""
    token = sign_in(api, staff, "admin")
    card_id = create(api, token, teaser_text=teaser).json()["id"]
    response = post(api, f"{CARDS}/{card_id}/publish", token)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "teaser_leak" and error["violations"]
    assert all(set(v) == {"code", "field"} for v in error["violations"])
    assert "ZZTEST" not in response.text and "example.test" not in response.text
    assert api.get(f"{CARDS}/{card_id}").json()["status"] == "draft"
    assert api.get(f"{PUBLIC}/{card_id}").status_code == 404


def test_audit_events_written_in_chain(api, staff):  # noqa: F811
    """card.created и card.published пишутся в той же транзакции, цепочка цела, details пуст."""
    token = sign_in(api, staff, "admin")
    card_id = create(api, token).json()["id"]
    post(api, f"{CARDS}/{card_id}/publish", token)
    rows = run_async(_rows(f"SELECT action, details::text FROM audit_events WHERE object_id = '{card_id}' ORDER BY id"))
    assert rows == [("card.created", "{}"), ("card.published", "{}")]
    assert run_async(_chain_ok(api))


def test_catalog_sql_never_touches_cards_table(api, staff):  # noqa: F811
    """Компенсирующий контроль варианта A: публичный каталог читает только view и не упоминает confidential-колонки."""
    token = sign_in(api, staff, "admin")
    card_id = create(api, token).json()["id"]
    post(api, f"{CARDS}/{card_id}/publish", token)
    api.cookies.clear()
    statements: list[str] = []
    engine = api.app.state.database.engine.sync_engine
    listener = lambda conn, cursor, statement, *rest: statements.append(statement)  # noqa: E731, ARG005
    event.listen(engine, "before_cursor_execute", listener)
    try:
        for url in (PUBLIC, f"{PUBLIC}?industry=manufacturing&page_size=5", f"{PUBLIC}/{card_id}", f"{PUBLIC}/123"):
            api.get(url)
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    catalog = [s for s in statements if "catalog_cards" in s]
    assert catalog, "каталог не выполнил ни одного запроса к view"
    for statement in catalog:
        assert not re.search(r"org_name|org_aliases|full_description", statement)
        assert not re.search(r"(?<![a-z_])cards(?![a-z_])", statement.replace("catalog_cards", ""))


async def _rows(query: str) -> list[tuple]:
    """Читает строки под владельцем."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_DATABASE_OWNER_URL"], hide_parameters=True)
    try:
        async with engine.begin() as connection:
            return [tuple(row) for row in (await connection.execute(text(query))).fetchall()]
    finally:
        await engine.dispose()


async def _chain_ok(client) -> bool:
    """Проверяет hash-цепочку отдельным соединением приложения."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.test_auth import app_rw_url

    engine = create_async_engine(app_rw_url(), hide_parameters=True)
    try:
        async with async_sessionmaker(engine)() as session, session.begin():
            return await verify_chain(session)
    finally:
        await engine.dispose()
