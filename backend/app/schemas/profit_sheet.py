"""Skema Lembar Hitung.

DIREKONSTRUKSI bersama model & service-nya — berkas asli tidak pernah ikut
ter-commit. Bentuknya mengikuti apa yang dituntut `tests/test_profit_sheet.py`
dan halaman Disbursement di frontend.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LineIn(BaseModel):
    payee_name: str
    # komisi | bagi_hasil
    jenis: str
    # Salah satu dari models/profit_sheet.py::DASAR — daftar TERTUTUP.
    dasar: str
    persen: Decimal = Field(default=Decimal("0"), ge=0)
    # Dipakai hanya bila dasar == "nominal".
    nominal: Decimal = Field(default=Decimal("0"), ge=0)
    note: str | None = None


class SheetIn(BaseModel):
    invoice_id: str
    date: date
    # Modal "seolah-olah" yang disepakati. Wajib untuk baris bagi hasil.
    modal_perjanjian: Decimal | None = Field(default=None, ge=0)
    # HPP versi kesepakatan. Tidak pernah menggeser HPP di jurnal.
    hpp_dasar_komisi: Decimal | None = Field(default=None, ge=0)
    # Pengurang tetap per dus (mis. Rp50.000/dus). Bukan ongkir riil.
    pengurang_per_dus: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    lines: list[LineIn]


class PratinjauIn(BaseModel):
    """Hitung tanpa menyimpan. Tanpa `date` — tidak ada dokumen yang dibuat."""
    invoice_id: str
    modal_perjanjian: Decimal | None = Field(default=None, ge=0)
    hpp_dasar_komisi: Decimal | None = Field(default=None, ge=0)
    pengurang_per_dus: Decimal = Field(default=Decimal("0"), ge=0)
    lines: list[LineIn]


class PratinjauLineOut(BaseModel):
    payee_name: str
    jenis: str
    dasar: str
    # Arti kode dasarnya, dikirim dari server supaya tidak ditulis ulang di UI.
    keterangan_dasar: str
    persen: Decimal
    nominal: Decimal
    basis_amount: Decimal
    amount: Decimal


class PratinjauOut(BaseModel):
    invoice_number: str
    penjualan: Decimal
    hpp_riil: Decimal
    hpp_dasar_komisi: Decimal
    jumlah_dus: Decimal
    margin_riil: Decimal
    profit_bersama: Decimal
    bagian_asf: Decimal
    # modal perjanjian - HPP riil. Angka TAMPILAN; tidak pernah dijurnal.
    hidden_margin: Decimal
    total_hak: Decimal
    # Dilaporkan, bukan ditolak di sini — pratinjau harus tetap menampilkan
    # angkanya supaya user melihat seberapa jauh melesetnya.
    melebihi_margin: bool
    baris: list[PratinjauLineOut]


class OpsiOut(BaseModel):
    kode: str
    keterangan: str


class DaftarDasarOut(BaseModel):
    dasar: list[OpsiOut]
    jenis: list[OpsiOut]


class TanggalIn(BaseModel):
    """Badan permintaan untuk menyetujui lembar."""
    date: date


class TransferIn(BaseModel):
    """Badan permintaan transfer satu hak.

    `paid_account_code` mengikuti pola router komisi & payout: yang dikirim
    adalah KODE akun (1-1000 Kas, 1-1100 Bank), bukan id — supaya frontend
    tidak perlu tahu id internal.
    """
    date: date
    paid_account_code: str = "1-1000"


class VoidIn(TanggalIn):
    reason: str | None = None


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    urutan: int
    payee_name: str
    jenis: str
    dasar: str
    persen: Decimal
    nominal: Decimal
    # Dasar hitung yang dipakai baris ini, supaya angkanya bisa ditelusuri
    # ("6 itu dari 4% x berapa?").
    basis_amount: Decimal
    amount: Decimal
    note: str | None = None
    settlement_journal_id: str | None = None


class SheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    number: str
    date: date
    invoice_id: str
    status: str
    penjualan: Decimal
    hpp_riil: Decimal
    jumlah_dus: Decimal
    modal_perjanjian: Decimal | None = None
    hpp_dasar_komisi: Decimal | None = None
    pengurang_per_dus: Decimal
    # Hasil antara, disimpan supaya dokumen bisa dibaca ulang tanpa
    # menjalankan kembali rumusnya.
    profit_bersama: Decimal
    bagian_asf: Decimal
    hidden_margin: Decimal
    notes: str | None = None
    journal_id: str | None = None
    void_reason: str | None = None


class SheetDetailOut(SheetOut):
    lines: list[LineOut] = []
