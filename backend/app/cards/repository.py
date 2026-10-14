"""cards: доступ к таблице cards; коммитов нет, границу транзакции держит сервис."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cards.models import Card


def add(session: AsyncSession, card: Card) -> None:
    """Добавляет карточку в сессию."""
    session.add(card)


async def get(session: AsyncSession, card_id: UUID) -> Card | None:
    """Читает карточку по id (staff-зона: видны все статусы)."""
    return await session.get(Card, card_id)


async def get_for_update(session: AsyncSession, card_id: UUID) -> Card | None:
    """Читает карточку с блокировкой строки: два параллельных publish не пройдут оба."""
    return await session.scalar(select(Card).where(Card.id == card_id).with_for_update())


async def mark_published(session: AsyncSession, card_id: UUID) -> Card | None:
    """Переводит draft в published; WHERE status='draft' делает переход атомарным, иначе возвращает None."""
    return await session.scalar(
        update(Card)
        .where(Card.id == card_id, Card.status == "draft")
        .values(status="published", published_at=func.now())
        .returning(Card)
        .execution_options(populate_existing=True)
    )
