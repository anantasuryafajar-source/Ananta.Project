"""Laporan tambahan khas ASF: arus kas, AR limit, komisi per-SKU, rekap kuartal.

Dipisah dari reports.py agar tidak menyentuh laporan lama. Semua read-only.
Perhitungan grouping dilakukan di Python agar netral terhadap dialek DB.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Journal, JournalEntry, Account, Invoice, InvoiceLine, Product, Contact,
)


def _f(v) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01")))


def _quarter(d: date) -> str:
    return f"Q{(d.month - 1) // 3 + 1}-{str(d.year)[2:]}"


# ------------------------------------------------------------ ARUS KAS
async def cashflow(db: AsyncSession, company_id: str, start: date, end: date) -> dict:
    """Arus kas dari mutasi jurnal pada akun Kas/Bank (kode 1-10xx / 1-11xx)."""
    cash_ids = (await db.execute(
        select(Account.id).where(
            Account.company_id == company_id,
            (Account.code.like("1-10%")) | (Account.code.like("1-11%")),
        )
    )).scalars().all()
    if not cash_ids:
        return {"months": [], "total_in": "0", "total_out": "0", "net": "0"}

    rows = (await db.execute(
        select(Journal.date, JournalEntry.debit, JournalEntry.credit)
        .join(JournalEntry, JournalEntry.journal_id == Journal.id)
        .where(Journal.company_id == company_id,
               JournalEntry.account_id.in_(cash_ids),
               Journal.date >= start, Journal.date <= end)
    )).all()

    buckets: dict[str, list[Decimal]] = {}
    for d, deb, cred in rows:
        key = d.strftime("%Y-%m")
        b = buckets.setdefault(key, [Decimal("0"), Decimal("0")])
        b[0] += Decimal(str(deb or 0))   # masuk
        b[1] += Decimal(str(cred or 0))  # keluar
    months = [
        {"month": k, "in": _f(v[0]), "out": _f(v[1]), "net": _f(v[0] - v[1])}
        for k, v in sorted(buckets.items())
    ]
    tin = sum((Decimal(m["in"]) for m in months), Decimal("0"))
    tout = sum((Decimal(m["out"]) for m in months), Decimal("0"))
    return {"months": months, "total_in": _f(tin), "total_out": _f(tout),
            "net": _f(tin - tout)}


# ------------------------------------------------------------ AR LIMIT
async def ar_limit(db: AsyncSession, company_id: str) -> dict:
    """Outstanding piutang per pelanggan vs limit kredit (mirip sheet AR SYSTEM)."""
    rows = (await db.execute(
        select(Contact.id, Contact.name, Contact.credit_limit,
               Invoice.total, Invoice.paid_total, Invoice.status)
        .join(Invoice, Invoice.contact_id == Contact.id)
        .where(Contact.company_id == company_id,
               Invoice.status.in_(("posted", "overdue")))
    )).all()

    agg: dict[str, dict] = {}
    for cid, name, limit, total, paid, _st in rows:
        a = agg.setdefault(cid, {"name": name, "limit": Decimal(str(limit or 0)),
                                 "outstanding": Decimal("0")})
        a["outstanding"] += Decimal(str(total or 0)) - Decimal(str(paid or 0))

    items = []
    for a in agg.values():
        if a["outstanding"] <= 0:
            continue
        limit = a["limit"]
        ratio = float(a["outstanding"] / limit) if limit > 0 else None
        status = ("TANPA LIMIT" if limit == 0
                  else "LEBIH LIMIT" if a["outstanding"] > limit else "AMAN")
        items.append({"customer": a["name"], "outstanding": _f(a["outstanding"]),
                      "credit_limit": _f(limit),
                      "ratio": round(ratio, 4) if ratio is not None else None,
                      "status": status})
    items.sort(key=lambda x: Decimal(x["outstanding"]), reverse=True)
    total = sum((Decimal(i["outstanding"]) for i in items), Decimal("0"))
    return {"items": items, "total_outstanding": _f(total)}


# ------------------------------------------------------------ KOMISI PER-SKU
async def commission(db: AsyncSession, company_id: str, start: date, end: date,
                     rate: float = 0.05) -> dict:
    """Komisi berbasis margin per SKU (modal dari purchase_price, seperti sheet KOMISI).
    commission = (harga_jual - modal) * qty * rate."""
    rows = (await db.execute(
        select(Product.sku, Product.name, Product.purchase_price,
               InvoiceLine.quantity, InvoiceLine.unit_price, InvoiceLine.discount)
        .join(InvoiceLine, InvoiceLine.product_id == Product.id)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(("posted", "paid", "overdue")),
               Invoice.date >= start, Invoice.date <= end)
    )).all()

    agg: dict[str, dict] = {}
    for sku, name, modal, qty, price, disc in rows:
        q = Decimal(str(qty or 0))
        revenue = q * Decimal(str(price or 0)) - Decimal(str(disc or 0))
        cost = q * Decimal(str(modal or 0))
        margin = revenue - cost
        a = agg.setdefault(sku, {"name": name, "qty": Decimal("0"),
                                 "revenue": Decimal("0"), "margin": Decimal("0")})
        a["qty"] += q
        a["revenue"] += revenue
        a["margin"] += margin

    items = []
    for sku, a in agg.items():
        comm = a["margin"] * Decimal(str(rate))
        items.append({"sku": sku, "name": a["name"], "qty": _f(a["qty"]),
                      "revenue": _f(a["revenue"]), "margin": _f(a["margin"]),
                      "commission": _f(comm)})
    items.sort(key=lambda x: Decimal(x["margin"]), reverse=True)
    total_comm = sum((Decimal(i["commission"]) for i in items), Decimal("0"))
    return {"rate": rate, "items": items, "total_commission": _f(total_comm)}


# ------------------------------------------------------------ REKAP KUARTAL
async def quarterly_recap(db: AsyncSession, company_id: str) -> dict:
    """Omzet, HPP (perkiraan dari modal), dan margin per kuartal (mirip REKAPQUARTAL)."""
    rows = (await db.execute(
        select(Invoice.date, Product.purchase_price,
               InvoiceLine.quantity, InvoiceLine.unit_price, InvoiceLine.discount)
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .join(Product, Product.id == InvoiceLine.product_id, isouter=True)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(("posted", "paid", "overdue")))
    )).all()

    agg: dict[str, dict] = {}
    for d, modal, qty, price, disc in rows:
        q = Decimal(str(qty or 0))
        rev = q * Decimal(str(price or 0)) - Decimal(str(disc or 0))
        hpp = q * Decimal(str(modal or 0))
        a = agg.setdefault(_quarter(d), {"omzet": Decimal("0"), "hpp": Decimal("0")})
        a["omzet"] += rev
        a["hpp"] += hpp
    items = [{"quarter": k, "omzet": _f(v["omzet"]), "hpp": _f(v["hpp"]),
              "gross_profit": _f(v["omzet"] - v["hpp"])}
             for k, v in sorted(agg.items())]
    return {"items": items}
