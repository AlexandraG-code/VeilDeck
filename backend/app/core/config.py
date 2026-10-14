"""Конфигурация приложения (SR-32): секреты только из env, fail-fast на пустых и дефолтных значениях."""

from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LENGTH = 32
FORBIDDEN_SECRET_VALUES = frozenset({"changeme", "change-me", "secret", "password", "default", "test"})


class Settings(BaseSettings):
    """Настройки из env; обязательные поля не имеют значений по умолчанию."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    env: Literal["demo", "dev", "test"] = Field(alias="ENV")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    session_secret: str = Field(alias="SESSION_SECRET")
    fernet_key: str = Field(alias="FERNET_KEY")
    hmac_key: str = Field(alias="HMAC_KEY")
    wm_key: str = Field(alias="WM_KEY")
    enable_docs: bool = Field(default=False, alias="ENABLE_DOCS")
    public_origin: str = Field(alias="PUBLIC_ORIGIN")

    @field_validator("session_secret", "fernet_key", "hmac_key", "wm_key")
    @classmethod
    def secret_is_strong(cls, value: str) -> str:
        """Отклоняет короткие и дефолтные секреты (SR-32, T-20)."""
        if len(value) < MIN_SECRET_LENGTH or value.lower() in FORBIDDEN_SECRET_VALUES:
            raise ValueError("секрет пуст, короток или равен значению по умолчанию")
        return value

    @field_validator("fernet_key")
    @classmethod
    def fernet_key_is_valid(cls, value: str) -> str:
        """FERNET_KEY должен быть корректным ключом Fernet (32 байта base64url), иначе приложение не стартует."""
        try:
            Fernet(value)
        except (ValueError, TypeError) as error:
            raise ValueError("FERNET_KEY не является ключом Fernet") from error
        return value

    @field_validator("public_origin")
    @classmethod
    def origin_is_https(cls, value: str) -> str:
        """PUBLIC_ORIGIN — только схема и хост (https://host[:port]): с ним сверяется заголовок Origin (CSRF)."""
        if not value.startswith("https://") or value.endswith("/") or value.count("/") != 2:
            raise ValueError("PUBLIC_ORIGIN должен иметь вид https://host[:port] без завершающего слеша")
        return value

    @property
    def docs_enabled(self) -> bool:
        """Swagger/ReDoc выключены при ENV=demo, если явно не задан ENABLE_DOCS=true (демо-стенд за basic auth)."""
        return self.env != "demo" or self.enable_docs


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек; при ошибке процесс не стартует."""
    return Settings()  # type: ignore[call-arg]
