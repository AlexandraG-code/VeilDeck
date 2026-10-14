"""HTTP-адаптер лимитера и отдельной транзакции аудита."""

from asyncpg import PostgresError
from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from app.api.client_ip import client_ip_hash
from app.audit.service import record_catalog_limit
from app.core.exceptions import RateLimited, ServiceUnavailable
from app.core.ratelimit import check_catalog, release_catalog_audit
from app.core.request_id import get_request_id


async def limit_catalog(request: Request) -> None:
    """Доверяет peer-IP, не произвольному X-Forwarded-For; IP в Redis/БД не сохраняется."""
    ip_hash = client_ip_hash(request)
    retry_after, audit = await check_catalog(request.app.state.redis, ip_hash)
    if retry_after:
        if audit:
            try:
                await record_catalog_limit(
                    request.app.state.database.sessions,
                    ip_hash=ip_hash,
                    request_id=get_request_id(),
                )
            except (OSError, SQLAlchemyError, PostgresError):
                await release_catalog_audit(request.app.state.redis, ip_hash, audit)
                raise ServiceUnavailable from None
        raise RateLimited(retry_after)
