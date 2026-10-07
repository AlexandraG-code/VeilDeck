"""Проверка живости для compose/healthcheck."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Ответ /healthz."""

    model_config = ConfigDict(extra="forbid")
    status: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Возвращает признак живости процесса, без обращения к БД."""
    return HealthResponse(status="ok")
