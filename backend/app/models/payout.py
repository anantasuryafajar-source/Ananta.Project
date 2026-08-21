"""Hak internal terakrual: insentif penjualan & bagi hasil omzet.

Beda dengan komisi pihak ketiga (yang hidup di `profit_sheets`), dua jenis
ini tidak melekat pada satu faktur:

    insentif  -> dasarnya UANG MASUK BERSIH, jadi diakui per cicilan
    omzet     -> dasarnya OMZET SEBULAN, jadi diakui saat tutup buku

Pembagian titik pengakuan ini disengaja dan penting: menaruh semuanya di satu
titik akan salah di salah satu sisi. Komisi pihak ketiga sudah diakui penuh
saat lembar hitung disetujui (`profit_sheet_service.approve_sheet`); kalau
insentif ikut diakui di situ, ia akan mendahului uangnya masuk. Sebaliknya
kalau komisi diakrual ulang per cicilan, ia terjurnal dua kali.
"""
from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money


class Payout(Base, PKMixin, TimestampMixin):
    __tablename__ = "payouts"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    # insentif | omzet
    jenis: Mapped[str] = mapped_column(String(12), index=True)
    payee_name: Mapped[str] = mapped_column(String(120), index=True)

    # Periode yang jadi dasar (untuk rekap & mencegah dobel akrual).
    periode_tahun: Mapped[int] = mapped_column(Integer, index=True)
    periode_bulan: Mapped[int] = mapped_column(Integer, index=True)
    # 1 | 2 | 0 (0 = bukan per-term, mis. bagi hasil omzet bulanan)
    term: Mapped[int] = mapped_column(Integer, default=0)

    # Dasar perhitungan yang dipakai (uang masuk bersih / omzet). Disimpan
    # supaya angkanya bisa ditelusuri tanpa menghitung ulang dari transaksi
    # yang mungkin sudah berubah.
    dasar: Mapped[object] = mapped_column(Money, default=0)
    persen: Mapped[object | None] = mapped_column(Money, nullable=True)
    amount: Mapped[object] = mapped_column(Money, default=0)

    # Faktur & pembayaran sumber, kalau hak ini lahir dari satu cicilan.
    invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True, index=True
    )

    # terutang | dibayar | batal
    status: Mapped[str] = mapped_column(String(12), default="terutang", index=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    expense_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    payable_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    paid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    settlement_journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
