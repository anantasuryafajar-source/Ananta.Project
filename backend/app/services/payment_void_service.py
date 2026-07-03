"""Void pembayaran (pelunasan) — hak absolut owner.

Membalik jurnal pembayaran, mengurangi paid_total dokumen, dan mengembalikan
status dokumen (paid -> posted) bila perlu. Pembayaran dihapus fisik karena
ia hanyalah catatan pelunasan (bukan dokumen sumber); jurnal pembaliknya
tetap tercatat sebagai jejak.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Invoice, Bill, PaymentReceived, PaymentMade, Journal, JournalEntry,
)
from .journal import Line, post_journal
from .numbering import next_number

CENT = Decimal("0.01")


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


class PaymentVoidError(ValueError):
    pass


async def _reverse_journal(db, *, company_id, user_id, journal_id, on_date,
                           memo, source_type, source_id):
    entries = (await db.execute(
        select(JournalEntry).where(JournalEntry.journal_id == journal_id)
    )).scalars().all()
    if not entries:
        raise PaymentVoidError("Jurnal pembayaran tidak ditemukan.")
    number = await next_number(db, company_id=company_id, doc_type="void",
                               on_date=on_date, prefix="VD", reset="monthly")
    lines = [Line(e.account_id, debit=_q(e.credit), credit=_q(e.debit),
                  description=f"Balik: {e.description or ''}".strip())
             for e in entries]
    return await post_journal(
        db, company_id=company_id, number=number, on_date=on_date, lines=lines,
        memo=memo, source_type=source_type, source_id=source_id,
        created_by=user_id)


async def void_payment_received(db: AsyncSession, *, company_id, user_id,
                                payment_id) -> str:
    pay = (await db.execute(
        select(PaymentReceived).where(PaymentReceived.id == payment_id,
                                      PaymentReceived.company_id == company_id)
    )).scalar_one_or_none()
    if pay is None:
        raise PaymentVoidError("Pembayaran tidak ditemukan.")
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == pay.invoice_id)
    )).scalar_one()
    number = pay.number

    if pay.journal_id:
        await _reverse_journal(
            db, company_id=company_id, user_id=user_id,
            journal_id=pay.journal_id, on_date=date.today(),
            memo=f"Pembatalan pembayaran {pay.number} ({inv.number})",
            source_type="void_payment", source_id=inv.id)

    inv.paid_total = _q(Decimal(str(inv.paid_total)) - Decimal(str(pay.amount)))
    if Decimal(str(inv.paid_total)) < Decimal(str(inv.total)) and inv.status == "paid":
        inv.status = "posted"
    await db.delete(pay)
    await db.flush()
    return number


async def void_payment_made(db: AsyncSession, *, company_id, user_id,
                            payment_id) -> str:
    pay = (await db.execute(
        select(PaymentMade).where(PaymentMade.id == payment_id,
                                  PaymentMade.company_id == company_id)
    )).scalar_one_or_none()
    if pay is None:
        raise PaymentVoidError("Pembayaran tidak ditemukan.")
    bill = (await db.execute(
        select(Bill).where(Bill.id == pay.bill_id)
    )).scalar_one()
    number = pay.number

    if pay.journal_id:
        await _reverse_journal(
            db, company_id=company_id, user_id=user_id,
            journal_id=pay.journal_id, on_date=date.today(),
            memo=f"Pembatalan pembayaran {pay.number} ({bill.number})",
            source_type="void_payment", source_id=bill.id)

    bill.paid_total = _q(Decimal(str(bill.paid_total)) - Decimal(str(pay.amount)))
    if Decimal(str(bill.paid_total)) < Decimal(str(bill.total)) and bill.status == "paid":
        bill.status = "posted"
    await db.delete(pay)
    await db.flush()
    return number
