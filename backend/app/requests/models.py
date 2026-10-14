"""requests: ORM-модели домена; связи с чужими доменами только через ForeignKey-строку."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccessRequest(Base):
    """Запрос доступа: e-mail только Fernet + HMAC, персональные поля обнуляет retention (статус purged)."""

    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'withdrawn', 'purged')", name="request_status"
        ),
        CheckConstraint("email_hash ~ '^[0-9a-f]{64}$'", name="request_email_hash_hex"),
        CheckConstraint("char_length(display_name) <= 60", name="request_display_name_len"),
        CheckConstraint("char_length(purpose) <= 1000", name="request_purpose_len"),
        Index("ix_access_requests_status_created_at", "status", "created_at"),
        Index("ix_access_requests_status_retain_until", "status", "retain_until"),
        # Атомарный дедуп повторного запроса на ту же карточку с того же e-mail
        Index(
            "uq_access_requests_pending",
            "card_id",
            "email_hash",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"))
    email_enc: Mapped[str | None] = mapped_column(Text)
    email_hash: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(60))
    purpose: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
