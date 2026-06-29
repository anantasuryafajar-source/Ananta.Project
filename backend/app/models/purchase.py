from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, PKMixin, TimestampMixin, Money, Qty


class Bill(Base, PKMixin, TimestampMixin):
    """Tagihan pembelian / pengadaan dari supplier (barang masuk)."""
    __tablename__ = "bills"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    # draft | posted | paid | overdue | void
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    subtotal: Mapped[object] = mapped_column(Money, default=0)
    tax_total: Mapped[object] = mapped_column(Money, default=0)
    total: Mapped[object] = mapped_column(Money, default=0)
    paid_total: Mapped[object] = mapped_column(Money, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan", lazy="selectin"
    )


class BillLine(Base, PKMixin):
    __tablename__ = "bill_lines"
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[object] = mapped_column(Qty, default=1)
    unit_cost: Mapped[object] = mapped_column(Money, default=0)
    discount: Mapped[object] = mapped_column(Money, default=0)
    tax_rate: Mapped[object] = mapped_column(Money, default=0)  # persen, mis. 11
    line_total: Mapped[object] = mapped_column(Money, default=0)

    bill: Mapped["Bill"] = relationship(back_populates="lines")


class PaymentMade(Base, PKMixin, TimestampMixin):
    """Pembayaran kas/bank ke supplier untuk melunasi Bill."""
    __tablename__ = "payments_made"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[object] = mapped_column(Money)
    cash_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
