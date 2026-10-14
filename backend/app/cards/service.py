"""cards: бизнес-логика без FastAPI/HTTP; Principal и сессия БД приходят аргументами (T-02, T-03, SR-03, SR-11)."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit
from app.cards import repository
from app.cards.leak_linter import find_leaks
from app.cards.models import Card
from app.cards.schemas import CardCreateIn, CardFull
from app.core.exceptions import Conflict, Forbidden, NotFound, TeaserLeak
from app.core.principal import Principal, Role


@dataclass(frozen=True)
class RequestContext:
    """Сведения о запросе для аудита: id запроса и HMAC от IP (сам IP в сервис не попадает)."""

    request_id: str
    ip_hash: str


def _parse_id(card_id: str) -> UUID:
    """Неверный UUID неотличим от несуществующей карточки (одинаковый 404, TC-CAT-02)."""
    try:
        parsed = UUID(card_id)
    except ValueError:
        raise NotFound from None
    if parsed.version != 4:  # noqa: PLR2004
        raise NotFound
    return parsed


def _require_admin(principal: Principal) -> None:
    """Разделение обязанностей, второй рубеж после RBAC: публиковать и создавать может только admin."""
    if principal.role != Role.ADMIN:
        raise Forbidden


async def create_card(session: AsyncSession, principal: Principal, data: CardCreateIn, ctx: RequestContext) -> CardFull:
    """Создаёт черновик; created_by берётся из серверной сессии, а не из запроса."""
    _require_admin(principal)
    async with session.begin():
        card = Card(**data.model_dump(mode="json"), status="draft", created_by=principal.subject_id)
        repository.add(session, card)
        await session.flush()
        await audit.record(
            session,
            actor_ref=str(principal.subject_id),
            action="card.created",
            object_type="card",
            object_id=card.id,
            ip_hash=ctx.ip_hash,
            request_id=ctx.request_id,
        )
        return CardFull.model_validate(card)


async def get_card(session: AsyncSession, card_id: str) -> CardFull:
    """Возвращает полную карточку любого статуса (роль проверена зависимостью роутера)."""
    identifier = _parse_id(card_id)
    async with session.begin():
        card = await repository.get(session, identifier)
        if card is None:
            raise NotFound
        return CardFull.model_validate(card)


async def publish_card(session: AsyncSession, principal: Principal, card_id: str, ctx: RequestContext) -> CardFull:
    """Публикует черновик после линтера утечек; при нарушении карточка остаётся draft, текст в ответ не попадает."""
    _require_admin(principal)
    identifier = _parse_id(card_id)
    async with session.begin():
        card = await repository.get_for_update(session, identifier)
        if card is None:
            raise NotFound
        if card.status != "draft":
            raise Conflict("Карточка уже опубликована или в архиве")
        violations = find_leaks(
            {"title_generic": card.title_generic, "teaser_text": card.teaser_text}, card.org_name, card.org_aliases
        )
        if violations:
            raise TeaserLeak([(str(v.code), v.field) for v in violations])
        published = await repository.mark_published(session, identifier)
        if published is None:
            raise Conflict("Карточка уже опубликована или в архиве")
        await audit.record(
            session,
            actor_ref=str(principal.subject_id),
            action="card.published",
            object_type="card",
            object_id=identifier,
            ip_hash=ctx.ip_hash,
            request_id=ctx.request_id,
        )
        return CardFull.model_validate(published)
