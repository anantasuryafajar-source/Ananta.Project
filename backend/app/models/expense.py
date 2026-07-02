from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money


class Expense(Base, PKMixin, TimestampMixin):
    """Beban operasional umum (armada, kantor, dll). Jurnal: Dr beban, Cr kas/bank."""
    __tablename__ = "expenses"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # armada | umum | lainnya (label bebas untuk filter)
    category: Mapped[str] = mapped_column(String(20), default="umum", index=True)
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[object] = mapped_column(Money)
    expense_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    paid_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class EmployeeLoan(Base, PKMixin, TimestampMixin):
    """Kasbon / pinjaman karyawan (mirip sheet LOAN ASF).
    Beri pinjaman: Dr Piutang Karyawan (1-1600), Cr kas.
    Terima cicilan: Dr kas, Cr Piutang Karyawan."""
    __tablename__ = "employee_loans"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    employee_name: Mapped[str] = mapped_column(String(120))
    date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[object] = mapped_column(Money)
    repaid_total: Mapped[object] = mapped_column(Money, default=0)
    # active | paid
    status: Mapped[str] = mapped_column(String(12), default="active", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
