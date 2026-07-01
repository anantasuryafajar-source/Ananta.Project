from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money


class CourierExpense(Base, PKMixin, TimestampMixin):
    """Biaya kurir/ekspedisi, opsional ditautkan ke faktur penjualan.

    Mendukung 'split dengan supplier': bagian yang ditanggung ASF
    (company_share) menjadi beban, bagian supplier (supplier_share)
    mengurangi utang ke supplier.
    """
    __tablename__ = "courier_expenses"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    courier_name: Mapped[str] = mapped_column(String(120))
    # faktur penjualan terkait (opsional) — untuk laporan ongkir per faktur
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)
    # supplier yang berbagi ongkir (opsional)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    amount: Mapped[object] = mapped_column(Money, default=0)           # total ongkir
    supplier_share: Mapped[object] = mapped_column(Money, default=0)   # ditanggung supplier
    company_share: Mapped[object] = mapped_column(Money, default=0)    # ditanggung ASF
    paid_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))  # kas/bank
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
