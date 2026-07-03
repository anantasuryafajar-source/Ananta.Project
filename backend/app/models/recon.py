from datetime import date
from sqlalchemy import String, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin


class BankReconMark(Base, PKMixin, TimestampMixin):
    """Penanda bahwa satu baris jurnal (entry) pada akun bank sudah dicocokkan
    dengan rekening koran. Menandai/melepas bersifat toggle."""
    __tablename__ = "bank_recon_marks"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.id"), index=True, unique=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    statement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    marked_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
