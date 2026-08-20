"""Komisi penjualan: pencatatan per kasus + jurnal otomatis (basis akrual).

Alur & jurnal
-------------
    catat   -> status "terutang"   Dr 6-1100 Beban Komisi
                                       Cr 2-1600 Utang Komisi     <- masuk PNL
    bayar   -> status "dibayar"    Dr 2-1600 Utang Komisi
                                       Cr Kas/Bank                <- neraca saja
    void    -> status "void"       jurnal balik atas yang sudah terposting

Beban diakui SEKALI, di titik nilainya disepakati. Cara melunasinya setelah itu
tidak pernah menyentuh Laba Rugi lagi — jadi mode pelunasan baru (potong PO,
potong kasbon, dsb.) bisa ditambahkan tanpa risiko menggeser laba.

Kenapa titik pengakuannya "saat disepakati" dan bukan "saat faktur terbit":
nilainya sering belum diketahui waktu faktur keluar, dan angka yang belum ada
tidak bisa dijurnal.

Kenapa `amount` tidak pernah dihitung ulang dari master: nilainya beda-beda
per kasus (kesepakatan internal). `hitung_saran()` di bawah hanya MENYARANKAN
angka untuk diketik user, dan hasilnya tidak pernah disimpan sebagai formula.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    SalesCommission, CommissionScheme, Invoice, InvoiceLine, Product, Account,
)
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import ensure_account

CENT = Decimal("0.01")

COMMISSION_CODE = "6-1100"  # Beban Komisi (ada di seed_asf.py)
PAYABLE_KEY = "commission_payable"  # 2-1600, dibuat via accounts_map bila belum ada

# Faktur yang barangnya sudah keluar. Komisi tidak boleh dicatat atas draft
# (barang belum keluar) maupun void (transaksinya dibatalkan).
FAKTUR_SAH = ("posted", "paid", "overdue")


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


async def _acc_id(db: AsyncSession, company_id: str, code: str) -> str:
    aid = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if not aid:
        raise ValueError(f"Akun {code} tidak ada di CoA.")
    return aid


async def _faktur_sah(db: AsyncSession, company_id: str, invoice_id: str) -> Invoice:
    inv = (await db.execute(
        select(Invoice).where(Invoice.company_id == company_id,
                              Invoice.id == invoice_id)
    )).scalar_one_or_none()
    if inv is None:
        raise ValueError("Faktur tidak ditemukan.")
    if inv.status not in FAKTUR_SAH:
        raise ValueError(
            f"Faktur {inv.number} berstatus '{inv.status}' — komisi baru bisa "
            f"dicatat setelah faktur diposting (barang keluar)."
        )
    return inv


# ------------------------------------------------------------ SARAN NILAI
async def hitung_saran(db: AsyncSession, company_id: str, invoice_id: str) -> dict:
    """Omzet & margin faktur, untuk MEMBANTU user mengetik nilai komisi.

    Angka ini tidak pernah disimpan dan tidak mengikat: user tetap mengetik
    nominal akhirnya sendiri, karena kesepakatannya beda-beda per kasus.

    SATUAN (aturan dus/botol, lihat services/units.py): omzet dari
    `qty_input` x `unit_price`, modal dari `quantity` (BOTOL) x
    `purchase_price` (per botol). Mencampur keduanya salah 12-48x.

    Modal memakai `Product.purchase_price` (modal ACUAN dari master), sama
    seperti sheet KOMISI client dan laporan `reports_ext.commission` —
    BUKAN avg_cost yang dipakai HPP di Laba Rugi. Jadi "margin" di sini bisa
    berbeda dari laba kotor akuntansi untuk penjualan yang sama. Itu memang
    perilaku yang diminta; jangan diseragamkan sepihak.
    """
    inv = await _faktur_sah(db, company_id, invoice_id)

    rows = (await db.execute(
        select(InvoiceLine.quantity, InvoiceLine.qty_input,
               InvoiceLine.unit_price, InvoiceLine.discount,
               Product.purchase_price)
        .join(Product, Product.id == InvoiceLine.product_id, isouter=True)
        .where(InvoiceLine.invoice_id == invoice_id)
    )).all()

    omzet = Decimal("0")
    modal = Decimal("0")
    for qty_base, qty_input, price, disc, beli in rows:
        omzet += _q(qty_input) * _q(price) - _q(disc)
        modal += _q(qty_base) * _q(beli)
    margin = omzet - modal

    return {
        "invoice_id": inv.id,
        "invoice_number": inv.number,
        "invoice_date": inv.date.isoformat(),
        "omzet": str(_q(omzet)),
        "modal": str(_q(modal)),
        "margin": str(_q(margin)),
        # Sekadar contoh angka di UI; user bebas menimpanya.
        "saran_5_persen_margin": str(_q(margin * Decimal("0.05"))),
    }


# ------------------------------------------------------------ SKEMA
async def hitung_dari_skema(
    db: AsyncSession, company_id: str, scheme, invoice_id: str,
) -> Decimal:
    """Nilai komisi menurut sebuah skema. Lima tipe, daftar tertutup.

    `manual` sengaja mengembalikan 0: ia pintu darurat untuk kasus khusus dan
    tidak menghitung apa pun — orang mengetik angkanya sendiri. Jangan
    membuatnya menerima rumus yang dieksekusi; begitu rumus bisa diketik user,
    angkanya berhenti bisa dijelaskan dan tidak ada yang bisa dites.
    """
    tipe = scheme.type
    nilai = _q(scheme.value)

    if tipe == "manual":
        return Decimal("0")
    if tipe == "nominal":
        return nilai

    rows = (await db.execute(
        select(InvoiceLine.quantity, InvoiceLine.qty_input,
               InvoiceLine.unit_price, InvoiceLine.discount,
               Product.purchase_price)
        .join(Product, Product.id == InvoiceLine.product_id, isouter=True)
        .where(InvoiceLine.invoice_id == invoice_id)
    )).all()

    if tipe == "per_botol":
        # `quantity` SELALU botol (aturan dus/botol di services/units.py).
        # Memakai qty_input di sini salah 12-48x untuk baris bersatuan dus.
        botol = sum((_q(q_base) for q_base, _, _, _, _ in rows), Decimal("0"))
        return _q(botol * nilai)

    omzet = sum((_q(qi) * _q(pr) - _q(d) for _, qi, pr, d, _ in rows),
                Decimal("0"))
    if tipe == "persen_omzet":
        return _q(omzet * nilai / Decimal("100"))
    if tipe == "persen_margin":
        modal = sum((_q(qb) * _q(hb) for qb, _, _, _, hb in rows), Decimal("0"))
        return _q((omzet - modal) * nilai / Decimal("100"))

    raise ValueError(f"Tipe skema '{tipe}' tidak dikenal.")


# ------------------------------------------------------------ CATAT
async def create_commission(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    on_date: date, invoice_id: str, payee_name: str, amount: Decimal,
    basis: str = "nominal", rate: Decimal | None = None,
    scheme_id: str | None = None, note: str | None = None,
) -> SalesCommission:
    """Catat kesepakatan komisi. TIDAK membuat jurnal — lihat pay_commission."""
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nilai komisi harus lebih dari 0.")
    if basis not in ("nominal", "persen_margin", "persen_omzet"):
        raise ValueError("Basis komisi tidak dikenal.")
    if not payee_name.strip():
        raise ValueError("Penerima komisi harus diisi.")

    inv = await _faktur_sah(db, company_id, invoice_id)

    # Jaring pengaman terhadap salah ketik nol berlebih: komisi yang melebihi
    # nilai fakturnya sendiri hampir pasti keliru.
    if amount > _q(inv.total):
        raise ValueError(
            f"Komisi {amount} melebihi nilai faktur {inv.number} ({_q(inv.total)}). "
            f"Periksa lagi nominalnya."
        )

    # Snapshot skema — supaya perubahan tarif nanti tidak menggeser angka lama.
    scheme_type = scheme_value = None
    if scheme_id:
        sk = (await db.execute(
            select(CommissionScheme).where(
                CommissionScheme.company_id == company_id,
                CommissionScheme.id == scheme_id)
        )).scalar_one_or_none()
        if sk is None:
            raise ValueError("Skema komisi tidak ditemukan.")
        scheme_type, scheme_value = sk.type, sk.value

    expense_id = await _acc_id(db, company_id, COMMISSION_CODE)
    payable_id = await ensure_account(db, company_id, PAYABLE_KEY)
    number = await next_number(
        db, company_id=company_id, doc_type="commission", on_date=on_date,
        prefix="KOM", reset="monthly",
    )

    kom = SalesCommission(
        company_id=company_id, number=number, date=on_date,
        invoice_id=invoice_id, payee_name=payee_name.strip(),
        basis=basis, rate=rate, amount=amount,
        scheme_id=scheme_id, scheme_type=scheme_type, scheme_value=scheme_value,
        status="terutang", expense_account_id=expense_id,
        payable_account_id=payable_id,
        note=note, created_by=user_id,
    )
    db.add(kom)
    await db.flush()

    # --- Jurnal PENGAKUAN: di sinilah komisi masuk Laba Rugi ---
    journal = await post_journal(
        db, company_id=company_id, number=number.replace("KOM", "JV"),
        on_date=on_date,
        lines=[
            Line(expense_id, debit=amount,
                 description=f"Komisi {kom.payee_name}"),
            Line(payable_id, credit=amount,
                 description=f"Utang komisi {number}"),
        ],
        memo=f"Komisi {number} · {kom.payee_name} · {inv.number}",
        source_type="commission", source_id=kom.id, created_by=user_id,
    )
    kom.journal_id = journal.id
    await db.flush()
    return kom


# ------------------------------------------------------------ BAYAR
async def pay_commission(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    commission_id: str, on_date: date, paid_account_code: str = "1-1000",
) -> SalesCommission:
    """Bayar komisi -> jurnal Dr Utang Komisi / Cr Kas-Bank.

    Ini murni pelunasan: hanya menyentuh akun neraca. Bebannya sudah diakui
    waktu komisi dicatat, jadi membayar TIDAK menambah beban lagi — kalau
    fungsi ini sampai mendebit 6-1100, komisinya terhitung dua kali.
    """
    kom = (await db.execute(
        select(SalesCommission).where(SalesCommission.company_id == company_id,
                                      SalesCommission.id == commission_id)
    )).scalar_one_or_none()
    if kom is None:
        raise ValueError("Komisi tidak ditemukan.")
    if kom.status == "dibayar":
        raise ValueError(f"Komisi {kom.number} sudah dibayar.")
    if kom.status == "void":
        raise ValueError(f"Komisi {kom.number} sudah dibatalkan.")

    paid_id = await _acc_id(db, company_id, paid_account_code)
    payable_id = kom.payable_account_id or await ensure_account(
        db, company_id, PAYABLE_KEY)
    amount = _q(kom.amount)

    journal = await post_journal(
        db, company_id=company_id, number=kom.number.replace("KOM", "JVB"),
        on_date=on_date,
        lines=[
            Line(payable_id, debit=amount,
                 description=f"Lunasi utang komisi {kom.number}"),
            Line(paid_id, credit=amount,
                 description=f"Bayar {kom.payee_name}"),
        ],
        memo=f"Pembayaran komisi {kom.number} · {kom.payee_name}",
        source_type="commission_payment", source_id=kom.id, created_by=user_id,
    )

    kom.status = "dibayar"
    kom.paid_date = on_date
    kom.paid_account_id = paid_id
    kom.settlement_journal_id = journal.id
    await db.flush()
    return kom


# ------------------------------------------------------------ BATALKAN
async def void_commission(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    commission_id: str, on_date: date, reason: str | None = None,
) -> SalesCommission:
    """Batalkan komisi dengan jurnal balik.

    Mengikuti aturan repo: transaksi terposting tidak dihapus (lihat
    services/void_service.py) — jejak auditnya harus tetap utuh.

    Karena sekarang ada DUA jurnal (pengakuan + pelunasan), keduanya dibalik
    dalam satu jurnal gabungan: kas kembali, utang komisi kembali nol, dan
    bebannya batal. Membalik pengakuan saja akan meninggalkan utang komisi
    menggantung yang tidak akan pernah lunas.
    """
    kom = (await db.execute(
        select(SalesCommission).where(SalesCommission.company_id == company_id,
                                      SalesCommission.id == commission_id)
    )).scalar_one_or_none()
    if kom is None:
        raise ValueError("Komisi tidak ditemukan.")
    if kom.status == "void":
        raise ValueError(f"Komisi {kom.number} sudah dibatalkan.")

    amount = _q(kom.amount)
    payable_id = kom.payable_account_id or await ensure_account(
        db, company_id, PAYABLE_KEY)
    lines: list[Line] = []

    if kom.status == "dibayar":
        if not kom.paid_account_id:
            raise ValueError("Komisi terbayar tanpa akun kas — data tidak konsisten.")
        # Balik pelunasan: kas kembali, utang komisi hidup lagi.
        lines += [
            Line(kom.paid_account_id, debit=amount,
                 description=f"Balik pembayaran {kom.number}"),
            Line(payable_id, credit=amount,
                 description="Utang komisi dipulihkan"),
        ]

    # Balik pengakuan: utang komisi nol, beban batal.
    lines += [
        Line(payable_id, debit=amount,
             description=f"Batalkan utang komisi {kom.number}"),
        Line(kom.expense_account_id, credit=amount,
             description=f"Batalkan beban komisi {kom.payee_name}"),
    ]

    await post_journal(
        db, company_id=company_id,
        number=kom.number.replace("KOM", "JVR"), on_date=on_date,
        lines=lines,
        memo=f"Pembatalan komisi {kom.number}" + (f" · {reason}" if reason else ""),
        source_type="commission_void", source_id=kom.id, created_by=user_id,
    )

    kom.status = "void"
    if reason:
        kom.note = f"{kom.note}\n[VOID] {reason}" if kom.note else f"[VOID] {reason}"
    await db.flush()
    return kom
