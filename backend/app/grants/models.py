"""grants: ORM-модели домена; связи с чужими доменами только через ForeignKey-строку."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Grant(Base):
    """Право доступа viewer-а к карточке и подмножеству материалов на ограниченный срок."""

    __tablename__ = "grants"
    __table_args__ = (
        CheckConstraint("max_views BETWEEN 1 AND 100", name="grant_max_views_range"),
        CheckConstraint("views_used >= 0 AND views_used <= max_views", name="grant_views_used_range"),
        CheckConstraint("cardinality(material_ids) >= 1 OR revoked_at IS NOT NULL", name="grant_materials_or_revoked"),
        Index("ix_grants_card_id", "card_id"),
        Index("ix_grants_expires_at", "expires_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("access_requests.id", ondelete="RESTRICT"), unique=True)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"))
    viewer_pseudonym: Mapped[str] = mapped_column(String(32), unique=True)
    material_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    allow_download: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_views: Mapped[int] = mapped_column(Integer)
    views_used: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_users.id", ondelete="RESTRICT"))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    expiry_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MagicLink(Base):
    """Одноразовая ссылка: в БД только SHA-256 токена; погашение — атомарный UPDATE used_at."""

    __tablename__ = "magic_links"
    __table_args__ = (
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="magic_link_token_hash_hex"),
        Index("ix_magic_links_grant_id", "grant_id"),
        Index("ix_magic_links_expires_at", "expires_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    grant_id: Mapped[UUID] = mapped_column(ForeignKey("grants.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
