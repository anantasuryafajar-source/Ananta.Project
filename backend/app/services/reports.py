"""Laporan keuangan — semuanya diturunkan dari jurnal (sumber kebenaran tunggal).

Tidak ada angka yang diinput manual: P&L, Neraca, dan Neraca Saldo dihitung
langsung dari journal_entries. AR aging dari faktur. Valuasi stok dari saldo stok.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Account, Journal, JournalEntry, Invoice, Product, StockLevel, Contact,
)

Z = Decimal("0")


def _f(v) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01")))


async def _balances(db: AsyncSession, company_id: str,
                    start: date | None, end: date | None):
    """Saldo (debit - kredit) per akun dalam rentang tanggal."""
    conds = [Journal.company_id == company_id]
    if start:
        conds.append(Journal.date >= start)
    if end:
        conds.append(Journal.date <= end)
    stmt = (
        select(
            Account.id, Account.code, Account.name, Account.type,
            Account.normal_balance,
            func.coalesce(func.sum(JournalEntry.debit), 0).label("d"),
            func.coalesce(func.sum(JournalEntry.credit), 0).label("c"),
        )
        .select_from(Account)
        .join(JournalEntry, JournalEntry.account_id == Account.id, isouter=True)
        .join(Journal, and_(Journal.id == JournalEntry.journal_id, *conds), isouter=True)
        .where(Account.company_id == company_id)
        .group_by(Account.id, Account.code, Account.name, Account.type,
                  Account.normal_balance)
        .order_by(Account.code)
    )
    rows = (await db.execute(stmt)).all()
    out = []
    for _id, code, name, type_, nb, d, c in rows:
        d, c = Decimal(str(d)), Decimal(str(c))
        signed = (d - c) if nb == "debit" else (c - d)
        out.append({
            "id": _id, "code": code, "name": name, "type": type_,
            "normal_balance": nb, "debit": d, "credit": c, "balance": signed,
        })
    return out


async def profit_loss(db: AsyncSession, company_id: str,
                      start: date, end: date) -> dict:
    rows = await _balances(db, company_id, start, end)
    income, expense = [], []
    total_income = total_expense = Z
    for r in rows:
        if r["type"] == "income":
            total_income += r["balance"]
            if r["balance"]:
                income.append({"code": r["code"], "name": r["name"],
                               "amount": _f(r["balance"])})
        elif r["type"] == "expense":
            total_expense += r["balance"]
            if r["balance"]:
                expense.append({"code": r["code"], "name": r["name"],
                                "amount": _f(r["balance"])})
    net = total_income - total_expense
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "income": income, "expense": expense,
        "total_income": _f(total_income),
        "total_expense": _f(total_expense),
        "net_profit": _f(net),
    }


async def balance_sheet(db: AsyncSession, company_id: str, as_of: date) -> dict:
    rows = await _balances(db, company_id, None, as_of)
    assets, liabilities, equity = [], [], []
    ta = tl = te = Z
    for r in rows:
        item = {"code": r["code"], "name": r["name"], "amount": _f(r["balance"])}
        if r["type"] == "asset":
            ta += r["balance"]
            if r["balance"]:
                assets.append(item)
        elif r["type"] == "liability":
            tl += r["balance"]
            if r["balance"]:
                liabilities.append(item)
        elif r["type"] == "equity":
            te += r["balance"]
            if r["balance"]:
                equity.append(item)
    # Laba berjalan (income - expense) masuk ke ekuitas
    pl = await profit_loss(db, company_id, date(as_of.year, 1, 1), as_of)
    running = Decimal(pl["net_profit"])
    te += running
    equity.append({"code": "3-9000", "name": "Laba Tahun Berjalan",
                   "amount": _f(running)})
    return {
        "as_of": as_of.isoformat(),
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": _f(ta),
        "total_liabilities_equity": _f(tl + te),
        "balanced": _f(ta) == _f(tl + te),
    }


async def trial_balance(db: AsyncSession, company_id: str, as_of: date) -> dict:
    rows = await _balances(db, company_id, None, as_of)
    items, td, tc = [], Z, Z
    for r in rows:
        if not r["debit"] and not r["credit"]:
            continue
        bal = r["balance"]
        debit = bal if r["normal_balance"] == "debit" else Z
        credit = bal if r["normal_balance"] == "credit" else Z
        if bal < 0:  # saldo terbalik
            debit, credit = (Z, -bal) if r["normal_balance"] == "debit" else (-bal, Z)
        td += debit
        tc += credit
        items.append({"code": r["code"], "name": r["name"],
                      "debit": _f(debit), "credit": _f(credit)})
    return {"as_of": as_of.isoformat(), "items": items,
            "total_debit": _f(td), "total_credit": _f(tc),
            "balanced": _f(td) == _f(tc)}


async def ar_aging(db: AsyncSession, company_id: str, as_of: date) -> dict:
    stmt = (
        select(Invoice, Contact.name)
        .join(Contact, Contact.id == Invoice.contact_id)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(["posted", "overdue"]))
        .order_by(Invoice.date)
    )
    rows = (await db.execute(stmt)).all()
    buckets = {"current": Z, "d1_30": Z, "d31_60": Z, "d61_90": Z, "d90_plus": Z}
    items = []
    for inv, cname in rows:
        outstanding = Decimal(str(inv.total)) - Decimal(str(inv.paid_total))
        if outstanding <= 0:
            continue
        ref = inv.due_date or inv.date
        age = (as_of - ref).days
        if age <= 0:
            b = "current"
        elif age <= 30:
            b = "d1_30"
        elif age <= 60:
            b = "d31_60"
        elif age <= 90:
            b = "d61_90"
        else:
            b = "d90_plus"
        buckets[b] += outstanding
        items.append({
            "number": inv.number, "contact": cname,
            "date": inv.date.isoformat(),
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "age_days": age, "bucket": b, "outstanding": _f(outstanding),
        })
    total = sum(buckets.values(), Z)
    return {
        "as_of": as_of.isoformat(),
        "buckets": {k: _f(v) for k, v in buckets.items()},
        "total": _f(total), "items": items,
    }


async def stock_valuation(db: AsyncSession, company_id: str) -> dict:
    stmt = (
        select(Product.sku, Product.name, StockLevel.quantity, StockLevel.avg_cost)
        .join(StockLevel, StockLevel.product_id == Product.id)
        .where(Product.company_id == company_id)
        .order_by(Product.sku)
    )
    rows = (await db.execute(stmt)).all()
    items, total = [], Z
    for sku, name, qty, avg in rows:
        qty, avg = Decimal(str(qty)), Decimal(str(avg))
        value = (qty * avg)
        total += value
        items.append({"sku": sku, "name": name, "quantity": _f(qty),
                      "avg_cost": _f(avg), "value": _f(value)})
    return {"items": items, "total_value": _f(total)}
