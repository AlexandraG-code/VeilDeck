"""requests: бизнес-логика без FastAPI/HTTP; Principal и сессия БД приходят аргументами.

Угрозы и требования: T-02/SR-23 (ответ не раскрывает состояние), T-08/SR-17 (mass assignment), T-09/SR-18,
T-11/SR-25 (флуд: 3 запроса в сутки на e-mail по HMAC), SR-28 (e-mail только Fernet + HMAC, не в аудите и логах).
"""

from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit
from app.catalog import service as catalog
from app.core.crypto import fernet_encrypt, hmac_hex
from app.core.exceptions import NotFound
from app.core.ratelimit import check_window, release_window_audit
from app.requests import repository
from app.requests.schemas import AccessRequestIn

EMAIL_LIMIT = 3
EMAIL_WINDOW_SECONDS = 86_400
EMAIL_LIMIT_NAME = "request-email"
ACTOR_ANONYMOUS = "anonymous"
OBJECT_TYPE = "access_request"
ACTION_CREATED = "request.created"
ACTION_DUPLICATE = "request.duplicate"
ACTION_RATE_LIMITED = "request.rate_limited"
PSEUDONYM_LENGTH = 12


async def _published_card_id(session: AsyncSession, card_id: str) -> UUID | None:
    """Идентификатор опубликованной карточки или None (черновик, архив, отсутствует, неверный UUID — одинаково)."""
    try:
        card = await catalog.get_card(session, card_id)
    except NotFound:
        return None
    return card.id


async def submit(
    session: AsyncSession,
    redis: Redis,
    card_id: str,
    data: AccessRequestIn,
    *,
    ip_hash: str,
    request_id: str,
) -> None:
    """Принимает запрос; результат (создан, дубль, лимит, нет карточки, honeypot) вызывающему не различим."""
    if data.website:
        return
    published = await _published_card_id(session, card_id)
    if published is None:
        return
    email_hash = hmac_hex(data.email)
    retry_after, audit_token = await check_window(
        redis, EMAIL_LIMIT_NAME, email_hash, EMAIL_LIMIT, EMAIL_WINDOW_SECONDS * 1000
    )
    if retry_after:
        if audit_token:
            await _record_email_limit(session, redis, email_hash, audit_token, ip_hash, request_id)
        return
    new_id = uuid4()
    async with session.begin():
        created = await repository.insert_pending(
            session,
            {
                "id": new_id,
                "card_id": published,
                "email_enc": fernet_encrypt(data.email),
                "email_hash": email_hash,
                "display_name": data.display_name,
                "purpose": data.purpose,
            },
        )
        await audit.record(
            session,
            actor_type=ACTOR_ANONYMOUS,
            actor_ref=f"requester:{new_id.hex[:PSEUDONYM_LENGTH]}" if created else ACTOR_ANONYMOUS,
            action=ACTION_CREATED if created else ACTION_DUPLICATE,
            object_type=OBJECT_TYPE,
            object_id=created,
            ip_hash=ip_hash,
            request_id=request_id,
            details={"card_id": str(published)},
        )


async def _record_email_limit(
    session: AsyncSession, redis: Redis, email_hash: str, audit_token: str, ip_hash: str, request_id: str
) -> None:
    """Пишет отказ по лимиту e-mail один раз за окно; при сбое БД освобождает маркер, чтобы отказ не потерялся."""
    try:
        async with session.begin():
            await audit.record(
                session,
                actor_type=ACTOR_ANONYMOUS,
                actor_ref=ACTOR_ANONYMOUS,
                action=ACTION_RATE_LIMITED,
                object_type=OBJECT_TYPE,
                object_id=None,
                outcome="deny",
                ip_hash=ip_hash,
                request_id=request_id,
                details={"scope": "email", "limit": EMAIL_LIMIT, "window_seconds": EMAIL_WINDOW_SECONDS},
            )
    except Exception:
        await release_window_audit(redis, EMAIL_LIMIT_NAME, email_hash, audit_token)
        raise
