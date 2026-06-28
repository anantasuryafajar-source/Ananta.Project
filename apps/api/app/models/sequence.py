from sqlalchemy import String, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin


class DocumentSequence(Base, PKMixin):
    """Penomoran dokumen otomatis dengan prefix & reset periode."""
    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("company_id", "doc_type", "period_key"),)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    # invoice | bill | journal | po | so | quotation | payment
    doc_type: Mapped[str] = mapped_column(String(20))
    prefix: Mapped[str] = mapped_column(String(16), default="")
    # 'YYYYMM' untuk reset bulanan, 'YYYY' tahunan, '' tanpa reset
    period_key: Mapped[str] = mapped_column(String(8), default="")
    next_number: Mapped[int] = mapped_column(Integer, default=1)
    padding: Mapped[int] = mapped_column(Integer, default=4)
