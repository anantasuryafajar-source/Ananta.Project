"""Pencatatan biaya kurir/ekspedisi + jurnal otomatis, dengan opsi split supplier.

Jurnal (ASF bayar kurir di muka):
    Dr  Beban Ekspedisi & Ongkir (6-2000)   company_share
    Dr  Utang Usaha (2-1000)                 supplier_share   (mengurangi utang ke supplier = klaim)
        Cr  Kas/Bank                              amount

Bila tanpa split, supplier_share = 0 dan seluruh amount jadi beban ASF.
Asumsi perlakuan klaim supplier via Utang Usaha — silakan dikonfirmasi/diubah.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import CourierExpense, Account
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import code_to_id

CENT = Decimal("0.01")
FREIGHT_CODE = "6-2000"  # Beban Ekspedisi & Ongkir


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


async def create_courier_expense(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    on_date: date, courier_name: str, amount: Decimal,
    invoice_id: str | None, supplier_id: str | None,
    supplier_share: Decimal, paid_account_code: str, note: str | None,
) -> CourierExpense:
    amount = _q(amount)
    supplier_share = _q(supplier_share)
    if supplier_share < 0 or supplier_share > amount:
        raise ValueError("Porsi supplier harus antara 0 dan total ongkir.")
    company_share = _q(amount - supplier_share)

    acc = await code_to_id(db, company_id)
    freight_id = await _acc_id(db, company_id, FREIGHT_CODE)
    paid_id = await _acc_id(db, company_id, paid_account_code)

    number = await next_number(
        db, company_id=company_id, doc_type="courier", on_date=on_date,
        prefix="KUR", reset="monthly",
    )

    exp = CourierExpense(
        company_id=company_id, number=number, date=on_date,
        courier_name=courier_name, invoice_id=invoice_id, supplier_id=supplier_id,
        amount=amount, supplier_share=supplier_share, company_share=company_share,
        paid_account_id=paid_id, note=note, created_by=user_id,
    )
    db.add(exp)
    await db.flush()

    j_lines: list[Line] = [Line(freight_id, debit=company_share, description="Ongkir kurir")]
    if supplier_share > 0:
        j_lines.append(Line(acc["ap"], debit=supplier_share, description="Klaim ongkir ke supplier"))
    j_lines.append(Line(paid_id, credit=amount, description=f"Bayar {courier_name}"))

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("KUR", "JV"),
        on_date=on_date, lines=j_lines, memo=f"Ongkir {number} · {courier_name}",
        source_type="courier", source_id=exp.id, created_by=user_id,
    )
    exp.journal_id = journal.id
    await db.flush()
    return exp
