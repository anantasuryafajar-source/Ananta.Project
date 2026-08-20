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
from .units import format_qty

Z = Decimal("0")


def _f(v) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01")))


async def _balances(db: AsyncSession, company_id: str,
                    start: date | None, end: date | None):
    """Saldo (debit - kredit) per akun dalam rentang tanggal.

    Penyaringan tanggal WAJIB terjadi sebelum penjumlahan, bukan di klausa ON
    sebuah LEFT JOIN. Versi lama menaruh `Journal.date >= start` di ON-nya
    outer join ke `journals`; karena penjumlahannya mengambil
    `JournalEntry.debit` yang sudah ikut lewat join sebelumnya, baris di luar
    periode TIDAK terbuang — kolom `journals` cuma jadi NULL sementara
    nominalnya tetap terjumlah. Akibatnya setiap periode Laba Rugi menampilkan
    angka SEUMUR HIDUP perusahaan, dan `as_of` di Neraca/Neraca Saldo juga
    diabaikan. Bentuk subquery di bawah membuang barisnya lewat WHERE, jadi
    filternya benar-benar berlaku.
    """
    conds = [Journal.company_id == company_id]
    if start:
        conds.append(Journal.date >= start)
    if end:
        conds.append(Journal.date <= end)

    agg = (
        select(
            JournalEntry.account_id.label("account_id"),
            func.coalesce(func.sum(JournalEntry.debit), 0).label("d"),
            func.coalesce(func.sum(JournalEntry.credit), 0).label("c"),
        )
        .select_from(JournalEntry)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(and_(*conds))
        .group_by(JournalEntry.account_id)
        .subquery()
    )

    stmt = (
        select(
            Account.id, Account.code, Account.name, Account.type,
            Account.normal_balance,
            func.coalesce(agg.c.d, 0).label("d"),
            func.coalesce(agg.c.c, 0).label("c"),
        )
        .select_from(Account)
        .join(agg, agg.c.account_id == Account.id, isouter=True)
        .where(Account.company_id == company_id)
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
    """Umur piutang, dihitung dari JADWAL TERMIN kalau fakturnya punya.

    Faktur dengan kesepakatan "tagih saat order berikutnya" tidak punya tanggal
    jatuh tempo. Kalau ia diperlakukan seperti faktur biasa (umur dihitung dari
    tanggal faktur), ia akan tampil menunggak 90+ hari padahal itu justru yang
    disepakati — dan orang akan menagih customer yang tidak terlambat. Karena
    itu termin tanpa tanggal masuk ember sendiri: `tanpa_tempo`.

    Faktur lama yang belum punya jadwal termin tetap dihitung dengan cara lama
    (`due_date` faktur), jadi tidak ada angka historis yang bergeser.
    """
    from ..models import InvoiceTerm
    stmt = (
        select(Invoice, Contact.name)
        .join(Contact, Contact.id == Invoice.contact_id)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(["posted", "overdue"]))
        .order_by(Invoice.date)
    )
    rows = (await db.execute(stmt)).all()

    inv_ids = [inv.id for inv, _ in rows]
    terms_by_inv: dict[str, list] = {}
    if inv_ids:
        for t in (await db.execute(
            select(InvoiceTerm).where(InvoiceTerm.invoice_id.in_(inv_ids))
            .order_by(InvoiceTerm.sequence)
        )).scalars().all():
            terms_by_inv.setdefault(t.invoice_id, []).append(t)

    buckets = {"current": Z, "d1_30": Z, "d31_60": Z, "d61_90": Z,
               "d90_plus": Z, "tanpa_tempo": Z}
    items = []

    def _bucket(age: int) -> str:
        if age <= 0:
            return "current"
        if age <= 30:
            return "d1_30"
        if age <= 60:
            return "d31_60"
        if age <= 90:
            return "d61_90"
        return "d90_plus"

    for inv, cname in rows:
        outstanding = Decimal(str(inv.total)) - Decimal(str(inv.paid_total))
        if outstanding <= 0:
            continue

        jadwal = terms_by_inv.get(inv.id)
        if not jadwal:
            ref = inv.due_date or inv.date
            age = (as_of - ref).days
            b = _bucket(age)
            buckets[b] += outstanding
            items.append({
                "number": inv.number, "contact": cname,
                "date": inv.date.isoformat(),
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "age_days": age, "bucket": b, "outstanding": _f(outstanding),
            })
            continue

        for t in jadwal:
            sisa = Decimal(str(t.amount)) - Decimal(str(t.settled_amount))
            if sisa <= 0:
                continue
            if t.due_date is None:
                b, age = "tanpa_tempo", None
            else:
                age = (as_of - t.due_date).days
                b = _bucket(age)
            buckets[b] += sisa
            items.append({
                "number": inv.number, "contact": cname,
                "date": inv.date.isoformat(),
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "term_kind": t.kind, "term_sequence": t.sequence,
                "age_days": age, "bucket": b, "outstanding": _f(sisa),
            })

    total = sum(buckets.values(), Z)
    return {
        "as_of": as_of.isoformat(),
        "buckets": {k: _f(v) for k, v in buckets.items()},
        "total": _f(total), "items": items,
    }


async def stock_valuation(db: AsyncSession, company_id: str) -> dict:
    """Valuasi stok. Kuantitas & avg_cost dalam BOTOL; `qty_display` menampilkan
    ulang sebagai 'dus + botol' untuk dibaca manusia."""
    stmt = (
        select(Product.sku, Product.name, Product.pack_size,
               StockLevel.quantity, StockLevel.avg_cost)
        .join(StockLevel, StockLevel.product_id == Product.id)
        .where(Product.company_id == company_id)
        .order_by(Product.name)
    )
    rows = (await db.execute(stmt)).all()
    items, total = [], Z
    for sku, name, pack_size, qty, avg in rows:
        qty, avg = Decimal(str(qty)), Decimal(str(avg))
        value = (qty * avg)
        total += value
        items.append({"sku": sku, "name": name, "quantity": _f(qty),
                      "pack_size": pack_size,
                      "qty_display": format_qty(qty, pack_size),
                      "avg_cost": _f(avg), "value": _f(value)})
    return {"items": items, "total_value": _f(total)}
