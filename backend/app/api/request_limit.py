"""HTTP-адаптер лимитов отправки запроса доступа: 5/ч на IP (T-11 / SR-25); IP только в виде HMAC."""

from asyncpg import PostgresError
from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from app.api.client_ip import client_ip_hash
from app.audit.service import record
from app.core.exceptions import RateLimited, ServiceUnavailable
from app.core.ratelimit import check_window, release_window_audit
from app.core.request_id import get_request_id

IP_LIMIT = 5
IP_WINDOW_SECONDS = 3600
IP_LIMIT_NAME = "request-ip"


async def limit_access_requests(request: Request) -> None:
    """429 + Retry-After после 5 запросов в час с одного IP; отказ пишется в аудит один раз за окно."""
    ip_hash = client_ip_hash(request)
    redis = request.app.state.redis
    retry_after, audit_token = await check_window(redis, IP_LIMIT_NAME, ip_hash, IP_LIMIT, IP_WINDOW_SECONDS * 1000)
    if not retry_after:
        return
    if audit_token:
        try:
            async with request.app.state.database.sessions() as session, session.begin():
                await record(
                    session,
                    actor_type="anonymous",
                    actor_ref="anonymous",
                    action="request.rate_limited",
                    object_type="access_request",
                    object_id=None,
                    outcome="deny",
                    ip_hash=ip_hash,
                    request_id=get_request_id(),
                    details={"scope": "ip", "limit": IP_LIMIT, "window_seconds": IP_WINDOW_SECONDS},
                )
        except (OSError, SQLAlchemyError, PostgresError):
            await release_window_audit(redis, IP_LIMIT_NAME, ip_hash, audit_token)
            raise ServiceUnavailable from None
    raise RateLimited(retry_after)
