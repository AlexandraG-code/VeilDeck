"""Экспорт OpenAPI в docs/api/openapi.json (контракт для генерации клиента фронта).

Запуск: python -m scripts.export_openapi [путь]. Секреты подставляются фиктивные: приложению нужен только импорт.
"""

import json
import os
import sys
from pathlib import Path

FAKE_ENV = {
    "ENV": "dev",
    "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
    "REDIS_URL": "redis://localhost:6379/0",
    "SESSION_SECRET": "s" * 40,
    "FERNET_KEY": "f" * 40,
    "HMAC_KEY": "h" * 40,
    "WM_KEY": "w" * 40,
}
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def main() -> None:
    """Записывает детерминированный OpenAPI (сортировка ключей, перевод строки в конце)."""
    for key, value in FAKE_ENV.items():
        os.environ[key] = value
    from app.main import app

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
