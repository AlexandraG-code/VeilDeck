"""Серверные сессии в Redis (SR-04..SR-07, D-02): SID ≥ 256 бит, в Redis только SHA-256 от SID, idle и absolute TTL.

Модуль не знает про HTTP и cookie: клиент Redis и время приходят аргументами, cookie ставит слой api.
"""

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

IDLE_TTL_SECONDS = 30 * 60
ABSOLUTE_TTL_SECONDS = 8 * 60 * 60
SID_BYTES = 32
SESSION_VERSION = 1
KIND_STAFF = "staff"
SESSION_PREFIX = "sess:"
STAFF_INDEX_PREFIX = "staff_sessions:"


@dataclass(frozen=True)
class SessionData:
    """Содержимое сессии; роль и csrf берутся только отсюда, не из запроса."""

    kind: str
    subject_id: UUID
    role: str
    csrf: str
    created: int
    last_seen: int
    digest: str


def sid_digest(sid: str) -> str:
    """Ключ сессии в Redis: сам SID на сервере не хранится."""
    return hashlib.sha256(sid.encode()).hexdigest()


def _key(digest: str) -> str:
    return f"{SESSION_PREFIX}{digest}"


def _staff_index(subject_id: UUID) -> str:
    return f"{STAFF_INDEX_PREFIX}{subject_id}"


async def create(redis: Redis, kind: str, subject_id: UUID, role: str, now: int | None = None) -> tuple[str, str]:
    """Создаёт новую сессию и возвращает (sid, csrf_token); SID всегда новый (защита от фиксации, TC-AUTH-05)."""
    moment = int(time.time()) if now is None else now
    sid = secrets.token_urlsafe(SID_BYTES)
    csrf = secrets.token_urlsafe(SID_BYTES)
    digest = sid_digest(sid)
    value = {
        "v": SESSION_VERSION,
        "kind": kind,
        "sub": str(subject_id),
        "role": role,
        "csrf": csrf,
        "created": moment,
        "last_seen": moment,
    }
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(_key(digest), json.dumps(value), ex=IDLE_TTL_SECONDS)
        pipe.sadd(_staff_index(subject_id), digest)
        pipe.expire(_staff_index(subject_id), ABSOLUTE_TTL_SECONDS)
        await pipe.execute()
    return sid, csrf


async def load_and_touch(redis: Redis, sid: str, now: int | None = None) -> SessionData | None:
    """Возвращает сессию и продлевает idle-срок; при исчерпании absolute-срока удаляет и возвращает None."""
    moment = int(time.time()) if now is None else now
    digest = sid_digest(sid)
    raw = await redis.get(_key(digest))
    if raw is None:
        return None
    value = json.loads(raw)
    age = moment - int(value["created"])
    if age >= ABSOLUTE_TTL_SECONDS:
        await _delete(redis, digest, UUID(value["sub"]))
        return None
    value["last_seen"] = moment
    ttl = min(IDLE_TTL_SECONDS, ABSOLUTE_TTL_SECONDS - age)
    # xx: продлеваем только существующий ключ; параллельный logout не должен воскрешать сессию
    if not await redis.set(_key(digest), json.dumps(value), ex=ttl, xx=True):
        return None
    return SessionData(
        kind=value["kind"],
        subject_id=UUID(value["sub"]),
        role=value["role"],
        csrf=value["csrf"],
        created=int(value["created"]),
        last_seen=moment,
        digest=digest,
    )


async def _delete(redis: Redis, digest: str, subject_id: UUID) -> None:
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(_key(digest))
        pipe.srem(_staff_index(subject_id), digest)
        await pipe.execute()


async def destroy(redis: Redis, sid: str) -> None:
    """Удаляет сессию по SID (logout, ротация при входе); неизвестный SID игнорируется."""
    digest = sid_digest(sid)
    raw = await redis.get(_key(digest))
    if raw is None:
        return
    await _delete(redis, digest, UUID(json.loads(raw)["sub"]))


async def destroy_all_for_subject(redis: Redis, subject_id: UUID) -> int:
    """Удаляет все сессии сотрудника (деактивация аккаунта, задача 3.3); возвращает число удалённых."""
    digests = await redis.smembers(_staff_index(subject_id))
    async with redis.pipeline(transaction=True) as pipe:
        for digest in digests:
            pipe.delete(_key(digest.decode() if isinstance(digest, bytes) else digest))
        pipe.delete(_staff_index(subject_id))
        await pipe.execute()
    return len(digests)
