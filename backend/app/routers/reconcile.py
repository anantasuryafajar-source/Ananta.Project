"""Rekonsiliasi bank: cocokkan mutasi jurnal akun bank/kas dengan rekening koran.

Alur: pilih akun bank + periode -> tampilkan mutasi (debit/kredit) beserta status
tercocok/belum -> user toggle 'cocok' per baris -> ringkasan menunjukkan saldo
buku, jumlah tercocok, dan selisih yang belum tercocok.
"""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import (
    Account, Journal, JournalEntry, BankReconMark, User,
)
from ..deps import current_user, require_roles

router = APIRouter(prefix="/reconcile", tags=["reconcile"])


def _s(v) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01")))


@router.get("/accounts")
async def bank_accounts(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """Akun kas & bank (kode 1-10xx / 1-11xx)."""
    rows = (await db.execute(
        select(Account.id, Account.code, Account.name)
        .where(Account.company_id == user.company_id,
               (Account.code.like("1-10%")) | (Account.code.like("1-11%")))
        .order_by(Account.code)
    )).all()
    return [{"id": i, "code": c, "name": n} for i, c, n in rows]


@router.get("/entries")
async def entries(
    account_id: str = Query(...),
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    acc = (await db.execute(
        select(Account).where(Account.id == account_id,
                              Account.company_id == user.company_id)
    )).scalar_one_or_none()
    if acc is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")

    rows = (await db.execute(
        select(JournalEntry.id, Journal.date, Journal.number, Journal.memo,
               JournalEntry.debit, JournalEntry.credit)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(Journal.company_id == user.company_id,
               JournalEntry.account_id == account_id,
               Journal.date >= start, Journal.date <= end)
        .order_by(Journal.date, Journal.number)
    )).all()

    marked = set((await db.execute(
        select(BankReconMark.entry_id)
        .where(BankReconMark.account_id == account_id)
    )).scalars().all())

    items = []
    book = Decimal("0")
    reconciled = Decimal("0")
    for eid, d, num, memo, deb, cred in rows:
        deb = Decimal(str(deb or 0)); cred = Decimal(str(cred or 0))
        delta = deb - cred
        book += delta
        is_marked = eid in marked
        if is_marked:
            reconciled += delta
        items.append({
            "entry_id": eid, "date": str(d), "number": num, "memo": memo,
            "debit": _s(deb), "credit": _s(cred), "reconciled": is_marked,
        })
    return {
        "account": {"code": acc.code, "name": acc.name},
        "book_balance": _s(book),
        "reconciled_balance": _s(reconciled),
        "unreconciled": _s(book - reconciled),
        "entries": items,
    }


class ToggleIn(BaseModel):
    entry_id: str
    account_id: str
    reconciled: bool
    statement_date: date | None = None


@router.post("/toggle")
async def toggle(
    body: ToggleIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(
        select(BankReconMark).where(BankReconMark.entry_id == body.entry_id)
    )).scalar_one_or_none()

    if body.reconciled and existing is None:
        db.add(BankReconMark(
            company_id=user.company_id, entry_id=body.entry_id,
            account_id=body.account_id, statement_date=body.statement_date,
            marked_by=user.id))
    elif not body.reconciled and existing is not None:
        await db.execute(
            delete(BankReconMark).where(BankReconMark.entry_id == body.entry_id))
    await db.commit()
    return {"ok": True, "reconciled": body.reconciled}
