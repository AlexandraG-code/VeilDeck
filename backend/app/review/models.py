"""review: ORM-модели домена; связи с чужими доменами только через ForeignKey-строку."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Decision(Base):
    """Решение по запросу: единственное (UNIQUE request_id), неизменяемое (у app_rw только INSERT/SELECT)."""

    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('approve', 'reject')", name="decision_kind"),
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN "
            "('insufficient_profile', 'not_qualified', 'conflict_of_interest', 'capacity_limit', 'other')",
            name="decision_reason_code",
        ),
        CheckConstraint("(decision = 'reject') = (reason_code IS NOT NULL)", name="decision_reject_has_reason"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("access_requests.id", ondelete="RESTRICT"), unique=True)
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("staff_users.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str | None] = mapped_column(String(32))
    comment_internal: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
