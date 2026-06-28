from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin


class Company(Base, PKMixin, TimestampMixin):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(160))
    npwp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    # Metode HPP per perusahaan: 'fifo' atau 'average'
    costing_method: Mapped[str] = mapped_column(String(10), default="average")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Warehouse(Base, PKMixin, TimestampMixin):
    __tablename__ = "warehouses"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
