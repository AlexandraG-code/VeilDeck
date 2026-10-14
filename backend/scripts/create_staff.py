"""Создание сотрудника (admin/reviewer): регистрации через UI нет (задача 3.1).

Запуск на стенде (exec, а не run: вывод run попал бы в логи контейнера):
  docker compose -f deploy/docker-compose.prod.yml exec api \\
    python -m scripts.create_staff --email a@demo.invalid --role admin
Пароль вводится интерактивно (getpass, дважды) или читается из stdin с --password-stdin; в argv его нет.
TOTP-секрет и otpauth URI печатаются один раз в stdout и нигде не сохраняются и не логируются.
"""

import argparse
import asyncio
import getpass
import sys

from app.auth.service import MIN_PASSWORD_LENGTH, STAFF_ROLES, create_staff_user
from app.core.config import get_settings
from app.core.database import Database
from app.core.exceptions import Conflict


def read_password(from_stdin: bool) -> str:
    """Читает пароль без эха; при двух вводах требует совпадения."""
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Пароль: ")
    if first != getpass.getpass("Повторите пароль: "):
        sys.exit("Пароли не совпадают")
    return first


async def run(email: str, role: str, password: str) -> None:
    """Создаёт сотрудника под ролью app_rw и печатает данные для TOTP-приложения."""
    database = Database(get_settings().database_url)
    try:
        async with database.sessions() as session:
            uri, secret = await create_staff_user(session, email, password, role)
    finally:
        await database.close()
    print(f"Сотрудник {email.strip().lower()} ({role}) создан.")
    print(f"TOTP: добавьте в приложение-аутентификатор URI или секрет вручную.\nURI: {uri}\nСекрет: {secret}")


def main() -> None:
    """Разбирает аргументы и создаёт сотрудника; ошибки без стек-трейса и без пароля."""
    parser = argparse.ArgumentParser(description="Создать сотрудника VeilDeck")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=STAFF_ROLES)
    parser.add_argument("--password-stdin", action="store_true", help="прочитать пароль из stdin")
    args = parser.parse_args()
    password = read_password(args.password_stdin)
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Пароль короче {MIN_PASSWORD_LENGTH} символов")
    try:
        asyncio.run(run(args.email, args.role, password))
    except Conflict as error:
        sys.exit(error.message)


if __name__ == "__main__":
    main()
