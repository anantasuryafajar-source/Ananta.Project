from sqlalchemy import String, ForeignKey, Boolean, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money, Qty, UnitCost


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
    # --- Satuan (lihat services/units.py untuk aturan lengkapnya) ---
    # Satuan DASAR penyimpanan: stok, HPP, dan valuasi selalu dalam satuan ini.
    unit: Mapped[str] = mapped_column(String(20), default="botol")
    # Satuan kemasan yang dipakai saat input/tampil.
    pack_unit: Mapped[str] = mapped_column(String(20), default="dus")
    # Isi per kemasan, mis. 24 botol/dus. WAJIB benar per produk — bukan
    # konstanta global, karena kemasan berbeda per SKU (ASF: 24 / 48 / 12).
    pack_size: Mapped[int] = mapped_column(Integer, default=12)

    # Harga jual TIDAK lagi diinput di master produk (harga jual ditentukan per
    # customer saat pembuatan faktur). Kolom dipertahankan sebagai harga acuan
    # opsional & kompatibilitas laporan; biarkan 0 bila tidak dipakai.
    sale_price: Mapped[object] = mapped_column(Money, default=0)
    # Modal per DUS — inilah yang diketik user (sumber kebenaran input).
    pack_purchase_price: Mapped[object] = mapped_column(Money, default=0)
    # Modal per BOTOL — turunan dari pack_purchase_price / pack_size. Dipakai
    # laporan margin (komisi/GPM) yang mengalikannya dengan kuantitas botol.
    purchase_price: Mapped[object] = mapped_column(Money, default=0)
    # Stok minimum, dalam satuan DASAR (botol).
    min_stock: Mapped[object] = mapped_column(Qty, default=0)
    # akun terkait (opsional override default perusahaan)
    income_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    inventory_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    cogs_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class StockLevel(Base, PKMixin):
    """Saldo stok per produk per gudang (real-time).

    `quantity` dan `avg_cost` SELALU dalam satuan dasar (botol) — dus hanya
    dipakai saat input & tampilan. Lihat services/units.py.
    """
    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    quantity: Mapped[object] = mapped_column(Qty, default=0)
    # nilai rata-rata berjalan untuk metode average — per BOTOL, 4 desimal
    # (lihat UnitCost di models/base.py: konversi dus->botol jarang bulat)
    avg_cost: Mapped[object] = mapped_column(UnitCost, default=0)


class StockMovement(Base, PKMixin, TimestampMixin):
    """Mutasi stok. `quantity` & `unit_cost` dalam satuan dasar (botol)."""
    __tablename__ = "stock_movements"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    # in | out | adjustment | transfer
    direction: Mapped[str] = mapped_column(String(12))
    quantity: Mapped[object] = mapped_column(Qty)
    unit_cost: Mapped[object] = mapped_column(UnitCost, default=0)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
