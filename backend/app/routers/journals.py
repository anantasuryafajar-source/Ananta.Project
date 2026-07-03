"""Modul Akuntansi: daftar jurnal, detail entri, dan buku besar per akun."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Journal, JournalEntry, Account, User
from ..deps import current_user

router = APIRouter(prefix="/journals", tags=["journals"])


def _s(v) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01")))


@router.get("")
async def list_journals(
    q: str | None = Query(default=None, description="cari nomor/memo"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (select(Journal)
            .where(Journal.company_id == user.company_id)
            .order_by(Journal.date.desc(), Journal.number.desc()))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Journal.number.ilike(like) | Journal.memo.ilike(like))
    stmt = stmt.offset(offset).limit(limit)
    journals = (await db.execute(stmt)).scalars().all()
    return [{
        "id": j.id, "number": j.number, "date": str(j.date),
        "memo": j.memo, "source_type": j.source_type,
        "total": _s(sum((Decimal(str(e.debit or 0)) for e in j.entries), Decimal("0"))),
    } for j in journals]


@router.get("/ledger")
async def ledger(
    account_id: str = Query(...),
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Buku besar satu akun: saldo awal + mutasi berurutan + saldo berjalan."""
    acc = (await db.execute(
        select(Account).where(Account.id == account_id,
                              Account.company_id == user.company_id)
    )).scalar_one_or_none()
    if acc is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")

    # saldo awal = mutasi sebelum periode
    prev = (await db.execute(
        select(JournalEntry.debit, JournalEntry.credit)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(Journal.company_id == user.company_id,
               JournalEntry.account_id == account_id,
               Journal.date < start)
    )).all()
    opening = sum((Decimal(str(d or 0)) - Decimal(str(c or 0)) for d, c in prev),
                  Decimal("0"))
    if acc.normal_balance == "credit":
        opening = -opening

    rows = (await db.execute(
        select(Journal.date, Journal.number, Journal.memo,
               JournalEntry.debit, JournalEntry.credit, JournalEntry.description)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(Journal.company_id == user.company_id,
               JournalEntry.account_id == account_id,
               Journal.date >= start, Journal.date <= end)
        .order_by(Journal.date, Journal.number)
    )).all()

    balance = opening
    entries = []
    for d, num, memo, deb, cred, desc in rows:
        deb = Decimal(str(deb or 0))
        cred = Decimal(str(cred or 0))
        delta = (deb - cred) if acc.normal_balance == "debit" else (cred - deb)
        balance += delta
        entries.append({
            "date": str(d), "number": num, "memo": desc or memo,
            "debit": _s(deb), "credit": _s(cred), "balance": _s(balance),
        })

    return {
        "account": {"code": acc.code, "name": acc.name,
                    "normal_balance": acc.normal_balance},
        "opening_balance": _s(opening),
        "entries": entries,
        "closing_balance": _s(balance),
    }


@router.get("/{journal_id}")
async def journal_detail(
    journal_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    j = (await db.execute(
        select(Journal).where(Journal.id == journal_id,
                              Journal.company_id == user.company_id)
    )).scalar_one_or_none()
    if j is None:
        raise HTTPException(status_code=404, detail="Jurnal tidak ditemukan.")

    acc_ids = [e.account_id for e in j.entries]
    accounts = {}
    if acc_ids:
        rows = (await db.execute(
            select(Account.id, Account.code, Account.name)
            .where(Account.id.in_(acc_ids))
        )).all()
        accounts = {i: (c, n) for i, c, n in rows}

    return {
        "id": j.id, "number": j.number, "date": str(j.date),
        "memo": j.memo, "source_type": j.source_type,
        "entries": [{
            "account_code": accounts.get(e.account_id, ("?", "?"))[0],
            "account_name": accounts.get(e.account_id, ("?", "?"))[1],
            "debit": _s(e.debit), "credit": _s(e.credit),
            "description": e.description,
        } for e in j.entries],
    }
