from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, PKMixin, TimestampMixin, Money


class Journal(Base, PKMixin, TimestampMixin):
    __tablename__ = "journals"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    # sumber: invoice | bill | payment | manual | adjustment
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    entries: Mapped[list["JournalEntry"]] = relationship(
        back_populates="journal", cascade="all, delete-orphan", lazy="selectin"
    )


class JournalEntry(Base, PKMixin):
    __tablename__ = "journal_entries"
    journal_id: Mapped[str] = mapped_column(ForeignKey("journals.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    debit: Mapped[object] = mapped_column(Money, default=0)
    credit: Mapped[object] = mapped_column(Money, default=0)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    journal: Mapped["Journal"] = relationship(back_populates="entries")
