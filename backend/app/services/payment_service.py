"""Pencatatan pembayaran: pelunasan piutang (masuk) & pelunasan utang (keluar).

Pembayaran diterima (pelunasan faktur penjualan):
    Dr  Kas/Bank            amount
        Cr  Piutang Usaha        amount

Pembayaran dilakukan (pelunasan tagihan pembelian):
    Dr  Utang Usaha         amount
        Cr  Kas/Bank             amount
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Invoice, PaymentReceived, Bill, PaymentMade,
)
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import code_to_id

CENT = Decimal("0.01")


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


async def receive_payment(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    invoice_id: str, on_date: date, amount: Decimal,
    cash_account_id: str | None = None,
) -> PaymentReceived:
    invoice = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id,
                              Invoice.company_id == company_id)
    )).scalar_one()
    acc = await code_to_id(db, company_id)
    cash_id = cash_account_id or acc["cash"]
    amount = _q(amount)

    number = await next_number(
        db, company_id=company_id, doc_type="payment_in", on_date=on_date,
        prefix="RCPT", reset="monthly",
    )

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("RCPT", "JV"),
        on_date=on_date,
        lines=[
            Line(cash_id, debit=amount, description="Penerimaan kas"),
            Line(acc["ar"], credit=amount, description="Pelunasan piutang"),
        ],
        memo=f"Penerimaan {number} untuk {invoice.number}",
        source_type="payment", source_id=invoice.id, created_by=user_id,
    )

    pay = PaymentReceived(
        company_id=company_id, number=number, invoice_id=invoice.id,
        date=on_date, amount=amount, cash_account_id=cash_id,
        journal_id=journal.id,
    )
    db.add(pay)

    invoice.paid_total = _q(Decimal(str(invoice.paid_total)) + amount)
    if Decimal(str(invoice.paid_total)) >= Decimal(str(invoice.total)):
        invoice.status = "paid"
    await db.flush()
    return pay


async def pay_bill(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    bill_id: str, on_date: date, amount: Decimal,
    cash_account_id: str | None = None,
) -> PaymentMade:
    bill = (await db.execute(
        select(Bill).where(Bill.id == bill_id, Bill.company_id == company_id)
    )).scalar_one()
    acc = await code_to_id(db, company_id)
    cash_id = cash_account_id or acc["cash"]
    amount = _q(amount)

    number = await next_number(
        db, company_id=company_id, doc_type="payment_out", on_date=on_date,
        prefix="PAY", reset="monthly",
    )

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("PAY", "JV"),
        on_date=on_date,
        lines=[
            Line(acc["ap"], debit=amount, description="Pelunasan utang"),
            Line(cash_id, credit=amount, description="Pengeluaran kas"),
        ],
        memo=f"Pembayaran {number} untuk {bill.number}",
        source_type="payment", source_id=bill.id, created_by=user_id,
    )

    pay = PaymentMade(
        company_id=company_id, number=number, bill_id=bill.id,
        date=on_date, amount=amount, cash_account_id=cash_id,
        journal_id=journal.id,
    )
    db.add(pay)

    bill.paid_total = _q(Decimal(str(bill.paid_total)) + amount)
    if Decimal(str(bill.paid_total)) >= Decimal(str(bill.total)):
        bill.status = "paid"
    await db.flush()
    return pay
