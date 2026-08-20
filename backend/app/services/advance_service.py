"""Uang muka pelanggan (DP): penerimaan & alokasi ke faktur.

    1. Terima DP (barang belum keluar)
        Dr  Kas/Bank
            Cr  Uang Muka Pelanggan (2-1500)

    2. Faktur terbit — jurnal normal, tidak tahu-menahu soal DP.

    3. Alokasi DP ke faktur
        Dr  Uang Muka Pelanggan
            Cr  Piutang Usaha

Pendapatan tetap diakui SEKALI, di tanggal barang keluar. Tidak ada PPN di
langkah 1 (keputusan client 2026-08-20).

Sisa DP yang belum terpakai tinggal di 2-1500 sebagai saldo customer dan siap
dipakai faktur berikutnya. Ia TIDAK BOLEH menjadi piutang negatif — itu yang
membuat neraca terlihat aneh dan AR Aging kacau.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    CustomerAdvance, AdvanceAllocation, Invoice, Contact, Account,
)
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import code_to_id, ensure_account

CENT = Decimal("0.01")

# Faktur yang piutangnya benar-benar ada (barang sudah keluar).
FAKTUR_BERPIUTANG = ("posted", "overdue")


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


async def _cash_id(db: AsyncSession, company_id: str, code: str) -> str:
    aid = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if not aid:
        raise ValueError(f"Akun {code} tidak ada di CoA.")
    return aid


# ------------------------------------------------------------ TERIMA DP
async def receive_advance(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    contact_id: str, on_date: date, amount: Decimal,
    cash_account_code: str = "1-1000", note: str | None = None,
) -> CustomerAdvance:
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nilai uang muka harus lebih dari 0.")

    contact = (await db.execute(
        select(Contact).where(Contact.company_id == company_id,
                              Contact.id == contact_id)
    )).scalar_one_or_none()
    if contact is None:
        raise ValueError("Customer tidak ditemukan.")

    cash_id = await _cash_id(db, company_id, cash_account_code)
    adv_acc_id = await ensure_account(db, company_id, "customer_advance")

    number = await next_number(
        db, company_id=company_id, doc_type="advance_in", on_date=on_date,
        prefix="DP", reset="monthly",
    )

    adv = CustomerAdvance(
        company_id=company_id, number=number, contact_id=contact_id,
        date=on_date, amount=amount, allocated_total=Decimal("0"),
        status="open", cash_account_id=cash_id,
        advance_account_id=adv_acc_id, note=note, created_by=user_id,
    )
    db.add(adv)
    await db.flush()

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("DP", "JV"),
        on_date=on_date,
        lines=[
            Line(cash_id, debit=amount, description="Terima uang muka"),
            Line(adv_acc_id, credit=amount,
                 description=f"Uang muka {contact.name}"),
        ],
        memo=f"Uang muka {number} · {contact.name}",
        source_type="advance", source_id=adv.id, created_by=user_id,
    )
    adv.journal_id = journal.id
    await db.flush()
    return adv


# ------------------------------------------------------------ SALDO
async def advance_balance(db: AsyncSession, company_id: str,
                          contact_id: str) -> Decimal:
    """Sisa uang muka customer yang belum terpakai."""
    rows = (await db.execute(
        select(CustomerAdvance.amount, CustomerAdvance.allocated_total)
        .where(CustomerAdvance.company_id == company_id,
               CustomerAdvance.contact_id == contact_id,
               CustomerAdvance.status != "void")
    )).all()
    return sum((_q(a) - _q(b) for a, b in rows), Decimal("0"))


# ------------------------------------------------------------ ALOKASI
async def allocate_to_invoice(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    advance_id: str, invoice_id: str, on_date: date, amount: Decimal,
) -> AdvanceAllocation:
    """Pakai uang muka untuk menutup sebagian/seluruh faktur."""
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nilai alokasi harus lebih dari 0.")

    adv = (await db.execute(
        select(CustomerAdvance).where(CustomerAdvance.company_id == company_id,
                                      CustomerAdvance.id == advance_id)
    )).scalar_one_or_none()
    if adv is None:
        raise ValueError("Uang muka tidak ditemukan.")
    if adv.status == "void":
        raise ValueError(f"Uang muka {adv.number} sudah dibatalkan.")

    sisa_dp = _q(adv.amount) - _q(adv.allocated_total)
    if amount > sisa_dp:
        raise ValueError(
            f"Alokasi {amount} melebihi sisa uang muka {adv.number} ({sisa_dp})."
        )

    inv = (await db.execute(
        select(Invoice).where(Invoice.company_id == company_id,
                              Invoice.id == invoice_id)
    )).scalar_one_or_none()
    if inv is None:
        raise ValueError("Faktur tidak ditemukan.")
    if inv.status not in FAKTUR_BERPIUTANG:
        raise ValueError(
            f"Faktur {inv.number} berstatus '{inv.status}' — uang muka baru "
            f"bisa dialokasikan setelah faktur diposting (barang keluar)."
        )
    if inv.contact_id != adv.contact_id:
        raise ValueError("Uang muka milik customer lain.")

    # Jaring pengaman: piutang tidak boleh jadi negatif. Kelebihan DP harus
    # tetap tinggal sebagai kewajiban di 2-1500, bukan mengurangi 1-1200
    # sampai minus.
    sisa_piutang = _q(inv.total) - _q(inv.paid_total)
    if amount > sisa_piutang:
        raise ValueError(
            f"Alokasi {amount} melebihi sisa piutang faktur {inv.number} "
            f"({sisa_piutang}). Kelebihan uang muka tetap jadi saldo customer."
        )

    acc = await code_to_id(db, company_id)
    number = await next_number(
        db, company_id=company_id, doc_type="advance_alloc", on_date=on_date,
        prefix="ALO", reset="monthly",
    )

    alloc = AdvanceAllocation(
        company_id=company_id, advance_id=adv.id, invoice_id=inv.id,
        date=on_date, amount=amount, created_by=user_id,
    )
    db.add(alloc)
    await db.flush()

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("ALO", "JV"),
        on_date=on_date,
        lines=[
            Line(adv.advance_account_id, debit=amount,
                 description="Pakai uang muka"),
            Line(acc["ar"], credit=amount,
                 description=f"Pelunasan piutang {inv.number}"),
        ],
        memo=f"Alokasi uang muka {adv.number} ke {inv.number}",
        source_type="advance_alloc", source_id=alloc.id, created_by=user_id,
    )
    alloc.journal_id = journal.id

    adv.allocated_total = _q(_q(adv.allocated_total) + amount)
    if _q(adv.allocated_total) >= _q(adv.amount):
        adv.status = "used"

    inv.paid_total = _q(_q(inv.paid_total) + amount)
    if _q(inv.paid_total) >= _q(inv.total):
        inv.status = "paid"

    await db.flush()

    # Tutup termin DP kalau jadwalnya ada.
    from .terms_service import settle_terms
    await settle_terms(db, invoice_id=inv.id, amount=amount, prefer_kind="dp")
    return alloc
