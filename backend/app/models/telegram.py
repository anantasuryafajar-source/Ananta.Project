"""Tabel khusus bot Telegram (langkah 1).

Bot TIDAK punya tabel keuangan sendiri. Ia hanya butuh:
- TelegramLink   : peta chat Telegram -> user Ananta (identitas & RBAC).
- TelegramSession: state percakapan terpandu, DISIMPAN DI DB (bukan memori)
                   supaya aman meski gunicorn jalan >1 worker.
"""
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, utcnow


class TelegramLink(Base, PKMixin, TimestampMixin):
    __tablename__ = "telegram_links"
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TelegramSession(Base, PKMixin):
    """State sementara alur terpandu (mis. tambah produk)."""
    __tablename__ = "telegram_sessions"
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    flow: Mapped[str | None] = mapped_column(String(40), nullable=True)
    step: Mapped[str | None] = mapped_column(String(40), nullable=True)
    draft: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=utcnow
    )
