"""Sisi PENYELESAIAN piutang: uang muka (DP) dan jadwal termin.

Aturan payung (lihat RANCANGAN-KUSTOMISASI.md §1): cara membayar tidak boleh
menyentuh cara mengakui. Jurnal penjualan tetap seragam untuk semua kesepakatan
— tunai, tempo, DP, atau tagih di PO berikutnya. Yang berbeda hanya bagaimana
piutang ditutup, dan itu semua hanya menyentuh akun NERACA. Karena itu Laba
Rugi tidak perlu tahu file ini ada.
"""
from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, PKMixin, TimestampMixin, Money


class CustomerAdvance(Base, PKMixin, TimestampMixin):
    """Uang muka (DP) diterima SEBELUM barang keluar.

    Ini kewajiban, bukan pendapatan. Saat customer transfer sebelum barang
    dikirim, ASF berhutang BARANG — belum menerima penghasilan apa pun.

        Dr  Kas/Bank
            Cr  Uang Muka Pelanggan (2-1500)

    PPN sengaja TIDAK dipungut di titik ini (keputusan client 2026-08-20).
    Kalau suatu saat berubah, tambahkan flag per perusahaan — jangan hardcode,
    dan perubahannya hanya menyentuh jurnal penerimaan di atas.

    Kenapa tidak lewat `payment_service.receive_payment`: fungsi itu SELALU
    mengkredit Piutang Usaha. Dipakai untuk DP atas faktur yang belum ada
    (atau masih draft), piutang jadi MINUS dan pendapatannya belum punya
    lawan — neraca langsung salah. DP wajib jalur sendiri.
    """
    __tablename__ = "customer_advances"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    amount: Mapped[object] = mapped_column(Money, default=0)
    # Sudah dialokasikan ke faktur berapa. Sisanya tetap jadi saldo uang muka
    # customer dan TIDAK BOLEH menjadi piutang negatif.
    allocated_total: Mapped[object] = mapped_column(Money, default=0)

    # open | used | void
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)

    cash_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    advance_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AdvanceAllocation(Base, PKMixin, TimestampMixin):
    """Pemakaian uang muka untuk menutup sebagian/seluruh faktur.

        Dr  Uang Muka Pelanggan
            Cr  Piutang Usaha

    Tidak ada kas yang bergerak di sini — uangnya sudah masuk waktu DP
    diterima. Ini murni memindahkan kewajiban jadi pelunasan piutang.
    """
    __tablename__ = "advance_allocations"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    advance_id: Mapped[str] = mapped_column(ForeignKey("customer_advances.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[object] = mapped_column(Money, default=0)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class InvoiceTerm(Base, PKMixin):
    """Satu baris jadwal pembayaran faktur: "kapan, berapa".

    Menggantikan `Invoice.due_date` tunggal yang tidak bisa menampung
    "DP 30% lalu sisanya tempo 30 hari". Satu faktur punya satu baris atau
    lebih:

        tunai          1 baris, jatuh tempo hari faktur
        tempo          1 baris, hari faktur + n
        dp + tempo     2 baris
        po_berikutnya  1 baris TANPA due_date
        custom         n baris bebas — tanggal & nominal diketik sendiri

    `custom` adalah pintu darurat yang sama dengan `manual` di skema komisi:
    ia menyimpan ANGKA, bukan aturan. Tidak ada yang dieksekusi sistem.

    INVARIAN: SUM(amount) semua termin == Invoice.total. Ditegakkan di
    `terms_service`, sekeras debit==kredit di post_journal. Tanpa itu jadwal
    dan faktur bisa berbeda diam-diam dan AR Aging jadi bohong tanpa error.

    `due_date` NULL berarti "belum ada tanggal", bukan "jatuh tempo hari
    faktur". AR Aging wajib membedakannya — kalau tidak, kesepakatan "tagih
    saat order berikutnya" akan terbaca menunggak 90+ hari dan orang menagih
    customer yang sebenarnya tidak terlambat.
    """
    __tablename__ = "invoice_terms"

    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    # tunai | dp | tempo | po_berikutnya | custom
    kind: Mapped[str] = mapped_column(String(16), default="tempo", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    amount: Mapped[object] = mapped_column(Money, default=0)
    settled_amount: Mapped[object] = mapped_column(Money, default=0)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
