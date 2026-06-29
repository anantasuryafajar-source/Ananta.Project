import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    # Semua `Mapped[str]` polos (PK id & semua FK ke *.id berupa UUID) dipetakan
    # ke VARCHAR(36) agar tipe kolom PK dan FK SAMA PERSIS. Tanpa ini, PostgreSQL
    # menolak FK ("foreign key constraint cannot be implemented").
    # Kolom dengan String(n) eksplisit atau Text TIDAK terpengaruh.
    type_annotation_map = {str: String(36)}


# Tipe uang seragam: Numeric(18,2). JANGAN pakai float untuk nilai uang.
Money = Numeric(18, 2)
Qty = Numeric(18, 4)
ZERO = Decimal("0.00")


class PKMixin:
    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=utcnow
    )
