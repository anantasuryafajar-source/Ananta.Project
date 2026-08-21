from datetime import date
from sqlalchemy import String, ForeignKey, Date, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, PKMixin, TimestampMixin, Money, Qty


class CommissionScheme(Base, PKMixin, TimestampMixin):
    """Cara menghitung komisi — daftar TERTUTUP, bukan mesin rumus.

    Lima tipe menutup semua kesepakatan yang dipakai ASF:

        nominal        value = rupiah flat per faktur      ("dikasih 50 ribu")
        per_botol      value = tarif per BOTOL terjual
        persen_margin  value = persen dari margin faktur
        persen_omzet   value = persen dari nilai faktur
        persen_margin_min_ongkir
                       value = persen, DIKURANGI dulu tarif ongkir per dus
                       (`ongkir_per_dus`) dikali jumlah dus di faktur
        manual         value diabaikan — orang mengetik angkanya sendiri

    `manual` adalah pintu darurat untuk kasus khusus yang belum terpikirkan.
    Ia sengaja TIDAK bisa menghitung apa pun: ia hanya menandai "angka ini
    diketik manusia, alasannya di catatan". Kalau suatu saat tergoda membuat
    `manual` menerima rumus yang dieksekusi sistem, jangan — begitu rumus bisa
    diketik user, angkanya berhenti bisa dijelaskan dan tidak ada yang bisa
    dites. Tambah tipe baru yang bernama jelas saja; masing-masing cuma
    belasan baris.

    `per_botol` aman karena `InvoiceLine.quantity` SELALU dalam botol (lihat
    services/units.py). Jangan pernah mengalikannya dengan `qty_input`, yang
    bisa berarti dus.
    """
    __tablename__ = "commission_schemes"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # nominal | per_botol | persen_margin | persen_omzet | manual
    type: Mapped[str] = mapped_column(String(20), index=True)
    # Rupiah untuk nominal/per_botol, persen untuk persen_*, diabaikan untuk manual.
    value: Mapped[object] = mapped_column(Money, default=0)

    # Tarif ongkir KESEPAKATAN per dus, hanya untuk persen_margin_min_ongkir.
    # SENGAJA bukan diambil dari `courier_expenses`: itu ongkir AKTUAL yang
    # dibayar ke ekspedisi, sedangkan ini angka yang disepakati dengan sales.
    # Dua-duanya sering beda, dan memakai yang salah berarti orang dibayar
    # keliru. Kalau tarifnya beda per tujuan, timpa saja nilainya saat
    # mencatat komisi — `amount` tetap sumber kebenarannya.
    ongkir_per_dus: Mapped[object | None] = mapped_column(Money, nullable=True)

    # Default otomatis. Keduanya opsional; kalau dua-duanya kosong skema ini
    # hanya bisa dipilih manual saat mencatat komisi.
    default_for_contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("contacts.id"), nullable=True, index=True
    )
    default_for_product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id"), nullable=True, index=True
    )

    # Skema lama dinonaktifkan, TIDAK dihapus — komisi lama masih menunjuk ke sini.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesCommission(Base, PKMixin, TimestampMixin):
    """Komisi penjualan — kesepakatan INTERNAL, bukan bagian dari faktur.

    Tiga aturan bisnis yang membentuk tabel ini (dari client, 2026-08-20):

    1. **Komisi hanya untuk kasus tertentu, nilainya beda-beda.** Karena itu
       tidak ada rate global dan tidak ada perhitungan otomatis: `amount`
       DIKETIK per kasus dan itulah sumber kebenarannya. `basis` & `rate` hanya
       catatan cara menghitungnya waktu itu — tidak pernah dipakai ulang untuk
       menghitung ulang `amount`. Kalau dihitung ulang dari master, angka lama
       akan berubah sendiri saat modal/harga master diperbarui.

    2. **Komisi TIDAK BOLEH muncul di faktur.** Itu sebabnya ini tabel sendiri
       dan bukan kolom di `invoices`/`invoice_lines`: komisi adalah perjanjian
       internal dengan sales, sementara faktur adalah dokumen yang dilihat
       customer dan harganya harus harga sebenarnya. Jangan pernah menitipkan
       komisi ke `unit_price` (markup) atau `discount` — dua jalur itu satu-
       satunya cara aturan ini bisa bocor ke mata customer.

    3. **Komisi diakui saat NILAINYA DISEPAKATI** (basis akrual, keputusan
       client 2026-08-20 sore, menggantikan basis kas yang diputuskan pagi
       harinya). Dua kejadian, dua jurnal:

           dicatat  -> Dr 6-1100 Beban Komisi / Cr 2-1600 Utang Komisi
                       ^ ini yang masuk Laba Rugi, sekali saja
           dibayar  -> Dr 2-1600 Utang Komisi / Cr Kas-Bank
                       ^ hanya menyentuh neraca

       Kenapa titik pengakuannya "saat disepakati" dan bukan "saat faktur
       terbit": nilainya sering belum diketahui waktu faktur keluar, dan angka
       yang belum ada tidak bisa dijurnal.

       Kenapa bukan lagi "saat dibayar": komisi yang sudah disepakati tapi
       belum dibayar tidak muncul di mana pun, padahal uangnya pasti keluar.
       Dengan mode pelunasan yang bisa berjarak berbulan-bulan (mis. dipotong
       di PO berikutnya), selisihnya jadi material dan laba terlihat lebih
       besar dari kenyataan.
    """
    __tablename__ = "sales_commissions"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(40), index=True)
    # Tanggal kesepakatan/pencatatan komisi (bukan tanggal bayar).
    date: Mapped[date] = mapped_column(Date, index=True)

    # Faktur yang jadi dasar komisi. WAJIB: komisi baru sah setelah barang
    # keluar, dan faktur adalah bukti barang keluar.
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)

    # Penerima komisi. Sengaja teks bebas, bukan FK ke users/contacts: penerima
    # sering orang lapangan yang tidak punya akun sistem dan bukan customer.
    payee_name: Mapped[str] = mapped_column(String(120), index=True)

    # Cara angkanya dihitung waktu disepakati — CATATAN saja, tidak dieksekusi.
    # nominal | persen_margin | persen_omzet
    basis: Mapped[str] = mapped_column(String(16), default="nominal")
    # Persen (mis. 5 = 5%), diisi hanya kalau basis persen. Untuk jejak audit.
    rate: Mapped[object | None] = mapped_column(Qty, nullable=True)

    # --- Skema yang dipakai, DI-SNAPSHOT ---
    # `scheme_id` untuk menelusuri asalnya; `scheme_type` & `scheme_value`
    # adalah salinan isi skema SAAT komisi dibuat. Alasannya sama dengan
    # `unit_factor` di baris transaksi: kalau tarif per botol naik tahun depan,
    # komisi yang sudah disepakati tahun ini tidak boleh ikut bergerak. Jangan
    # pernah membaca ulang tarif dari `commission_schemes` saat melapor.
    scheme_id: Mapped[str | None] = mapped_column(
        ForeignKey("commission_schemes.id"), nullable=True
    )
    scheme_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scheme_value: Mapped[object | None] = mapped_column(Money, nullable=True)

    # Nilai komisi yang disepakati. INI sumber kebenarannya.
    amount: Mapped[object] = mapped_column(Money, default=0)

    # terutang | dibayar | void
    status: Mapped[str] = mapped_column(String(12), default="terutang", index=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    expense_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    # Utang Komisi (2-1600) — lawan beban saat komisi diakui.
    payable_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    # Kas/bank sumber pembayaran — baru terisi saat komisi dibayar.
    paid_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    # Jurnal PENGAKUAN (beban). Dibuat saat komisi dicatat.
    journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    # Jurnal PELUNASAN (kas keluar). Dibuat saat komisi dibayar. Sengaja
    # terpisah dari `journal_id` supaya dua kejadian itu bisa ditelusuri
    # sendiri-sendiri — beban dan kas keluar bukan hal yang sama.
    settlement_journal_id: Mapped[str | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
