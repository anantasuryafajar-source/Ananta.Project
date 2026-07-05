"""Tabel Asisten AI web (riwayat percakapan per pengguna).

Terpisah dari bot Telegram. Menyimpan percakapan agar riwayat muncul di sidebar
dan tidak hilang saat refresh / ganti perangkat.
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin


class AiConversation(Base, PKMixin, TimestampMixin):
    __tablename__ = "ai_conversations"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Percakapan baru")


class AiMessage(Base, PKMixin):
    __tablename__ = "ai_messages"
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
