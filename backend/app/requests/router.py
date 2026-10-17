"""Публичная отправка запроса на расширенный доступ: всегда 202 {"status":"received"} (SR-23)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client_ip import client_ip_hash
from app.api.database import get_session
from app.api.request_limit import limit_access_requests
from app.core.request_id import get_request_id
from app.requests import service
from app.requests.schemas import AccessRequestIn, AccessRequestOut

router = APIRouter(tags=["requests"])


@router.post(
    "/{card_id}/access-requests",
    status_code=202,
    response_model=AccessRequestOut,
    operation_id="createAccessRequest",
    dependencies=[Depends(limit_access_requests)],
)
async def create_access_request(
    card_id: str,
    body: AccessRequestIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccessRequestOut:
    """Анонимная форма: ответ одинаков для новой карточки, дубля, неопубликованной карточки и honeypot."""
    await service.submit(
        session,
        request.app.state.redis,
        card_id,
        body,
        ip_hash=client_ip_hash(request),
        request_id=get_request_id(),
    )
    return AccessRequestOut()
