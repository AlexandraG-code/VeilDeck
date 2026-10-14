"""auth: вход сотрудников и создание аккаунтов; без FastAPI/HTTP, сессия БД и Redis приходят аргументами.

Угрозы и требования: T-04/SR-04 (серверная сессия), T-05/SR-12 (перебор: lockout, dummy-хеш), SR-13 (TOTP без повтора).
"""

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import repository
from app.auth.models import StaffUser
from app.core import sessions
from app.core.crypto import fernet_decrypt, fernet_encrypt
from app.core.exceptions import Conflict, Unauthorized

LOGIN_FAILED_MESSAGE = "Неверные данные для входа"
LOCKOUT = timedelta(minutes=15)
TOTP_INTERVAL_SECONDS = 30
TOTP_WINDOW_STEPS = (-1, 0, 1)
STAFF_ROLES = ("reviewer", "admin")
MIN_PASSWORD_LENGTH = 12

_hasher = PasswordHasher()


# Считается при импорте, а не лениво: первый запрос с несуществующим e-mail не должен быть медленнее остальных
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def _password_ok(stored_hash: str, password: str) -> bool:
    """Проверяет пароль; любая ошибка формата хеша считается неудачей."""
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _matching_step(secret: str, code: str, now: datetime) -> int | None:
    """Возвращает шаг TOTP, которому соответствует код в окне ±1 (сравнение за постоянное время), иначе None."""
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL_SECONDS)
    current = int(now.timestamp()) // TOTP_INTERVAL_SECONDS
    matched = None
    if not (code.isascii() and code.isdigit()):
        return None  # ни одно исключение не должно выйти из login: иначе пароль можно проверять без TOTP
    for offset in TOTP_WINDOW_STEPS:
        step = current + offset
        if hmac.compare_digest(totp.generate_otp(step).encode(), code.encode()):
            matched = step
    return matched


async def login(
    session: AsyncSession, redis: Redis, email: str, password: str, totp: str, now: datetime | None = None
) -> tuple[str, str, str]:
    """Проверяет пароль и TOTP, создаёт новую сессию; возвращает (sid, csrf, role). Любой отказ — одно сообщение."""
    moment = now or datetime.now(UTC)
    user_id: UUID | None = None
    role = ""
    failed = True
    async with session.begin():
        user = await repository.get_by_email(session, email)
        password_ok = _password_ok(user.password_hash if user else DUMMY_HASH, password)
        usable = user is not None and user.is_active and not (user.locked_until and user.locked_until > moment)
        if user is not None and usable and password_ok:
            step = _matching_step(fernet_decrypt(user.totp_secret_enc), totp, moment)
            if step is not None and await repository.accept_totp_step(session, user.id, step):
                failed, user_id, role = False, user.id, user.role
        if failed:
            # Одинаковый набор операций с БД для любого отказа: для несуществующего, неактивного и заблокированного
            # аккаунта UPDATE уходит на случайный id и ничего не меняет, поэтому по времени и записи отличий нет.
            target = user.id if user is not None and usable else uuid4()
            await repository.register_failure(session, target, moment + LOCKOUT)
    if failed or user_id is None:
        raise Unauthorized(LOGIN_FAILED_MESSAGE)
    sid, csrf = await sessions.create(redis, sessions.KIND_STAFF, user_id, role, now=int(moment.timestamp()))
    return sid, csrf, role


async def get_user(session: AsyncSession, user_id: UUID) -> StaffUser:
    """Возвращает сотрудника сессии; если аккаунт исчез или отключён, сессия считается недействительной."""
    async with session.begin():
        user = await repository.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise Unauthorized()
    return user


async def create_staff_user(session: AsyncSession, email: str, password: str, role: str) -> tuple[str, str]:
    """Создаёт сотрудника (только CLI): argon2id-хеш и TOTP-секрет в Fernet; возвращает (otpauth URI, base32-секрет)."""
    if role not in STAFF_ROLES or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Недопустимая роль или слишком короткий пароль")
    normalized = email.strip().lower()
    secret = pyotp.random_base32()
    async with session.begin():
        if await repository.get_by_email(session, normalized) is not None:
            raise Conflict("Сотрудник с таким e-mail уже существует")
        repository.add(
            session,
            StaffUser(
                email=normalized,
                password_hash=_hasher.hash(password),
                totp_secret_enc=fernet_encrypt(secret),
                role=role,
            ),
        )
    return pyotp.TOTP(secret).provisioning_uri(name=normalized, issuer_name="VeilDeck"), secret
