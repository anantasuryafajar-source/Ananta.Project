from decimal import Decimal
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import (
    Invoice, Bill, StockLevel, Product, User, Contact, Account,
    Journal, JournalEntry,
)
from ..deps import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _s(v) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01")))


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _prev_month_start(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


@router.get("/summary")
async def summary(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    cid = user.company_id
    today = date.today()
    m0 = _month_start(today)
    m_prev = _prev_month_start(today)
    OPEN = ("posted", "overdue")
    SOLD = ("posted", "paid", "overdue")

    # ---- KPI utama ----
    # Omzet dihitung dari JURNAL akun 4-1000 (Penjualan) agar histori
    # (jurnal ringkasan) maupun faktur baru dua-duanya terhitung.
    sales_acc_id = (await db.execute(
        select(Account.id).where(Account.company_id == cid,
                                 Account.code == "4-1000")
    )).scalar_one_or_none()

    async def _sales_between(d_start, d_end):
        if not sales_acc_id:
            return Decimal("0")
        deb, cred = (await db.execute(
            select(func.coalesce(func.sum(JournalEntry.debit), 0),
                   func.coalesce(func.sum(JournalEntry.credit), 0))
            .join(Journal, Journal.id == JournalEntry.journal_id)
            .where(Journal.company_id == cid,
                   JournalEntry.account_id == sales_acc_id,
                   Journal.date >= d_start, Journal.date < d_end)
        )).one()
        return Decimal(str(cred)) - Decimal(str(deb))

    next_m = (m0 + timedelta(days=32)).replace(day=1)
    revenue = await _sales_between(m0, next_m)
    revenue_prev = await _sales_between(m_prev, m0)
    receivable = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total - Invoice.paid_total), 0))
        .where(Invoice.company_id == cid, Invoice.status.in_(OPEN))
    )).scalar_one()
    payable = (await db.execute(
        select(func.coalesce(func.sum(Bill.total - Bill.paid_total), 0))
        .where(Bill.company_id == cid, Bill.status.in_(OPEN))
    )).scalar_one()
    stock_value = (await db.execute(
        select(func.coalesce(func.sum(StockLevel.quantity * StockLevel.avg_cost), 0))
        .join(Product, Product.id == StockLevel.product_id)
        .where(Product.company_id == cid)
    )).scalar_one()

    # ---- saldo kas & bank (mutasi jurnal akun 1-10xx / 1-11xx) ----
    cash_ids = (await db.execute(
        select(Account.id).where(
            Account.company_id == cid,
            (Account.code.like("1-10%")) | (Account.code.like("1-11%")),
        )
    )).scalars().all()
    cash_balance = Decimal("0")
    if cash_ids:
        deb, cred = (await db.execute(
            select(func.coalesce(func.sum(JournalEntry.debit), 0),
                   func.coalesce(func.sum(JournalEntry.credit), 0))
            .join(Journal, Journal.id == JournalEntry.journal_id)
            .where(Journal.company_id == cid,
                   JournalEntry.account_id.in_(cash_ids))
        )).one()
        cash_balance = Decimal(str(deb)) - Decimal(str(cred))

    # ---- tren omzet 6 bulan ----
    six_ago = (m0 - timedelta(days=1)).replace(day=1)
    for _ in range(4):
        six_ago = (six_ago - timedelta(days=1)).replace(day=1)
    trend_rows = []
    if sales_acc_id:
        trend_rows = (await db.execute(
            select(Journal.date, JournalEntry.debit, JournalEntry.credit)
            .join(JournalEntry, JournalEntry.journal_id == Journal.id)
            .where(Journal.company_id == cid,
                   JournalEntry.account_id == sales_acc_id,
                   Journal.date >= six_ago)
        )).all()
    buckets: dict[str, Decimal] = {}
    cursor = six_ago
    while cursor <= m0:
        buckets[cursor.strftime("%Y-%m")] = Decimal("0")
        nxt = (cursor + timedelta(days=32)).replace(day=1)
        cursor = nxt
    for d, deb, cred in trend_rows:
        key = d.strftime("%Y-%m")
        if key in buckets:
            buckets[key] += Decimal(str(cred or 0)) - Decimal(str(deb or 0))
    trend = [{"month": k, "omzet": _s(v)} for k, v in sorted(buckets.items())]

    # ---- PERINGATAN ----
    # 1) stok di bawah minimum (agregat semua gudang)
    stock_rows = (await db.execute(
        select(Product.sku, Product.name, Product.min_stock,
               func.coalesce(func.sum(StockLevel.quantity), 0))
        .join(StockLevel, StockLevel.product_id == Product.id, isouter=True)
        .where(Product.company_id == cid)
        .group_by(Product.id, Product.sku, Product.name, Product.min_stock)
    )).all()
    low_stock = [
        {"sku": sku, "name": name, "quantity": _s(qty), "min_stock": _s(ms)}
        for sku, name, ms, qty in stock_rows
        if Decimal(str(ms or 0)) > 0 and Decimal(str(qty or 0)) < Decimal(str(ms))
    ][:8]

    # 2) faktur jatuh tempo / telat
    od_rows = (await db.execute(
        select(Invoice.number, Invoice.due_date,
               (Invoice.total - Invoice.paid_total), Contact.name)
        .join(Contact, Contact.id == Invoice.contact_id, isouter=True)
        .where(Invoice.company_id == cid, Invoice.status.in_(OPEN),
               Invoice.due_date.is_not(None), Invoice.due_date < today,
               (Invoice.total - Invoice.paid_total) > 0)
        .order_by(Invoice.due_date)
        .limit(8)
    )).all()
    overdue = [
        {"number": n, "due_date": str(dd), "customer": cn or "—",
         "outstanding": _s(out), "days_late": (today - dd).days}
        for n, dd, out, cn in od_rows
    ]

    # 3) pelanggan lewat limit kredit
    lim_rows = (await db.execute(
        select(Contact.name, Contact.credit_limit,
               func.coalesce(func.sum(Invoice.total - Invoice.paid_total), 0))
        .join(Invoice, Invoice.contact_id == Contact.id)
        .where(Contact.company_id == cid, Invoice.status.in_(OPEN),
               Contact.credit_limit > 0)
        .group_by(Contact.id, Contact.name, Contact.credit_limit)
    )).all()
    over_limit = [
        {"customer": n, "outstanding": _s(out), "credit_limit": _s(lim)}
        for n, lim, out in lim_rows
        if Decimal(str(out or 0)) > Decimal(str(lim or 0))
    ][:5]

    # ---- faktur terbaru ----
    recent_rows = (await db.execute(
        select(Invoice.number, Invoice.date, Invoice.total, Invoice.status,
               Contact.name)
        .join(Contact, Contact.id == Invoice.contact_id, isouter=True)
        .where(Invoice.company_id == cid)
        .order_by(Invoice.date.desc(), Invoice.number.desc())
        .limit(5)
    )).all()
    recent = [
        {"number": n, "date": str(d), "total": _s(t), "status": st,
         "customer": cn or "—"}
        for n, d, t, st, cn in recent_rows
    ]

    return {
        "period": m0.isoformat(),
        "revenue_month": _s(revenue),
        "revenue_prev_month": _s(revenue_prev),
        "cash_bank": _s(cash_balance),
        "receivable_total": _s(receivable),
        "payable_total": _s(payable),
        "stock_value": _s(stock_value),
        "trend": trend,
        "alerts": {
            "low_stock": low_stock,
            "overdue_invoices": overdue,
            "over_limit": over_limit,
        },
        "recent_invoices": recent,
    }
