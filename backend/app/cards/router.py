"""cards: staff-API карточек. Создание и публикация — только admin, чтение — admin и reviewer."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client_ip import client_ip_hash
from app.api.database import get_session
from app.api.deps import require_staff
from app.cards import service
from app.cards.schemas import CardCreateIn, CardFull, TeaserLeakError
from app.core.principal import Principal, Role
from app.core.request_id import get_request_id

router = APIRouter(tags=["cards"])
Admin = Annotated[Principal, Depends(require_staff(Role.ADMIN))]
AnyStaff = Annotated[Principal, Depends(require_staff(Role.ADMIN, Role.REVIEWER))]
Session = Annotated[AsyncSession, Depends(get_session)]


def _context(request: Request) -> service.RequestContext:
    """Контекст аудита: id запроса и HMAC от peer-IP."""
    return service.RequestContext(request_id=get_request_id(), ip_hash=client_ip_hash(request))


@router.post("", response_model=CardFull, status_code=201, operation_id="createCard")
async def create_card(body: CardCreateIn, request: Request, principal: Admin, session: Session) -> CardFull:
    """Создаёт черновик карточки (admin)."""
    return await service.create_card(session, principal, body, _context(request))


@router.get("/{card_id}", response_model=CardFull, operation_id="getCard")
async def get_card(card_id: str, _: AnyStaff, session: Session) -> CardFull:
    """Полная карточка любого статуса (admin и reviewer); неверный ID — тот же 404, что и несуществующий."""
    return await service.get_card(session, card_id)


@router.post(
    "/{card_id}/publish",
    response_model=CardFull,
    operation_id="publishCard",
    responses={422: {"model": TeaserLeakError, "description": "Teaser раскрывает организацию (teaser_leak)"}},
)
async def publish_card(card_id: str, request: Request, principal: Admin, session: Session) -> CardFull:
    """Публикует черновик после проверки линтером утечек (admin)."""
    return await service.publish_card(session, principal, card_id, _context(request))
