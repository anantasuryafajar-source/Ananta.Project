"""Investor: penerimaan dana & pembayaran (dividen / pengembalian pokok).

Jurnal:
  Terima dana pokok :  Dr Kas/Bank,           Cr 2-3000 Utang Investor
  Payout dividend   :  Dr 6-4000 Beban Investor, Cr Kas/Bank
  Payout principal  :  Dr 2-3000 Utang Investor, Cr Kas/Bank
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Investor, InvestorPayout, Account
from .journal import Line, post_journal
from .numbering import next_number

CENT = Decimal("0.01")
LIAB_CODE = "2-3000"   # Utang Investor
EXP_CODE = "6-4000"    # Beban Investor


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


async def _acc_id(db, company_id, code) -> str:
    aid = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if not aid:
        raise ValueError(f"Akun {code} tidak ada di CoA.")
    return aid


async def receive_funds(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    investor_id: str, on_date: date, amount: Decimal, cash_account_code: str,
) -> Investor:
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nominal harus lebih dari 0.")
    inv = (await db.execute(
        select(Investor).where(Investor.id == investor_id,
                               Investor.company_id == company_id)
    )).scalar_one()

    cash_id = await _acc_id(db, company_id, cash_account_code)
    liab_id = await _acc_id(db, company_id, LIAB_CODE)
    number = await next_number(db, company_id=company_id, doc_type="invfund",
                               on_date=on_date, prefix="IF", reset="monthly")
    await post_journal(
        db, company_id=company_id, number=number, on_date=on_date,
        lines=[
            Line(cash_id, debit=amount, description=f"Dana masuk {inv.name}"),
            Line(liab_id, credit=amount, description=f"Utang investor {inv.name}"),
        ],
        memo=f"Penerimaan dana investor {inv.name}",
        source_type="investor", source_id=inv.id, created_by=user_id,
    )
    inv.received_total = _q(Decimal(str(inv.received_total)) + amount)
    await db.flush()
    return inv


async def create_payout(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    investor_id: str, on_date: date, ptype: str, amount: Decimal,
    cash_account_code: str, note: str | None,
) -> InvestorPayout:
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nominal harus lebih dari 0.")
    if ptype not in ("dividend", "principal"):
        raise ValueError("Tipe payout harus dividend atau principal.")
    inv = (await db.execute(
        select(Investor).where(Investor.id == investor_id,
                               Investor.company_id == company_id)
    )).scalar_one()

    cash_id = await _acc_id(db, company_id, cash_account_code)
    debit_id = await _acc_id(db, company_id,
                             EXP_CODE if ptype == "dividend" else LIAB_CODE)
    number = await next_number(db, company_id=company_id, doc_type="payout",
                               on_date=on_date, prefix="IP", reset="monthly")

    payout = InvestorPayout(
        company_id=company_id, investor_id=investor_id, number=number,
        date=on_date, type=ptype, amount=amount, paid_account_id=cash_id,
        note=note, created_by=user_id,
    )
    db.add(payout)
    await db.flush()

    label = "Dividen" if ptype == "dividend" else "Pengembalian pokok"
    journal = await post_journal(
        db, company_id=company_id, number=number.replace("IP", "JV"),
        on_date=on_date,
        lines=[
            Line(debit_id, debit=amount, description=f"{label} {inv.name}"),
            Line(cash_id, credit=amount, description=f"Bayar {inv.name}"),
        ],
        memo=f"{label} investor {inv.name} ({number})",
        source_type="investor_payout", source_id=payout.id, created_by=user_id,
    )
    payout.journal_id = journal.id
    await db.flush()
    return payout
