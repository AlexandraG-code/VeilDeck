"""Субъект запроса. Собирается только из серверной сессии и передаётся в сервисы аргументом."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    """Роли системы (staff и viewer — разные сессии)."""

    REVIEWER = "reviewer"
    ADMIN = "admin"
    VIEWER = "viewer"


@dataclass(frozen=True)
class Principal:
    """Кто делает запрос; card_id/grant_id viewer-а берутся только отсюда, не из запроса."""

    subject_id: UUID
    role: Role
    grant_id: UUID | None = None
    card_id: UUID | None = None
