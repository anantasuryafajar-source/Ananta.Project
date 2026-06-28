from sqlalchemy import String, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money


class Contact(Base, PKMixin, TimestampMixin):
    __tablename__ = "contacts"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    # customer | supplier | both
    type: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    npwp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    payment_term_days: Mapped[int] = mapped_column(Integer, default=0)
    credit_limit: Mapped[object] = mapped_column(Money, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
