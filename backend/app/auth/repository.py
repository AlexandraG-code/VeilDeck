"""auth: доступ к таблице staff_users; коммитов здесь нет, границу транзакции держит сервис."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import StaffUser

MAX_FAILED_LOGINS = 5


async def get_by_email(session: AsyncSession, email: str) -> StaffUser | None:
    """Ищет сотрудника по e-mail без учёта регистра."""
    return await session.scalar(select(StaffUser).where(func.lower(StaffUser.email) == email.lower()))


async def get_by_id(session: AsyncSession, user_id: UUID) -> StaffUser | None:
    """Ищет сотрудника по идентификатору."""
    return await session.get(StaffUser, user_id)


def add(session: AsyncSession, user: StaffUser) -> None:
    """Добавляет нового сотрудника в сессию."""
    session.add(user)


async def accept_totp_step(session: AsyncSession, user_id: UUID, step: int) -> bool:
    """Атомарно принимает шаг TOTP, если он новее принятого (повтор отклоняется); сбрасывает счётчики."""
    result = await session.execute(
        update(StaffUser)
        .where(StaffUser.id == user_id, (StaffUser.totp_last_step.is_(None)) | (StaffUser.totp_last_step < step))
        .values(totp_last_step=step, failed_logins=0, locked_until=None)
    )
    return result.rowcount == 1


async def register_failure(session: AsyncSession, user_id: UUID, locked_until: datetime) -> None:
    """Увеличивает счётчик неудач; на пятой блокирует вход до locked_until и обнуляет счётчик (одним UPDATE)."""
    reached = StaffUser.failed_logins + 1 >= MAX_FAILED_LOGINS
    await session.execute(
        update(StaffUser)
        .where(StaffUser.id == user_id)
        .values(
            failed_logins=case((reached, 0), else_=StaffUser.failed_logins + 1),
            locked_until=case((reached, locked_until), else_=StaffUser.locked_until),
        )
    )
