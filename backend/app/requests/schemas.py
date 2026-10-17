"""requests: Pydantic-схемы запросов и ответов домена (extra="forbid")."""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ModelWrapValidatorHandler, field_validator, model_validator

EMAIL_MAX_LENGTH = 254
DISPLAY_NAME_MAX_LENGTH = 60
PURPOSE_MAX_LENGTH = 1000
HONEYPOT_MAX_LENGTH = 200
# Практичная проверка адреса по allowlist символов: local@domain.tld; без пробелов, скобок и кавычек (SR-18)
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+\-]{1,64}@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)
# Буквы и цифры любых алфавитов, пробел и дефис (без подчёркивания)
DISPLAY_NAME_PATTERN = re.compile(r"^(?:[^\W_]|[ \-])+$")


class AccessRequestIn(BaseModel):
    """Форма запроса расширенного доступа (SR-17: лишние поля, status и card_id в теле отвергаются)."""

    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=EMAIL_MAX_LENGTH)
    display_name: str = Field(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)
    purpose: str = Field(min_length=1, max_length=PURPOSE_MAX_LENGTH)
    consent: Literal[True]
    # Honeypot: легитимная форма оставляет поле пустым, заполненное — признак бота (запрос молча не создаётся)
    website: str = Field(default="", max_length=HONEYPOT_MAX_LENGTH)

    @model_validator(mode="wrap")
    @classmethod
    def honeypot_short_circuit(
        cls, data: Any, handler: ModelWrapValidatorHandler["AccessRequestIn"]
    ) -> "AccessRequestIn":
        """Заполненный honeypot не проверяет остальные поля: ответ бота (202) не зависит от их валидности (SR-23)."""
        website = data.get("website") if isinstance(data, dict) else None
        if isinstance(website, str) and website:
            return cls.model_construct(website=website)
        return handler(data)

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str) -> str:
        """Нормализует (trim, нижний регистр) и проверяет адрес."""
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("некорректный e-mail")
        return normalized

    @field_validator("display_name")
    @classmethod
    def display_name_is_valid(cls, value: str) -> str:
        """Только буквы, цифры, пробел и дефис."""
        stripped = value.strip()
        if not stripped or not DISPLAY_NAME_PATTERN.fullmatch(stripped):
            raise ValueError("недопустимые символы в имени")
        return stripped

    @field_validator("purpose")
    @classmethod
    def purpose_is_not_blank(cls, value: str) -> str:
        """Текст сохраняется как есть (экранирование при выводе); пустой после trim не принимается."""
        if not value.strip():
            raise ValueError("пустая цель запроса")
        return value


class AccessRequestOut(BaseModel):
    """Единый ответ на отправку: не зависит от исхода (SR-23, T-02)."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["received"] = "received"
