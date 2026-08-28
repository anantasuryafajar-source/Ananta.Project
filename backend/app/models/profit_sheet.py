"""Lembar Hitung — kalkulator kesepakatan yang menempel di satu faktur.

DIREKONSTRUKSI. Berkas aslinya tidak pernah ikut ter-commit ke GitHub (lihat
commit 7724f6a "fix embedded repo nested folder"), padahal delapan berkas lain
sudah merujuknya sehingga backend gagal di-import sama sekali. Bentuk model ini
disusun ulang dari kontrak yang MEMANG terkirim: `tests/test_profit_sheet.py`,
pemakaian di `payout_service` & `void_service`, kode akun di `accounts_map`,
dan aturan 1-8 "Lembar Hitung" di CLAUDE.md. Kalau berkas asli suatu saat
muncul, bandingkan dulu — jangan langsung ditimpa.

Yang perlu dipahami sebelum mengubah apa pun di sini:

1. **Lembar tidak pernah menyentuh Pendapatan, HPP, atau Persediaan.** Ia hanya
   MENGHITUNG dari angka faktur yang sudah terposting, lalu menjurnal HASILNYA
   sebagai beban + utang. Hidden margin (selisih modal perjanjian vs HPP riil)
   tidak pernah dijurnal — ia turunan, dan menjurnalnya membuat laba dobel.

2. **`hpp_riil` di-SNAPSHOT dari jurnal, bukan dihitung ulang dari stok.**
   `avg_cost` sudah bergerak sejak faktur diposting, jadi menghitung ulang
   memberi angka yang berbeda tiap hari. Sengaja tidak bisa ditimpa user: kalau
   bisa, lembar berhenti bisa dipakai memeriksa pembukuan. Yang boleh ditimpa
   `hpp_dasar_komisi`, dan keduanya disimpan berdampingan supaya selisihnya
   terlihat.

3. **`jumlah_dus` PECAHAN, bukan dibulatkan.** 18 botol dari dus isi 12 = 1,5
   dus. Keputusan bisnis, bukan detail teknis — membulatkan ke atas membuat
   orang dibayar lebih.
"""
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Money, PKMixin, Qty, TimestampMixin

# Dasar hitung yang boleh dipakai satu baris. Daftar TERTUTUP dan disengaja:
# custom berarti user mengetik ANGKA (modal perjanjian, persen, pengurang),
# BUKAN user mendefinisikan rumus. Begitu rumus bisa diketik, angkanya berhenti
# bisa dijelaskan dan tidak ada yang bisa dites. Tambah dasar baru bernama
# jelas saja; masing-masing cuma beberapa baris di service.
DASAR = (
    "omzet",                 # nilai faktur (sebelum PPN)
    "margin_riil",           # omzet - hpp_riil
    "margin_komisi",         # omzet - hpp_dasar_komisi (HPP versi kesepakatan)
    "margin_min_pengurang",  # omzet - hpp_riil - (pengurang_per_dus x jumlah_dus)
    "profit_bersama",        # omzet - modal_perjanjian
    "bagian_asf",            # profit_bersama - seluruh hak mitra bagi hasil
    "nominal",               # pintu darurat: angka diketik, tidak dihitung
)

# Sifat baris. Menentukan pasangan akunnya, bukan cara menghitungnya.
JENIS = (
    "komisi",      # pihak ketiga/perantara -> 6-1100 / 2-1600
    "bagi_hasil",  # hak mitra (mis. Andre)  -> 6-1300 / 2-1700
)

STATUS = ("draft", "disetujui", "ditransfer", "batal")


class ProfitSheet(Base, PKMixin, TimestampMixin):
    """Satu lembar per faktur. Lihat catatan modul di atas."""
    __tablename__ = "profit_sheets"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)

    # draft | disetujui | ditransfer | batal
    # Beban baru diakui saat 'disetujui'; 'batal' membalik jurnalnya.
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)

    # --- SNAPSHOT angka faktur saat lembar dibuat ---
    # Disimpan, bukan dibaca ulang: faktur bisa berubah statusnya dan avg_cost
    # bergerak terus, sedangkan lembar harus tetap bisa dibaca ulang apa adanya.
    penjualan: Mapped[object] = mapped_column(Money, default=0)
    hpp_riil: Mapped[object] = mapped_column(Money, default=0)
    jumlah_dus: Mapped[object] = mapped_column(Qty, default=0)

    # --- variabel kesepakatan yang diketik user ---
    # Modal "seolah-olah" yang disepakati dengan mitra. Selisihnya terhadap
    # hpp_riil adalah hidden margin — hak internal penuh, TIDAK dijurnal.
    modal_perjanjian: Mapped[object | None] = mapped_column(Money, nullable=True)
    # HPP versi kesepakatan untuk dasar komisi. Tidak pernah menggeser HPP jurnal.
    hpp_dasar_komisi: Mapped[object | None] = mapped_column(Money, nullable=True)
    # Pengurang tetap per dus (mis. Rp50.000/dus pada skema Rusdi). Murni
    # variabel hitung — TIDAK ada hubungannya dengan `courier_expenses` dan
    # tidak pernah masuk jurnal. Sempat bernama `ongkir_per_dus` dan itu keliru.
    pengurang_per_dus: Mapped[object] = mapped_column(Money, default=0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Jurnal pengakuan beban (saat disetujui) & jurnal baliknya (saat dibatalkan).
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    void_journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["ProfitSheetLine"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan", lazy="selectin",
        order_by="ProfitSheetLine.urutan",
    )


class ProfitSheetLine(Base, PKMixin):
    """Satu penerima hak dalam satu lembar.

    `urutan` menjaga baris tampil sesuai yang diketik. Ia BUKAN urutan
    evaluasi: baris `bagian_asf` selalu dihitung setelah seluruh baris
    `profit_bersama`, berapa pun urutan ketiknya (lihat CLAUDE.md aturan 4).
    """
    __tablename__ = "profit_sheet_lines"

    sheet_id: Mapped[str] = mapped_column(ForeignKey("profit_sheets.id"), index=True)
    urutan: Mapped[int] = mapped_column(Integer, default=0)
    payee_name: Mapped[str] = mapped_column(String(120))
    # komisi | bagi_hasil — menentukan pasangan akun, bukan cara menghitung.
    jenis: Mapped[str] = mapped_column(String(16), index=True)
    # Salah satu dari DASAR di atas.
    dasar: Mapped[str] = mapped_column(String(24))
    persen: Mapped[object] = mapped_column(Money, default=0)
    # Dipakai hanya bila dasar == "nominal".
    nominal: Mapped[object] = mapped_column(Money, default=0)

    # Hasil hitung, dibekukan saat lembar dibuat. Inilah angka yang dijurnal
    # dan yang dibayarkan — jangan pernah dihitung ulang saat melapor.
    amount: Mapped[object] = mapped_column(Money, default=0)
    # Dasar hitung yang dipakai baris ini, disimpan untuk bisa ditelusuri
    # ("6 itu dari 4% x berapa?").
    basis_amount: Mapped[object] = mapped_column(Money, default=0)

    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Terisi saat haknya benar-benar ditransfer. NULL = masih utang.
    # Dipakai payout_service untuk memisahkan "siap transfer" vs "sudah cair".
    settlement_journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )

    sheet: Mapped["ProfitSheet"] = relationship(back_populates="lines")
