"""Service jurnal: satu-satunya pintu untuk membuat jurnal akuntansi.

Invarian inti sistem: setiap jurnal HARUS balance (sum debit == sum credit).
Semua transaksi keuangan (faktur, tagihan, pembayaran, penyesuaian) memanggil
post_journal() agar tidak pernah ada jurnal pincang.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Journal, JournalEntry

CENT = Decimal("0.01")


class JournalNotBalanced(ValueError):
    pass


@dataclass
class Line:
    account_id: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: str | None = None


def _q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(CENT)


async def post_journal(
    db: AsyncSession,
    *,
    company_id: str,
    number: str,
    on_date: date,
    lines: list[Line],
    memo: str | None = None,
    source_type: str = "manual",
    source_id: str | None = None,
    created_by: str | None = None,
) -> Journal:
    if len(lines) < 2:
        raise JournalNotBalanced("Jurnal butuh minimal dua baris.")

    total_debit = sum((_q(l.debit) for l in lines), Decimal("0"))
    total_credit = sum((_q(l.credit) for l in lines), Decimal("0"))

    if total_debit != total_credit:
        raise JournalNotBalanced(
            f"Jurnal tidak balance: debit {total_debit} ≠ kredit {total_credit}."
        )
    if total_debit == 0:
        raise JournalNotBalanced("Total jurnal nol.")

    for l in lines:
        d, c = _q(l.debit), _q(l.credit)
        if d < 0 or c < 0:
            raise JournalNotBalanced("Nilai debit/kredit tidak boleh negatif.")
        if d > 0 and c > 0:
            raise JournalNotBalanced("Satu baris tidak boleh debit DAN kredit sekaligus.")

    # --- Tutup buku: tolak posting pada periode yang sudah dikunci ---
    from ..models import Company
    lock = (await db.execute(
        select(Company.period_lock_date).where(Company.id == company_id)
    )).scalar_one_or_none()
    if lock is not None and on_date <= lock:
        raise JournalNotBalanced(
            f"Periode sampai {lock} sudah ditutup — tidak bisa memposting "
            f"transaksi bertanggal {on_date}. Minta owner membuka periode dulu.")

    journal = Journal(
        company_id=company_id, number=number, date=on_date, memo=memo,
        source_type=source_type, source_id=source_id, created_by=created_by,
        entries=[
            JournalEntry(
                account_id=l.account_id, debit=_q(l.debit),
                credit=_q(l.credit), description=l.description,
            )
            for l in lines
        ],
    )
    db.add(journal)
    await db.flush()
    return journal
