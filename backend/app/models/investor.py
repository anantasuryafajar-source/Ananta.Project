from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money


class Investor(Base, PKMixin, TimestampMixin):
    """Investor & skema bagi hasil (mirip sheet INVESTOR)."""
    __tablename__ = "investors"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    scheme: Mapped[str | None] = mapped_column(String(60), nullable=True)   # mis. "Opsi III"
    principal: Mapped[object] = mapped_column(Money, default=0)              # dana pokok
    received_total: Mapped[object] = mapped_column(Money, default=0)         # dana pokok yang sudah diterima
    roi_rate: Mapped[object] = mapped_column(Money, default=0)               # % per periode (info)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # active | closed
    status: Mapped[str] = mapped_column(String(12), default="active", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvestorPayout(Base, PKMixin, TimestampMixin):
    """Pembayaran ke investor. type: dividend (beban) | principal (pengembalian pokok)."""
    __tablename__ = "investor_payouts"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    investor_id: Mapped[str] = mapped_column(ForeignKey("investors.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    type: Mapped[str] = mapped_column(String(12))  # dividend | principal
    amount: Mapped[object] = mapped_column(Money)
    paid_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
