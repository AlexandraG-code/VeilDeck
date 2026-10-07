"""Конфигурация приложения (SR-32): секреты только из env, fail-fast на пустых и дефолтных значениях."""

from functools import lru_cache
from typing import Literal

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

    @field_validator("session_secret", "fernet_key", "hmac_key", "wm_key")
    @classmethod
    def secret_is_strong(cls, value: str) -> str:
        """Отклоняет короткие и дефолтные секреты (SR-32, T-20)."""
        if len(value) < MIN_SECRET_LENGTH or value.lower() in FORBIDDEN_SECRET_VALUES:
            raise ValueError("секрет пуст, короток или равен значению по умолчанию")
        return value

    @property
    def docs_enabled(self) -> bool:
        """Swagger/ReDoc выключены при ENV=demo."""
        return self.env != "demo"


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек; при ошибке процесс не стартует."""
    return Settings()  # type: ignore[call-arg]
