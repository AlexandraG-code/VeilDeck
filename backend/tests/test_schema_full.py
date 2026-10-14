"""Полная схема design §2 поверх среза каталога: права app_rw по матрице, откат 0002, ограничения (1.6, 1.7)."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

REQUIRED = ("TEST_DATABASE_OWNER_URL", "TEST_APP_RW_PASSWORD")
pytestmark = pytest.mark.skipif(not all(os.getenv(key) for key in REQUIRED), reason="нужен PostgreSQL из TEST_*")
BACKEND = Path(__file__).resolve().parents[1]
ALL_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
# Ожидаемые права app_rw на все объекты схемы; новая таблица без записи здесь роняет тест.
EXPECTED = {
    "cards": set(),  # публичный API читает только view catalog_cards
    "catalog_cards": {"SELECT"},
    "audit_events": {"SELECT", "INSERT"},
    "staff_users": {"SELECT", "INSERT", "UPDATE"},
    "access_requests": {"SELECT", "INSERT", "UPDATE"},
    "materials": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "grants": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "magic_links": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "decisions": {"SELECT", "INSERT"},
    "alembic_version": set(),
}


def owner_url() -> str:
    """URL владельца; только отдельная БД *_test (тесты делают downgrade)."""
    url = os.environ["TEST_DATABASE_OWNER_URL"]
    assert make_url(url).database.endswith("_test"), "нужна отдельная БД *_test"
    return url


def run(module_args: list[str]) -> None:
    """Запускает модуль backend с owner URL; секреты не выводятся."""
    env = {**os.environ, "MIGRATION_DATABASE_URL": owner_url(), "APP_RW_PASSWORD": os.environ["TEST_APP_RW_PASSWORD"]}
    subprocess.run([sys.executable, "-m", *module_args], env=env, cwd=BACKEND, check=True, capture_output=True)  # noqa: S603


async def sql(url: str, statements: list[str]) -> list:
    """Выполняет SQL в одной транзакции отдельного пула; возвращает строки последнего запроса."""
    engine = create_async_engine(url, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            result = None
            for statement in statements:
                result = await connection.execute(text(statement))
            return result.fetchall() if result is not None and result.returns_rows else []
    finally:
        await engine.dispose()


CLEANUP = [
    "DELETE FROM grants WHERE request_id = '00000000-0000-4000-8000-000000000003'",
    "DELETE FROM decisions WHERE request_id = '00000000-0000-4000-8000-000000000003'",
    "DELETE FROM access_requests WHERE id = '00000000-0000-4000-8000-000000000003'",
    "DELETE FROM cards WHERE id = '00000000-0000-4000-8000-000000000002'",
    "DELETE FROM staff_users WHERE id = '00000000-0000-4000-8000-000000000001'",
]


@pytest.fixture(scope="module")
def migrated():
    """Применяет все миграции под app_owner; после тестов удаляет только свои строки (база общая с каталогом)."""
    run(["scripts.bootstrap_db"])
    yield
    asyncio.run(sql(owner_url(), CLEANUP))


async def test_app_rw_privilege_matrix(migrated):
    """Права app_rw совпадают с матрицей, а TRUNCATE и REFERENCES нет ни у одной таблицы."""
    names = await sql(
        owner_url(),
        [
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v')"
        ],
    )
    assert {row[0] for row in names} == set(EXPECTED)
    for table, expected in EXPECTED.items():
        rows = await sql(
            owner_url(),
            [f"SELECT p, has_table_privilege('app_rw', '{table}', p) FROM unnest(ARRAY{list(ALL_PRIVILEGES)}) p"],
        )
        assert {p for p, granted in rows if granted} == expected, table


async def test_decision_reject_requires_reason(migrated):
    """CHECK: отказ без reason_code и одобрение с reason_code невозможны."""
    owner = owner_url()
    await sql(
        owner,
        [
            "INSERT INTO staff_users (id, email, password_hash, totp_secret_enc, role) "
            "VALUES ('00000000-0000-4000-8000-000000000001', 'r@example.test', 'x', 'x', 'reviewer')",
            "INSERT INTO cards (id, title_generic, industry, region_macro, size_band, revenue_band, deal_type, "
            "teaser_text, org_name, full_description) VALUES ('00000000-0000-4000-8000-000000000002', 't', "
            "'logistics', 'europe', 'under_50', 'under_10m', 'asset', 'x', 'o', 'd')",
            "INSERT INTO access_requests (id, card_id, email_hash) VALUES "
            f"('00000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-000000000002', '{'a' * 64}')",
        ],
    )
    bad = (
        "INSERT INTO decisions (request_id, reviewer_id, decision, reason_code) VALUES "
        "('00000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-000000000001', '{d}', {r})"
    )
    for decision, reason in (("reject", "NULL"), ("approve", "'other'")):
        with pytest.raises(IntegrityError):
            await sql(owner, [bad.format(d=decision, r=reason)])
    await sql(owner, [bad.format(d="reject", r="'other'")])
    with pytest.raises(IntegrityError):  # единственное решение: UNIQUE(request_id)
        await sql(owner, [bad.format(d="reject", r="'other'")])


async def test_grant_needs_materials_unless_revoked(migrated):
    """CHECK: пустой material_ids допустим только у отозванного grant (удалён единственный материал)."""
    owner = owner_url()
    insert = (
        "INSERT INTO grants (request_id, card_id, viewer_pseudonym, material_ids, expires_at, max_views, revoked_at) "
        "VALUES ('00000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-000000000002', 'viewer-{n}', "
        "ARRAY[]::uuid[], now() + interval '1 day', 3, {revoked})"
    )
    with pytest.raises(IntegrityError):
        await sql(owner, [insert.format(n="AAAA", revoked="NULL")])
    await sql(owner, [insert.format(n="AAAA", revoked="now()")])


async def test_audit_stays_append_only_after_0002(migrated):
    """0002 не ослабила аудит: UPDATE/DELETE/TRUNCATE по-прежнему отклоняются даже у владельца."""
    for statement in ("UPDATE audit_events SET action = 'x'", "DELETE FROM audit_events", "TRUNCATE audit_events"):
        with pytest.raises(DBAPIError) as error:
            await sql(owner_url(), [statement])
        assert "append-only" in str(error.value)


async def test_downgrade_0002_and_back(migrated):
    """Откат 0002 удаляет её таблицы и возвращается на срез каталога; повторный upgrade восстанавливает всё."""
    run(["alembic", "downgrade", "0001_catalog"])
    names = {row[0] for row in await sql(owner_url(), ["SELECT tablename FROM pg_tables WHERE schemaname = 'public'"])}
    assert not names & {"staff_users", "grants", "decisions", "magic_links", "materials", "access_requests"}
    run(["alembic", "upgrade", "head"])
    names = {row[0] for row in await sql(owner_url(), ["SELECT tablename FROM pg_tables WHERE schemaname = 'public'"])}
    assert {"staff_users", "grants", "decisions", "magic_links", "materials", "access_requests"} <= names
