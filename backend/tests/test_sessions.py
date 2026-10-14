"""Серверные сессии: TTL idle/absolute, ротация, удаление, индекс сессий сотрудника (TC-AUTH-04, TC-AUTH-05)."""

from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.core import sessions

SUBJECT = uuid4()
START = 1_000_000


@pytest.fixture
def redis():
    """Redis в памяти: проверяем логику сессий без сети."""
    return fakeredis.aioredis.FakeRedis()


async def test_create_and_load(redis):
    """Новая сессия читается по SID; в Redis лежит только SHA-256 от SID."""
    sid, csrf = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    data = await sessions.load_and_touch(redis, sid, now=START + 5)
    assert data is not None
    assert (data.subject_id, data.role, data.csrf) == (SUBJECT, "admin", csrf)
    assert not await redis.exists(f"sess:{sid}")
    assert await redis.exists(f"sess:{sessions.sid_digest(sid)}")


async def test_sid_is_unique_and_long(redis):
    """Каждый вход выдаёт новый SID (фиксация сессии невозможна), длина ≥ 128 бит."""
    first, _ = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    second, _ = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    assert first != second
    assert len(first) >= 43


async def test_unknown_sid_is_rejected(redis):
    """Неизвестный (подставленный) SID не даёт сессии."""
    assert await sessions.load_and_touch(redis, "attacker-chosen-sid", now=START) is None


async def test_destroy_invalidates_session(redis):
    """После logout старая cookie не работает (TC-AUTH-04)."""
    sid, _ = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    await sessions.destroy(redis, sid)
    assert await sessions.load_and_touch(redis, sid, now=START + 1) is None
    assert await redis.scard(f"staff_sessions:{SUBJECT}") == 0


async def test_absolute_ttl_expires_even_when_active(redis):
    """Сессия живёт не дольше 8 часов, сколько бы её ни продлевали."""
    sid, _ = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    step = sessions.IDLE_TTL_SECONDS - 1
    moment = START
    while moment + step < START + sessions.ABSOLUTE_TTL_SECONDS:
        moment += step
        assert await sessions.load_and_touch(redis, sid, now=moment) is not None
    assert await sessions.load_and_touch(redis, sid, now=START + sessions.ABSOLUTE_TTL_SECONDS) is None
    assert not await redis.exists(f"sess:{sessions.sid_digest(sid)}")


async def test_idle_ttl_is_set_and_capped(redis):
    """Redis TTL = idle (30 мин), а у старой сессии не больше остатка до absolute."""
    sid, _ = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    key = f"sess:{sessions.sid_digest(sid)}"
    assert 0 < await redis.ttl(key) <= sessions.IDLE_TTL_SECONDS
    late = START + sessions.ABSOLUTE_TTL_SECONDS - 60
    await sessions.load_and_touch(redis, sid, now=late)
    assert await redis.ttl(key) <= 60


async def test_destroy_all_for_subject(redis):
    """Деактивация сотрудника завершает все его сессии сразу."""
    sids = [(await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "reviewer", now=START))[0] for _ in range(3)]
    assert await sessions.destroy_all_for_subject(redis, SUBJECT) == 3
    for sid in sids:
        assert await sessions.load_and_touch(redis, sid, now=START + 1) is None


async def test_touch_does_not_resurrect_destroyed_session(redis, monkeypatch):
    """Гонка: logout между чтением и продлением не должен вернуть сессию к жизни."""
    sid, _ = await sessions.create(redis, sessions.KIND_STAFF, SUBJECT, "admin", now=START)
    original_get = redis.get

    async def get_then_logout(key):
        raw = await original_get(key)
        await redis.delete(key)  # параллельный logout удаляет ключ между чтением и продлением
        return raw

    monkeypatch.setattr(redis, "get", get_then_logout)
    assert await sessions.load_and_touch(redis, sid, now=START + 1) is None
    assert not await redis.exists(f"sess:{sessions.sid_digest(sid)}")
