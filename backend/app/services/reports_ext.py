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
    """Omzet & HPP per kuartal, dihitung dari JURNAL akun 4-1000 (Penjualan) &
    5-1000 (HPP) — sehingga histori (jurnal ringkasan) maupun faktur baru
    dua-duanya terhitung."""
    from ..models import Account
    accs = (await db.execute(
        select(Account.id, Account.code).where(
            Account.company_id == company_id,
            Account.code.in_(("4-1000", "5-1000")))
    )).all()
    code_by_id = {i: c for i, c in accs}
    if not code_by_id:
        return {"items": []}

    rows = (await db.execute(
        select(Journal.date, JournalEntry.account_id,
               JournalEntry.debit, JournalEntry.credit)
        .join(JournalEntry, JournalEntry.journal_id == Journal.id)
        .where(Journal.company_id == company_id,
               JournalEntry.account_id.in_(list(code_by_id.keys())))
    )).all()

    agg: dict[str, dict] = {}
    for d, acc_id, deb, cred in rows:
        code = code_by_id.get(acc_id)
        a = agg.setdefault(_quarter(d), {"omzet": Decimal("0"), "hpp": Decimal("0")})
        if code == "4-1000":      # Penjualan: normal kredit
            a["omzet"] += Decimal(str(cred or 0)) - Decimal(str(deb or 0))
        elif code == "5-1000":    # HPP: normal debit
            a["hpp"] += Decimal(str(deb or 0)) - Decimal(str(cred or 0))
    items = [{"quarter": k, "omzet": _f(v["omzet"]), "hpp": _f(v["hpp"]),
              "gross_profit": _f(v["omzet"] - v["hpp"])}
             for k, v in sorted(agg.items())]
    return {"items": items}


# ------------------------------------------------------------ GPM (margin) per SKU & customer
async def gpm(db: AsyncSession, company_id: str, start: date, end: date) -> dict:
    """Gross Profit Margin per SKU dan per customer (mirip sheet GPMCUST).
    Modal dari purchase_price. GPM% = margin / omzet * 100."""
    from ..models import Contact
    rows = (await db.execute(
        select(Contact.name, Product.sku, Product.name, Product.purchase_price,
               InvoiceLine.quantity, InvoiceLine.unit_price, InvoiceLine.discount)
        .join(InvoiceLine, InvoiceLine.product_id == Product.id)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .join(Contact, Contact.id == Invoice.contact_id, isouter=True)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(("posted", "paid", "overdue")),
               Invoice.date >= start, Invoice.date <= end)
    )).all()

    by_sku: dict[str, dict] = {}
    by_cust: dict[str, dict] = {}
    for cust, sku, pname, modal, qty, price, disc in rows:
        q = Decimal(str(qty or 0))
        revenue = q * Decimal(str(price or 0)) - Decimal(str(disc or 0))
        cost = q * Decimal(str(modal or 0))
        margin = revenue - cost
        s = by_sku.setdefault(sku, {"name": pname, "revenue": Decimal("0"), "margin": Decimal("0")})
        s["revenue"] += revenue
        s["margin"] += margin
        cname = cust or "(tanpa nama)"
        c = by_cust.setdefault(cname, {"revenue": Decimal("0"), "margin": Decimal("0")})
        c["revenue"] += revenue
        c["margin"] += margin

    def pct(margin, revenue):
        return round(float(margin / revenue * 100), 2) if revenue > 0 else None

    sku_items = [{"sku": k, "name": v["name"], "revenue": _f(v["revenue"]),
                  "margin": _f(v["margin"]), "gpm": pct(v["margin"], v["revenue"])}
                 for k, v in by_sku.items()]
    sku_items.sort(key=lambda x: Decimal(x["margin"]), reverse=True)
    cust_items = [{"customer": k, "revenue": _f(v["revenue"]),
                   "margin": _f(v["margin"]), "gpm": pct(v["margin"], v["revenue"])}
                  for k, v in by_cust.items()]
    cust_items.sort(key=lambda x: Decimal(x["margin"]), reverse=True)
    return {"by_sku": sku_items, "by_customer": cust_items}


# ------------------------------------------------------------ KARTU PIUTANG (statement)
async def customer_statement(db: AsyncSession, company_id: str, contact_id: str) -> dict:
    """Kartu piutang per customer: faktur & pembayaran berurutan + saldo berjalan."""
    from ..models import PaymentReceived, Contact
    contact = (await db.execute(
        select(Contact.name).where(Contact.id == contact_id,
                                   Contact.company_id == company_id)
    )).scalar_one_or_none()
    if contact is None:
        return {"customer": None, "entries": [], "balance": "0"}

    inv_rows = (await db.execute(
        select(Invoice.number, Invoice.date, Invoice.total)
        .where(Invoice.company_id == company_id,
               Invoice.contact_id == contact_id,
               Invoice.status.in_(("posted", "paid", "overdue")))
    )).all()
    pay_rows = (await db.execute(
        select(PaymentReceived.number, PaymentReceived.date, PaymentReceived.amount)
        .join(Invoice, Invoice.id == PaymentReceived.invoice_id)
        .where(PaymentReceived.company_id == company_id,
               Invoice.contact_id == contact_id)
    )).all()

    entries = (
        [{"date": d, "ref": n, "type": "Faktur", "debit": Decimal(str(t or 0)),
          "credit": Decimal("0")} for n, d, t in inv_rows]
        + [{"date": d, "ref": n, "type": "Pembayaran", "debit": Decimal("0"),
            "credit": Decimal(str(a or 0))} for n, d, a in pay_rows]
    )
    entries.sort(key=lambda e: (e["date"], e["type"]))
    bal = Decimal("0")
    out = []
    for e in entries:
        bal += e["debit"] - e["credit"]
        out.append({"date": str(e["date"]), "ref": e["ref"], "type": e["type"],
                    "debit": _f(e["debit"]), "credit": _f(e["credit"]),
                    "balance": _f(bal)})
    return {"customer": contact, "entries": out, "balance": _f(bal)}


# ------------------------------------------------------------ KPI SALES
async def sales_kpi(db: AsyncSession, company_id: str, start: date, end: date) -> dict:
    """Kinerja per sales (user pembuat faktur): jumlah faktur, omzet, terbayar."""
    from ..models import User
    rows = (await db.execute(
        select(User.full_name, Invoice.total, Invoice.paid_total)
        .join(User, User.id == Invoice.created_by, isouter=True)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(("posted", "paid", "overdue")),
               Invoice.date >= start, Invoice.date <= end)
    )).all()
    agg: dict[str, dict] = {}
    for name, total, paid in rows:
        key = name or "(tanpa user)"
        a = agg.setdefault(key, {"count": 0, "omzet": Decimal("0"),
                                 "paid": Decimal("0")})
        a["count"] += 1
        a["omzet"] += Decimal(str(total or 0))
        a["paid"] += Decimal(str(paid or 0))
    items = [{"sales": k, "invoices": v["count"], "omzet": _f(v["omzet"]),
              "paid": _f(v["paid"]),
              "collection_pct": round(float(v["paid"] / v["omzet"] * 100), 1)
              if v["omzet"] > 0 else None}
             for k, v in agg.items()]
    items.sort(key=lambda x: Decimal(x["omzet"]), reverse=True)
    return {"items": items}


# ------------------------------------------------------------ PPN / PPh RINGKAS
async def tax_summary(db: AsyncSession, company_id: str, start: date, end: date) -> dict:
    """Ringkasan pajak per bulan: PPN keluaran (faktur jual) vs PPN masukan (bill)."""
    from ..models import Bill
    out_rows = (await db.execute(
        select(Invoice.date, Invoice.tax_total)
        .where(Invoice.company_id == company_id,
               Invoice.status.in_(("posted", "paid", "overdue")),
               Invoice.date >= start, Invoice.date <= end)
    )).all()
    in_rows = (await db.execute(
        select(Bill.date, Bill.tax_total)
        .where(Bill.company_id == company_id,
               Bill.date >= start, Bill.date <= end)
    )).all()
    agg: dict[str, dict] = {}
    for d, t in out_rows:
        a = agg.setdefault(d.strftime("%Y-%m"), {"out": Decimal("0"), "in": Decimal("0")})
        a["out"] += Decimal(str(t or 0))
    for d, t in in_rows:
        a = agg.setdefault(d.strftime("%Y-%m"), {"out": Decimal("0"), "in": Decimal("0")})
        a["in"] += Decimal(str(t or 0))
    months = [{"month": k, "vat_out": _f(v["out"]), "vat_in": _f(v["in"]),
               "net_payable": _f(v["out"] - v["in"])}
              for k, v in sorted(agg.items())]
    tot_out = sum((Decimal(m["vat_out"]) for m in months), Decimal("0"))
    tot_in = sum((Decimal(m["vat_in"]) for m in months), Decimal("0"))
    return {"months": months, "total_vat_out": _f(tot_out),
            "total_vat_in": _f(tot_in), "net_payable": _f(tot_out - tot_in)}
