"""Lembar Hitung: kalkulator kesepakatan yang menempel pada satu faktur.

Rancangan lengkapnya di RANCANGAN-LEMBAR-HITUNG.md; penjaganya
`tests/test_profit_sheet.py`.

Kenapa tabel sendiri dan bukan kolom di `invoices`
--------------------------------------------------
Faktur adalah dokumen yang DILIHAT CUSTOMER, dan harganya harus harga
sebenarnya. Semua kesepakatan internal — bagi hasil mitra, komisi pihak
ketiga, modal perjanjian — hidup di sini supaya tidak ada jalan bagi angka
kesepakatan untuk merembes ke `unit_price` atau `discount` faktur.

Yang DISIMPAN vs yang DITURUNKAN
--------------------------------
`hpp_riil` di-snapshot dari `journal_entries` saat lembar dibuat, BUKAN
dihitung ulang dari stok: `avg_cost` sudah bergerak sejak faktur diposting,
jadi menghitung ulang akan memberi angka yang berbeda tiap kali dibuka. Ia
juga sengaja tidak bisa ditimpa user — kalau bisa, lembar ini berhenti bisa
dipakai memeriksa pembukuan. Yang boleh ditimpa `hpp_dasar_komisi`, dan
selisih keduanya ditampilkan berdampingan.

`jumlah_dus` juga snapshot (aturan `unit_factor`): kalau isi dus produk
berubah nanti, lembar lama harus tetap berarti sama.

`hidden_margin` disimpan sebagai ANGKA TAMPILAN saja dan tidak pernah
dijurnal — ia turunan (`penjualan - hpp_riil - bagian mitra - bagian ASF`).
Menjurnalnya sebagai pendapatan terpisah membuat laba dobel.
"""
from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, PKMixin, TimestampMixin, Money, Qty


class ProfitSheet(Base, PKMixin, TimestampMixin):
    __tablename__ = "profit_sheets"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Satu faktur hanya boleh punya satu lembar aktif (ditegakkan di service,
    # bukan unique constraint, karena lembar berstatus "batal" boleh menumpuk).
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)

    # draft | disetujui | ditransfer | batal
    #   draft      -> belum ada jurnal apa pun, aman dihapus
    #   disetujui  -> beban & utang sudah diakui
    #   ditransfer -> semua barisnya sudah dibayar
    #   batal      -> jurnalnya sudah dibalik
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)

    # ---- dasar perhitungan (semua di-snapshot saat lembar dibuat) ----
    penjualan: Mapped[object] = mapped_column(Money, default=0)
    hpp_riil: Mapped[object] = mapped_column(Money, default=0)
    # Default = hpp_riil. Diisi berbeda hanya kalau kesepakatannya memakai
    # modal lain sebagai dasar komisi.
    hpp_dasar_komisi: Mapped[object] = mapped_column(Money, default=0)
    # Dipakai dasar "profit_bersama". NULL berarti tidak ada kesepakatan
    # bagi hasil di lembar ini.
    modal_perjanjian: Mapped[object | None] = mapped_column(Money, nullable=True)
    # Variabel pengurang komisi per dus. MURNI angka kesepakatan: tidak ada
    # hubungannya dengan `courier_expenses` dan tidak pernah masuk jurnal.
    # Sempat bernama `ongkir_per_dus` di 0008 dan itu keliru — lihat 0009.
    pengurang_per_dus: Mapped[object | None] = mapped_column(Money, nullable=True)
    # Dihitung PECAHAN (18 botol dari dus isi 12 = 1,5 dus), bukan dibulatkan.
    jumlah_dus: Mapped[object] = mapped_column(Qty, default=0)

    # ---- hasil antara (disimpan supaya angkanya bisa ditelusuri) ----
    profit_bersama: Mapped[object] = mapped_column(Money, default=0)
    bagian_asf: Mapped[object] = mapped_column(Money, default=0)
    hidden_margin: Mapped[object] = mapped_column(Money, default=0)

    journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    void_journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["ProfitSheetLine"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan", lazy="selectin",
        order_by="ProfitSheetLine.sequence",
    )


class ProfitSheetLine(Base, PKMixin):
    __tablename__ = "profit_sheet_lines"

    sheet_id: Mapped[str] = mapped_column(ForeignKey("profit_sheets.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    payee_name: Mapped[str] = mapped_column(String(120), index=True)
    # komisi | bagi_hasil -- menentukan pasangan akunnya:
    #   komisi     -> 6-1100 Beban Komisi     / 2-1600 Utang Komisi
    #   bagi_hasil -> 6-1300 Beban Bagi Hasil / 2-1700 Utang Bagi Hasil
    jenis: Mapped[str] = mapped_column(String(12), index=True)
    # Daftar TERTUTUP, lihat profit_sheet_service.DASAR. "nominal" adalah pintu
    # darurat yang menyimpan ANGKA, bukan rumus yang dieksekusi sistem.
    dasar: Mapped[str] = mapped_column(String(24))
    persen: Mapped[object | None] = mapped_column(Money, nullable=True)
    # Dipakai HANYA saat dasar == "nominal".
    nominal: Mapped[object | None] = mapped_column(Money, nullable=True)
    # Sumber kebenaran nilai hak ini. Sekali disetujui tidak dihitung ulang.
    amount: Mapped[object] = mapped_column(Money, default=0)

    expense_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    payable_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    # Terisi saat uangnya benar-benar ditransfer (Dr Utang / Cr Kas).
    paid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settlement_journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sheet: Mapped["ProfitSheet"] = relationship(back_populates="lines")
