"""auth: Pydantic-схемы запросов и ответов домена (extra="forbid")."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_MAX = 254
PASSWORD_MAX = 128
TOTP_PATTERN = r"^[0-9]{6}$"  # только ASCII: \d принял бы юникодные цифры


class LoginIn(BaseModel):
    """Вход сотрудника: e-mail, пароль и обязательный TOTP-код."""

    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=EMAIL_MAX)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)
    totp: str = Field(pattern=TOTP_PATTERN)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Приводит e-mail к нижнему регистру без пробелов по краям."""
        return value.strip().lower()


class LoginOut(BaseModel):
    """Ответ входа: CSRF-токен для заголовка X-CSRF-Token и роль для интерфейса."""

    model_config = ConfigDict(extra="forbid")
    csrf_token: str
    role: str


class MeOut(BaseModel):
    """Текущий сотрудник из серверной сессии."""

    model_config = ConfigDict(extra="forbid")
    id: str
    email: str
    role: str
    csrf_token: str
