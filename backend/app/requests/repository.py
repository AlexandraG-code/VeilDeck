"""requests: Доступ к БД: только таблицы этого домена, без commit."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.requests.models import AccessRequest


async def insert_pending(session: AsyncSession, values: dict) -> UUID | None:
    """Атомарно создаёт pending-запрос; для той же пары (карточка, e-mail) возвращает None (дубль)."""
    statement = (
        insert(AccessRequest)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["card_id", "email_hash"],
            index_where=text("status = 'pending'"),
        )
        .returning(AccessRequest.id)
    )
    return await session.scalar(statement)
