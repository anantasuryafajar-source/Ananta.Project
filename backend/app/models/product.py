from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money, Qty


class ProductCategory(Base, PKMixin):
    __tablename__ = "product_categories"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))


class Product(Base, PKMixin, TimestampMixin):
    __tablename__ = "products"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    sku: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    # 'good' (barang, kelola stok) | 'service' (jasa)
    kind: Mapped[str] = mapped_column(String(10), default="good")
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    sale_price: Mapped[object] = mapped_column(Money, default=0)
    purchase_price: Mapped[object] = mapped_column(Money, default=0)
    min_stock: Mapped[object] = mapped_column(Qty, default=0)
    # akun terkait (opsional override default perusahaan)
    income_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    inventory_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    cogs_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class StockLevel(Base, PKMixin):
    """Saldo stok per produk per gudang (real-time)."""
    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    quantity: Mapped[object] = mapped_column(Qty, default=0)
    # nilai rata-rata berjalan untuk metode average
    avg_cost: Mapped[object] = mapped_column(Money, default=0)


class StockMovement(Base, PKMixin, TimestampMixin):
    __tablename__ = "stock_movements"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    # in | out | adjustment | transfer
    direction: Mapped[str] = mapped_column(String(12))
    quantity: Mapped[object] = mapped_column(Qty)
    unit_cost: Mapped[object] = mapped_column(Money, default=0)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
