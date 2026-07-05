from datetime import datetime
from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin


class User(Base, PKMixin, TimestampMixin):
    __tablename__ = "users"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reset_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reset_expires: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # --- kode tautan bot Telegram (langkah 2) ---
    telegram_link_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    telegram_link_expires: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Role(Base, PKMixin):
    __tablename__ = "roles"
    # owner, finance, sales, warehouse, viewer
    name: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(80))


class UserRole(Base, PKMixin):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)
