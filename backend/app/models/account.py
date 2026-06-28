from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin


class Account(Base, PKMixin, TimestampMixin):
    """Bagan Akun (Chart of Accounts) standar Indonesia."""
    __tablename__ = "accounts"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(160))
    # asset, liability, equity, income, expense
    type: Mapped[str] = mapped_column(String(20), index=True)
    # normal balance: 'debit' atau 'credit'
    normal_balance: Mapped[str] = mapped_column(String(6))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
