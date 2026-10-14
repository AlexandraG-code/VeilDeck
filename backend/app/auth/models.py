"""auth: ORM-модели домена; связи с чужими доменами только через ForeignKey-строку."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StaffUser(Base):
    """Сотрудник (reviewer/admin): пароль argon2id, TOTP-секрет только в виде Fernet; регистрации через UI нет."""

    __tablename__ = "staff_users"
    __table_args__ = (CheckConstraint("role IN ('reviewer', 'admin')", name="staff_role"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(Text)
    totp_secret_enc: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    failed_logins: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


Index("uq_staff_users_email_lower", func.lower(StaffUser.email), unique=True)
