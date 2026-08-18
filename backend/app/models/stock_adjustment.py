"""Penyesuaian stok (opname / stok awal).

Satu-satunya jalan mengubah stok TANPA membuat utang ke supplier. Dipakai
untuk memasukkan hasil hitung fisik gudang, yang di ASF dilakukan rutin.

Bentuk datanya sengaja menyimpan hitungan fisik APA ADANYA (`qty_counted`)
beserta saldo sistem saat itu (`qty_before`) dan selisihnya (`qty_diff`).
Menyimpan selisihnya saja membuat dokumen tidak bisa dibaca ulang: orang tidak
tahu "-20 botol" itu dari 96 jadi 76 atau dari 20 jadi 0. Ketiganya di-SNAPSHOT
supaya dokumen lama tetap berarti sama walau stok sesudahnya berubah lagi.

Lihat services/stock_adjustment_service.py untuk aturan jurnalnya.
"""
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Money, PKMixin, Qty, TimestampMixin, UnitCost


class StockAdjustment(Base, PKMixin, TimestampMixin):
    """Dokumen penyesuaian stok — satu gudang, satu tanggal, banyak baris."""
    __tablename__ = "stock_adjustments"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)

    # opening = stok awal (lawan jurnal EKUITAS, tidak menyentuh laba rugi)
    # opname  = selisih hitung rutin (lawan jurnal BEBAN Selisih Persediaan)
    # Perbedaan ini menentukan benar-tidaknya laba rugi periode berjalan:
    # mencatat stok awal sebagai selisih opname membuat laba bulan pertama
    # anjlok/melonjak sebesar seluruh nilai persediaan.
    mode: Mapped[str] = mapped_column(String(10), default="opname", index=True)

    # Bila True, produk yang TIDAK tercantum dianggap habis (dinolkan).
    # Bawaannya False: daftar hitung client sering hanya memuat barang yang ada,
    # dan menolkan sisanya diam-diam akan menghapus stok beserta jurnalnya.
    hitungan_lengkap: Mapped[bool] = mapped_column(Boolean, default=False)

    # posted | void
    status: Mapped[str] = mapped_column(String(12), default="posted", index=True)
    # Nilai bersih penyesuaian (positif = stok bertambah). Untuk ditampilkan;
    # angka resminya tetap dari jurnal.
    total_value: Mapped[object] = mapped_column(Money, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["StockAdjustmentLine"]] = relationship(
        back_populates="adjustment", cascade="all, delete-orphan", lazy="selectin"
    )


class StockAdjustmentLine(Base, PKMixin):
    """Satu PRODUK dalam satu penyesuaian — satu baris per produk.

    Kuantitas diketik dalam dua kolom terpisah, `qty_dus` dan `qty_botol`,
    karena begitulah client menghitung: "15 dus 11 botol", "1 dus", "4 botol".
    Memaksa mereka menjumlahkan sendiri jadi botol memindahkan aritmetika ke
    manusia — tempat salah hitung paling mungkin terjadi. `qty_counted` adalah
    hasilnya dalam BOTOL dan itulah yang dipakai sistem.

    `pack_size_snapshot` merekam isi/dus saat penyesuaian dibuat. Jangan dibaca
    ulang dari master saat menampilkan dokumen lama: kalau kemasan produk
    berubah, "1 dus" pada dokumen lama harus tetap berarti jumlah yang sama.
    """
    __tablename__ = "stock_adjustment_lines"
    adjustment_id: Mapped[str] = mapped_column(
        ForeignKey("stock_adjustments.id"), index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))

    # --- seperti diketik ---
    qty_dus: Mapped[object] = mapped_column(Qty, default=0)
    qty_botol: Mapped[object] = mapped_column(Qty, default=0)
    pack_size_snapshot: Mapped[int] = mapped_column(Integer, default=12)

    # --- dalam BOTOL ---
    qty_counted: Mapped[object] = mapped_column(Qty, default=0)   # hitung fisik
    qty_before: Mapped[object] = mapped_column(Qty, default=0)    # saldo sistem
    qty_diff: Mapped[object] = mapped_column(Qty, default=0)      # counted - before

    # Biaya per BOTOL yang dipakai menilai selisih baris ini.
    unit_cost: Mapped[object] = mapped_column(UnitCost, default=0)
    # qty_diff * unit_cost, dibulatkan ke rupiah (nilai yang masuk jurnal).
    line_value: Mapped[object] = mapped_column(Money, default=0)

    # Keterangan bebas: cukai biru/coklat, asal barang, kondisi. Client ASF
    # memakai ini untuk hal yang TIDAK memengaruhi angka (lihat CLAUDE.md).
    # Text, bukan String(255): satu produk bisa punya banyak rincian sekaligus
    # ("4 botol returan steven; 9 botol returan denatsu; 2 botol tanpa cukai").
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    adjustment: Mapped["StockAdjustment"] = relationship(back_populates="lines")
