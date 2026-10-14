"""cards: Pydantic-схемы запросов и ответов домена (extra="forbid")."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.card_fields import CardStatus, DealType, Industry, RegionMacro, RevenueBand, SizeBand

TITLE_MAX = 80
TEASER_MAX = 600
ORG_NAME_MAX = 200
ALIAS_MAX = 200
ALIASES_MAX_COUNT = 10
DESCRIPTION_MAX = 20000

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX)]
Teaser = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TEASER_MAX)]
OrgName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ORG_NAME_MAX)]
Alias = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ALIAS_MAX)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX)]


class CardCreateIn(BaseModel):
    """Создание черновика. id, status, created_by и published_at сюда не входят: лишнее поле даёт 422 (TC-API-02)."""

    model_config = ConfigDict(extra="forbid")
    title_generic: Title
    industry: Industry
    region_macro: RegionMacro
    size_band: SizeBand
    revenue_band: RevenueBand
    deal_type: DealType
    teaser_text: Teaser
    org_name: OrgName
    org_aliases: list[Alias] = Field(default_factory=list, max_length=ALIASES_MAX_COUNT)
    full_description: Description


class ViolationOut(BaseModel):
    """Нарушение линтера утечек: только код вида и имя поля, без фрагментов текста."""

    model_config = ConfigDict(extra="forbid")
    code: str
    field: str


class TeaserLeakErrorBody(BaseModel):
    """Тело ошибки 422 teaser_leak (для OpenAPI)."""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    request_id: str
    violations: list[ViolationOut]


class TeaserLeakError(BaseModel):
    """Обёртка единого формата ошибки (для OpenAPI)."""

    model_config = ConfigDict(extra="forbid")
    error: TeaserLeakErrorBody


class CardFull(BaseModel):
    """Полная карточка для staff: включает конфиденциальные поля, наружу публичному API не отдаётся."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    status: CardStatus
    title_generic: str
    industry: Industry
    region_macro: RegionMacro
    size_band: SizeBand
    revenue_band: RevenueBand
    deal_type: DealType
    teaser_text: str
    org_name: str
    org_aliases: list[str]
    full_description: str
    created_by: UUID | None
    published_at: datetime | None
