from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, PKMixin, TimestampMixin, Money, Qty


# ============================= PURCHASE ORDER =============================
class PurchaseOrder(Base, PKMixin, TimestampMixin):
    """Pesanan pembelian ke supplier (tahap sebelum Bill/barang masuk)."""
    __tablename__ = "purchase_orders"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    # draft | confirmed | received | cancelled  (received = sudah jadi Bill)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    subtotal: Mapped[object] = mapped_column(Money, default=0)
    tax_total: Mapped[object] = mapped_column(Money, default=0)
    total: Mapped[object] = mapped_column(Money, default=0)
    # ongkir & pembagian dengan supplier (proses #3 ASF)
    freight_total: Mapped[object] = mapped_column(Money, default=0)
    freight_supplier_share: Mapped[object] = mapped_column(Money, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    bill_id: Mapped[str | None] = mapped_column(ForeignKey("bills.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["POLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class POLine(Base, PKMixin):
    __tablename__ = "purchase_order_lines"
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[object] = mapped_column(Qty, default=1)
    unit_cost: Mapped[object] = mapped_column(Money, default=0)
    discount: Mapped[object] = mapped_column(Money, default=0)
    tax_rate: Mapped[object] = mapped_column(Money, default=0)
    line_total: Mapped[object] = mapped_column(Money, default=0)
    order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")


# ============================= SALES ORDER =============================
class SalesOrder(Base, PKMixin, TimestampMixin):
    """Pesanan pelanggan (tahap sebelum Invoice & pengiriman)."""
    __tablename__ = "sales_orders"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    # draft | confirmed | delivered | invoiced | cancelled
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    subtotal: Mapped[object] = mapped_column(Money, default=0)
    tax_total: Mapped[object] = mapped_column(Money, default=0)
    total: Mapped[object] = mapped_column(Money, default=0)
    # pengiriman
    delivery_status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|shipped|delivered
    courier_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["SOLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class SOLine(Base, PKMixin):
    __tablename__ = "sales_order_lines"
    order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[object] = mapped_column(Qty, default=1)
    unit_price: Mapped[object] = mapped_column(Money, default=0)
    discount: Mapped[object] = mapped_column(Money, default=0)
    tax_rate: Mapped[object] = mapped_column(Money, default=0)
    line_total: Mapped[object] = mapped_column(Money, default=0)
    order: Mapped["SalesOrder"] = relationship(back_populates="lines")
