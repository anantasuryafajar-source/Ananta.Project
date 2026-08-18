"""Skema penyesuaian stok (opname & stok awal).

Perhatikan bentuk input kuantitasnya: `qty_dus` DAN `qty_botol` terpisah, bukan
satu angka + satuan seperti di faktur/tagihan. Alasannya ada di
models/stock_adjustment.py - hitungan fisik client berbentuk "15 dus 11 botol",
dan memaksa mereka menjumlahkan sendiri memindahkan aritmetika ke manusia.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LineIn(BaseModel):
    product_id: str
    qty_dus: Decimal = Field(default=Decimal("0"), ge=0)
    qty_botol: Decimal = Field(default=Decimal("0"), ge=0)
    # Modal per DUS. Hanya dipakai bila stok BERTAMBAH dan produknya belum
    # punya modal rata-rata. Kosong = sistem memakai avg_cost yang ada, lalu
    # modal acuan dari master produk.
    modal_per_dus: Decimal | None = Field(default=None, ge=0)
    note: str | None = None


class PreviewIn(BaseModel):
    warehouse_id: str | None = None
    hitungan_lengkap: bool = False
    lines: list[LineIn] = []


class AdjustmentIn(PreviewIn):
    date: date
    # opening = stok awal (lawan jurnal ekuitas)
    # opname  = selisih hitung rutin (lawan jurnal beban)
    mode: str = "opname"
    notes: str | None = None


class PreviewLineOut(BaseModel):
    """Satu baris hasil hitung - dipakai layar pratinjau SEBELUM menyimpan."""
    product_id: str
    product_name: str
    pack_size: int
    qty_before: Decimal
    qty_counted: Decimal
    qty_diff: Decimal
    unit_cost: Decimal
    line_value: Decimal
    note: str | None = None
    # True bila produk ini diketik user; False bila ikut terbawa karena
    # `hitungan_lengkap` menganggapnya habis.
    tercantum: bool
    before_display: str
    counted_display: str
    diff_display: str


class PreviewOut(BaseModel):
    lines: list[PreviewLineOut]
    total_value: Decimal
    jumlah_berubah: int
    # Peringatan yang TIDAK menghalangi penyimpanan, mis. barang bertambah
    # tetapi modalnya nol.
    warnings: list[str] = []


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    description: str
    qty_dus: Decimal
    qty_botol: Decimal
    pack_size_snapshot: int
    qty_before: Decimal
    qty_counted: Decimal
    qty_diff: Decimal
    unit_cost: Decimal
    line_value: Decimal
    note: str | None = None


class AdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    number: str
    date: date
    warehouse_id: str
    mode: str
    hitungan_lengkap: bool
    status: str
    total_value: Decimal
    notes: str | None = None
    journal_id: str | None = None


class AdjustmentDetailOut(AdjustmentOut):
    lines: list[LineOut] = []
