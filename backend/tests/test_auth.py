"""Вход staff, сессии, CSRF, RBAC: TC-AUTH-01..05, TC-RBAC-05, TC-API-04 (задачи 2.2, 2.3, 2.5, 3.1, 3.2)."""

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import service
from app.core.config import get_settings
from app.core.exceptions import Unauthorized
from app.main import create_app

REQUIRED = ("TEST_DATABASE_OWNER_URL", "TEST_APP_RW_PASSWORD", "TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not all(os.getenv(key) for key in REQUIRED), reason="нужны PostgreSQL/Redis из TEST_*")
BACKEND = Path(__file__).resolve().parents[1]
ORIGIN = "https://testserver"
PASSWORD = "synthetic-test-password"
ADMIN = "admin-auth-test@example.test"
REVIEWER = "reviewer-auth-test@example.test"
LOGIN = "/api/v1/staff/auth/login"
ME = "/api/v1/staff/auth/me"
LOGOUT = "/api/v1/staff/auth/logout"
BAD_LOGIN_MESSAGE = "Неверные данные для входа"


def app_rw_url() -> str:
    """URL роли приложения в отдельной БД *_test."""
    owner = make_url(os.environ["TEST_DATABASE_OWNER_URL"])
    assert owner.database.endswith("_test"), "нужна отдельная БД *_test"
    return owner.set(username="app_rw", password=os.environ["TEST_APP_RW_PASSWORD"]).render_as_string(
        hide_password=False
    )


def run_async(coro):
    """Выполняет корутину в отдельном цикле (TestClient живёт в своём потоке)."""
    return asyncio.run(coro)


async def owner_sql(statement: str) -> None:
    """Служебный SQL под владельцем (очистка тестовых аккаунтов)."""
    engine = create_async_engine(os.environ["TEST_DATABASE_OWNER_URL"], hide_parameters=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def make_user(email: str, role: str) -> str:
    """Создаёт сотрудника тем же кодом, что CLI; возвращает base32-секрет TOTP."""
    engine = create_async_engine(app_rw_url(), hide_parameters=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            _, secret = await service.create_staff_user(session, email, PASSWORD, role)
        return secret
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def secrets_by_role():
    """Мигрирует БД, создаёт admin и reviewer; после модуля удаляет только свои аккаунты."""
    env = {
        **os.environ,
        "MIGRATION_DATABASE_URL": os.environ["TEST_DATABASE_OWNER_URL"],
        "APP_RW_PASSWORD": os.environ["TEST_APP_RW_PASSWORD"],
    }
    subprocess.run(
        [sys.executable, "-m", "scripts.bootstrap_db"], env=env, cwd=BACKEND, check=True, capture_output=True
    )  # noqa: S603
    cleanup = f"DELETE FROM staff_users WHERE email IN ('{ADMIN}', '{REVIEWER}')"
    run_async(owner_sql(cleanup))
    yield {"admin": run_async(make_user(ADMIN, "admin")), "reviewer": run_async(make_user(REVIEWER, "reviewer"))}
    run_async(owner_sql(cleanup))


@pytest.fixture
def api(secrets_by_role, monkeypatch):
    """Настоящее приложение: app_rw, настоящий Redis (БД 15), клиент по https, чтобы Secure-cookie сохранялись."""
    monkeypatch.setenv("DATABASE_URL", app_rw_url())
    monkeypatch.setenv("REDIS_URL", os.environ["TEST_REDIS_URL"])
    monkeypatch.setenv("PUBLIC_ORIGIN", ORIGIN)
    get_settings.cache_clear()

    async def reset_redis():
        redis = Redis.from_url(os.environ["TEST_REDIS_URL"])
        assert redis.connection_pool.connection_kwargs["db"] == 15
        await redis.flushdb()
        await redis.aclose()

    run_async(reset_redis())
    run_async(
        owner_sql(
            f"UPDATE staff_users SET failed_logins = 0, locked_until = NULL, totp_last_step = NULL "
            f"WHERE email IN ('{ADMIN}', '{REVIEWER}')"
        )
    )
    with TestClient(create_app(), base_url=ORIGIN, raise_server_exceptions=False) as client:
        yield client
    get_settings.cache_clear()


def totp_code(secret: str, offset: int = 0) -> str:
    """Текущий TOTP-код; сервер принимает окно ±1 шаг, перед каждым тестом счётчик повтора сбрасывается."""
    return pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=30 * offset))


def csrf(api) -> str:
    """Получает анонимный CSRF-токен (cookie ставится клиенту)."""
    return api.get("/api/v1/csrf").json()["csrf_token"]


def post(api, path, token, body=None, origin=ORIGIN):
    """POST с CSRF-заголовком и Origin, как делает браузер."""
    headers = {"X-CSRF-Token": token}
    if origin:
        headers["Origin"] = origin
    return api.post(path, json=body, headers=headers)


def login(api, secrets_by_role, role="admin", offset=0, password=PASSWORD):
    """Полный вход: csrf → login; возвращает (response, новый csrf-токен)."""
    email = ADMIN if role == "admin" else REVIEWER
    body = {"email": email, "password": password, "totp": totp_code(secrets_by_role[role], offset)}
    response = post(api, LOGIN, csrf(api), body)
    return response, (response.json().get("csrf_token") if response.status_code == 200 else None)


def test_tc_auth_01_login_sets_host_cookies(api, secrets_by_role):
    """Успешный вход: __Host-sid HttpOnly+Secure+SameSite=Strict, __Host-csrf читаем для SPA, ответ no-store."""
    response, token = login(api, secrets_by_role)
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "admin"
    cookies = {h.split("=")[0]: h.lower() for h in response.headers.get_list("set-cookie")}
    sid, csrf_cookie = cookies["__Host-sid"], cookies["__Host-csrf"]
    for attrs in (sid, csrf_cookie):
        assert "secure" in attrs and "samesite=strict" in attrs and "path=/" in attrs and "domain" not in attrs
    assert "httponly" in sid and "httponly" not in csrf_cookie
    assert response.headers["cache-control"] == "no-store"
    assert token


def test_tc_auth_02_all_failures_look_the_same(api, secrets_by_role):
    """Неверный TOTP, неверный пароль и несуществующий e-mail дают один и тот же ответ."""
    bodies = []
    for email, password, code in (
        (ADMIN, PASSWORD, "000000"),
        (ADMIN, "wrong-password-value", totp_code(secrets_by_role["admin"])),
        ("nobody@example.test", PASSWORD, "123456"),
    ):
        response = post(api, LOGIN, csrf(api), {"email": email, "password": password, "totp": code})
        assert response.status_code == 401
        bodies.append((response.json()["error"]["code"], response.json()["error"]["message"]))
    assert len(set(bodies)) == 1 and bodies[0][1] == BAD_LOGIN_MESSAGE


def test_totp_code_cannot_be_replayed(api, secrets_by_role):
    """Тот же TOTP-код второй раз отклоняется, даже в его окне."""
    first, _ = login(api, secrets_by_role)
    assert first.status_code == 200
    api.cookies.clear()
    second, _ = login(api, secrets_by_role)
    assert second.status_code == 401


def test_tc_auth_04_logout_kills_session(api, secrets_by_role):
    """После logout старая cookie не работает (401), на сервере сессии нет."""
    _, token = login(api, secrets_by_role)
    assert api.get(ME).status_code == 200
    old_cookies = dict(api.cookies)
    assert post(api, LOGOUT, token).status_code == 204
    api.cookies.clear()
    api.cookies.update(old_cookies)
    assert api.get(ME).status_code == 401


def test_tc_auth_05_session_fixation(api, secrets_by_role):
    """Подставленный до входа __Host-sid после входа не работает; выдаётся новый."""
    api.cookies.set("__Host-sid", "attacker-chosen-sid-value", domain="testserver.local", path="/")
    response, _ = login(api, secrets_by_role)
    assert response.status_code == 200
    assert api.cookies.get("__Host-sid", domain="testserver.local") != "attacker-chosen-sid-value"
    api.cookies.set("__Host-sid", "attacker-chosen-sid-value", domain="testserver.local", path="/")
    assert api.get(ME).status_code == 401


def test_tc_rbac_05_anonymous_gets_401(api):
    """Без сессии staff-API отвечает 401 в едином формате."""
    response = api.get(ME)
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "request_id"}


def test_me_returns_session_user(api, secrets_by_role):
    """me отдаёт сотрудника из серверной сессии и её CSRF-токен."""
    _, token = login(api, secrets_by_role)
    body = api.get(ME).json()
    assert (body["email"], body["role"], body["csrf_token"]) == (ADMIN, "admin", token)


@pytest.mark.parametrize("case", ["no_origin", "foreign_origin", "no_header", "wrong_header"])
def test_tc_api_04_csrf_is_enforced_on_login(api, case):
    """Изменяющий запрос без верного Origin или токена получает 403 до проверки паролей."""
    token = csrf(api)
    body = {"email": ADMIN, "password": PASSWORD, "totp": "000000"}
    headers = {"Origin": ORIGIN, "X-CSRF-Token": token}
    if case == "no_origin":
        del headers["Origin"]
    elif case == "foreign_origin":
        headers["Origin"] = "https://evil.example"
    elif case == "no_header":
        del headers["X-CSRF-Token"]
    else:
        headers["X-CSRF-Token"] = "x" * len(token)
    assert api.post(LOGIN, json=body, headers=headers).status_code == 403


def test_csrf_token_of_other_session_is_rejected(api, secrets_by_role):
    """При живой сессии токен должен совпасть и с cookie, и с токеном сессии (синхронайзер)."""
    login(api, secrets_by_role)
    foreign = "f" * 43
    api.cookies.set("__Host-csrf", foreign)
    assert post(api, LOGOUT, foreign).status_code == 403


def test_tc_auth_03_lockout_after_five_failures(secrets_by_role):
    """5 неудач блокируют вход на 15 минут даже с верными данными; потом вход возможен."""
    run_async(lockout_scenario(secrets_by_role["reviewer"]))


async def lockout_scenario(secret: str) -> None:
    """Сервисный уровень с подставным временем: ни одного sleep."""
    redis = Redis.from_url(os.environ["TEST_REDIS_URL"])
    engine = create_async_engine(app_rw_url(), hide_parameters=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC) + timedelta(hours=2)
    try:
        await owner_sql(
            f"UPDATE staff_users SET failed_logins = 0, locked_until = NULL, totp_last_step = NULL "
            f"WHERE email = '{REVIEWER}'"
        )
        for _ in range(5):
            async with sessions() as session:
                with pytest.raises(Unauthorized):
                    await service.login(session, redis, REVIEWER, "wrong-password-value", "000000", now)
        good_code = pyotp.TOTP(secret).at(now)
        async with sessions() as session:
            with pytest.raises(Unauthorized):  # верные данные, но аккаунт заблокирован
                await service.login(session, redis, REVIEWER, PASSWORD, good_code, now)
        later = now + timedelta(minutes=16)
        async with sessions() as session:
            sid, _, role = await service.login(session, redis, REVIEWER, PASSWORD, pyotp.TOTP(secret).at(later), later)
        assert sid and role == "reviewer"
    finally:
        await redis.aclose()
        await engine.dispose()


@pytest.mark.parametrize("password", [PASSWORD, "wrong-password-value"])
def test_non_ascii_totp_is_rejected_the_same(api, password):
    """Юникодные цифры в TOTP отклоняются одинаково при верном и неверном пароле (нет оракула пароля, нет 500)."""
    body = {"email": ADMIN, "password": password, "totp": "\u0661\u0662\u0663\u0664\u0665\u0666"}
    response = post(api, LOGIN, csrf(api), body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
