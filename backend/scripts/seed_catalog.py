"""Повторяемое заполнение синтетическими данными (задача 4.4): карточки, PDF, staff, запросы, grant и ссылка.

Запускается доверенной CLI от app_owner (публичных операций записи нет). Повторный запуск не плодит дубли
и выдаёт свежую одноразовую ссылку для демо-grant. Пароли, TOTP-секреты и токен выводятся один раз в консоль
по спецификации; на стенде с реальными данными seed не запускается (только синтетика, ENV=demo/dev).
"""

import asyncio
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import StaffUser
from app.auth.service import create_staff_user
from app.cards.leak_linter import find_leaks
from app.cards.models import Card, Material
from app.core.crypto import fernet_encrypt, hmac_hex
from app.core.database import Database
from app.core.exceptions import Conflict
from app.grants.models import Grant, MagicLink
from app.requests.models import AccessRequest
from app.review.models import Decision
from scripts.synthetic_pdf import build_pdf

MATERIALS_DIR = Path(os.environ.get("MATERIALS_DIR", "/data/materials"))
MATERIAL_CARDS = 3
MATERIAL_PAGES = (3, 2)
STAFF_ACCOUNTS = (("reviewer@demo.invalid", "reviewer"), ("admin@demo.invalid", "admin"))
PASSWORD_BYTES = 18
MAGIC_LINK_TTL = timedelta(minutes=30)
GRANT_TTL = timedelta(days=7)
GRANT_MAX_VIEWS = 5
PSEUDONYM = "Viewer-DEMO01"
DEMO_REQUESTS = (
    ("pending", "pending1@example.invalid", "Demo Investor One"),
    ("pending", "pending2@example.invalid", "Demo Investor Two"),
    ("rejected", "rejected@example.invalid", "Demo Investor Three"),
    ("approved", "approved@example.invalid", "Demo Investor Four"),
)
PURPOSE = "SYNTHETIC — учебный запрос для демонстрации."


SEED_IDS = (
    UUID("d39a2aed-6ae6-4f40-80a5-e0d60d0591e0"),
    UUID("55738666-4114-466d-a3ac-fb1fc5e84d18"),
    UUID("a85e109c-4a05-43c1-aae5-8b088c1c28cf"),
    UUID("89b2215e-25bd-4ec4-9ffb-c2f8005798a2"),
    UUID("f69ca296-7f91-4251-a64d-391b04e7bb68"),
    UUID("ed221d30-3d6a-48de-ab60-28c0ab0f14ab"),
    UUID("83619abb-ef58-4407-9754-bd46c7c51455"),
    UUID("86cd7080-e221-412c-bff5-f6d302143774"),
    UUID("63503e31-ee8b-4a92-a392-3f308a22bad0"),
    UUID("02ea9ad9-e084-49b6-b846-b3b4fd0627a3"),
    UUID("f263859c-df68-4a58-9d62-cba62f54fccf"),
    UUID("02332073-7731-4a1b-827d-f3a1b616edd6"),
    UUID("57dffa1e-f28c-4fdb-915a-28d7e06b7db4"),
    UUID("0f63f80c-c849-412c-b06a-eb8e7f66018a"),
)


def synthetic_cards() -> list[dict]:
    """Создаёт 12 опубликованных карточек, черновик и архив со стабильными UUIDv4."""
    rows = []
    for index, identifier in enumerate(SEED_IDS, start=1):
        status = "published" if index <= 12 else ("draft" if index == 13 else "archived")
        values = {
            "id": identifier,
            "status": status,
            "title_generic": f"Синтетическая корпоративная возможность {index}",
            "industry": "manufacturing" if index % 2 else "logistics",
            "region_macro": "europe" if index % 3 else "asia",
            "size_band": "50_to_249",
            "revenue_band": "10m_to_50m",
            "deal_type": "equity" if index % 2 else "partnership",
            "teaser_text": "SYNTHETIC — FOR TESTING ONLY. Обезличенное предложение для учебной демонстрации.",
            "org_name": f"Asterion Logistik GmbH {index}",
            "org_aliases": [],
            "full_description": "SYNTHETIC — закрытое демонстрационное описание.",
            "created_by": None,
            "published_at": datetime(2026, 10, 1, tzinfo=UTC) if status == "published" else None,
        }
        fields = {name: values[name] for name in ("title_generic", "teaser_text")}
        if find_leaks(fields, values["org_name"], values["org_aliases"]):
            raise RuntimeError("синтетический teaser не прошёл линтер")
        rows.append(values)
    return rows


async def seed_staff(session: AsyncSession) -> dict[str, UUID]:
    """Создаёт reviewer и admin; выводит пароли и TOTP только для созданных сейчас, возвращает id по роли."""
    for email, role in STAFF_ACCOUNTS:
        password = secrets.token_urlsafe(PASSWORD_BYTES)
        try:
            uri, totp_secret = await create_staff_user(session, email, password, role)
        except Conflict:
            print(f"Сотрудник {email} уже есть (пароль и TOTP выдавались при первом запуске).")
            continue
        print(f"Сотрудник {email} ({role})\n  пароль: {password}\n  TOTP-секрет: {totp_secret}\n  URI: {uri}")
    async with session.begin():
        rows = await session.execute(select(StaffUser.role, StaffUser.id))
        return {role: user_id for role, user_id in rows}


async def seed_materials(session: AsyncSession) -> list[Material]:
    """Создаёт PDF для первых карточек (если у карточки их ещё нет); файл пишется под случайным storage_key."""
    created: list[Material] = []
    MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
    async with session.begin():
        for index, card_id in enumerate(SEED_IDS[:MATERIAL_CARDS], start=1):
            count = await session.scalar(select(func.count()).select_from(Material).where(Material.card_id == card_id))
            if count:
                continue
            for number, pages in enumerate(MATERIAL_PAGES, start=1):
                data = build_pdf(f"Synthetic material {index}.{number}", pages)
                key = secrets.token_hex(16)
                (MATERIALS_DIR / key).write_bytes(data)
                material = Material(
                    card_id=card_id,
                    storage_key=key,
                    original_name=f"synthetic-{index}-{number}.pdf",
                    mime="application/pdf",
                    size=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    pages=pages,
                )
                session.add(material)
                created.append(material)
    return created


async def seed_requests(session: AsyncSession, reviewer_id: UUID) -> UUID | None:
    """Создаёт запросы доступа к первой карточке; возвращает id grant демо-просмотра (или None, если нет PDF)."""
    card_id = SEED_IDS[0]
    now = datetime.now(UTC)
    async with session.begin():
        existing = await session.scalar(
            select(func.count()).select_from(AccessRequest).where(AccessRequest.card_id == card_id)
        )
        if existing:
            return await session.scalar(select(Grant.id).where(Grant.viewer_pseudonym == PSEUDONYM))
        materials = (await session.scalars(select(Material.id).where(Material.card_id == card_id))).all()
        grant_id = None
        for status, email, name in DEMO_REQUESTS:
            request = AccessRequest(
                id=uuid4(),
                card_id=card_id,
                email_enc=fernet_encrypt(email),
                email_hash=hmac_hex(email),
                display_name=name,
                purpose=PURPOSE,
                status=status,
            )
            session.add(request)
            await session.flush()
            if status == "rejected":
                session.add(
                    Decision(request_id=request.id, reviewer_id=reviewer_id, decision="reject", reason_code="other")
                )
            elif status == "approved" and materials:
                session.add(Decision(request_id=request.id, reviewer_id=reviewer_id, decision="approve"))
                grant = Grant(
                    request_id=request.id,
                    card_id=card_id,
                    viewer_pseudonym=PSEUDONYM,
                    material_ids=list(materials),
                    allow_download=False,
                    expires_at=now + GRANT_TTL,
                    max_views=GRANT_MAX_VIEWS,
                )
                session.add(grant)
                await session.flush()
                grant_id = grant.id
    return grant_id


async def issue_magic_link(session: AsyncSession, grant_id: UUID) -> str | None:
    """Выдаёт свежую одноразовую ссылку демо-grant, если нет неиспользованной и действующей; токен — один раз."""
    now = datetime.now(UTC)
    async with session.begin():
        active = await session.scalar(
            select(func.count())
            .select_from(MagicLink)
            .where(MagicLink.grant_id == grant_id, MagicLink.used_at.is_(None), MagicLink.expires_at > now)
        )
        if active:
            return None
        token = secrets.token_urlsafe(32)
        session.add(
            MagicLink(
                grant_id=grant_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=now + MAGIC_LINK_TTL,
            )
        )
    return token


async def seed() -> None:
    """Добавляет отсутствующие demo-записи, не меняя существующие данные."""
    database = Database(os.environ["MIGRATION_DATABASE_URL"])
    try:
        async with database.sessions() as session, session.begin():
            await session.execute(insert(Card).values(synthetic_cards()).on_conflict_do_nothing(index_elements=["id"]))
        async with database.sessions() as session:
            staff = await seed_staff(session)
        async with database.sessions() as session:
            await seed_materials(session)
        async with database.sessions() as session:
            grant_id = await seed_requests(session, staff["reviewer"])
        if grant_id is None:
            return
        async with database.sessions() as session:
            token = await issue_magic_link(session, grant_id)
        origin = os.environ.get("PUBLIC_ORIGIN", "https://localhost:8443")
        if token:
            print(f"Одноразовая ссылка viewer (30 мин, показана один раз):\n  {origin}/access#t={token}")
        else:
            print("Действующая одноразовая ссылка уже есть; чтобы получить новую, дождитесь её истечения.")
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(seed())
    print("Синтетические данные готовы: 12 published, 1 draft, 1 archived; staff, PDF, запросы, grant (без дублей).")
