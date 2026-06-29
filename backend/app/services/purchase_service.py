"""Posting tagihan pembelian (Bill): jurnal otomatis + stok MASUK.

Cermin dari invoice_service, tetapi arah sebaliknya. Semua dalam SATU transaksi
DB (atomik) — bila gagal, caller (router) rollback.

Jurnal pembelian (barang):
    Dr  Persediaan Barang        subtotal (harga modal)
    Dr  PPN Masukan              tax_total
        Cr  Utang Usaha                 total

Stok masuk memakai metode AVERAGE: avg_cost baru dihitung tertimbang
    avg_baru = (qty_lama * avg_lama + qty_masuk * cost_masuk) / (qty_lama + qty_masuk)
Inilah yang membuat HPP di faktur penjualan menjadi benar.
"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Bill, BillLine, Product, StockLevel, StockMovement, Contact,
)
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import code_to_id

CENT = Decimal("0.01")
QTYQ = Decimal("0.0001")


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


def compute_line(qty: Decimal, cost: Decimal, discount: Decimal, tax_rate: Decimal):
    base = _q(Decimal(qty) * Decimal(cost) - Decimal(discount))
    tax = _q(base * Decimal(tax_rate) / Decimal(100))
    return base, tax


async def create_and_post_bill(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    contact_id: str, on_date: date, warehouse_id: str | None,
    lines_in: list[dict], notes: str | None = None,
) -> Bill:
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id,
                              Contact.company_id == company_id)
    )).scalar_one()

    acc = await code_to_id(db, company_id)
    number = await next_number(
        db, company_id=company_id, doc_type="bill", on_date=on_date,
        prefix="BILL", reset="monthly",
    )

    subtotal = Decimal("0")
    tax_total = Decimal("0")
    bill_lines: list[BillLine] = []
    stock_ops: list[tuple[Product, Decimal, Decimal]] = []  # (product, qty, unit_cost)

    for raw in lines_in:
        qty = Decimal(str(raw["quantity"]))
        cost = Decimal(str(raw["unit_cost"]))
        discount = Decimal(str(raw.get("discount", 0)))
        tax_rate = Decimal(str(raw.get("tax_rate", 0)))
        base, tax = compute_line(qty, cost, discount, tax_rate)
        subtotal += base
        tax_total += tax

        product = None
        if raw.get("product_id"):
            product = (await db.execute(
                select(Product).where(Product.id == raw["product_id"])
            )).scalar_one()

        bill_lines.append(BillLine(
            product_id=raw.get("product_id"),
            description=raw.get("description") or (product.name if product else ""),
            quantity=qty, unit_cost=cost, discount=discount,
            tax_rate=tax_rate, line_total=_q(base + tax),
        ))

        if product and product.kind == "good" and warehouse_id:
            # cost per unit setelah diskon baris (untuk valuasi rata-rata)
            eff_cost = base / qty if qty else Decimal("0")
            stock_ops.append((product, qty, _q(eff_cost)))

    subtotal, tax_total = _q(subtotal), _q(tax_total)
    total = _q(subtotal + tax_total)

    bill = Bill(
        company_id=company_id, number=number, contact_id=contact_id,
        date=on_date,
        due_date=on_date + timedelta(days=contact.payment_term_days or 0),
        warehouse_id=warehouse_id, status="posted",
        subtotal=subtotal, tax_total=tax_total, total=total, paid_total=0,
        notes=notes, created_by=user_id, lines=bill_lines,
    )
    db.add(bill)
    await db.flush()

    # --- Jurnal pembelian ---
    j_lines: list[Line] = []
    if subtotal > 0:
        j_lines.append(Line(acc["inventory"], debit=subtotal, description="Persediaan masuk"))
    if tax_total > 0:
        j_lines.append(Line(acc["vat_in"], debit=tax_total, description="PPN Masukan"))
    j_lines.append(Line(acc["ap"], credit=total, description="Utang pembelian"))

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("BILL", "JV"),
        on_date=on_date, lines=j_lines,
        memo=f"Pembelian {number}", source_type="bill", source_id=bill.id,
        created_by=user_id,
    )
    bill.journal_id = journal.id

    # --- Stok masuk + perbarui average cost ---
    for product, qty, unit_cost in stock_ops:
        level = (await db.execute(
            select(StockLevel).where(
                StockLevel.product_id == product.id,
                StockLevel.warehouse_id == warehouse_id,
            )
        )).scalar_one_or_none()
        if level is None:
            level = StockLevel(product_id=product.id, warehouse_id=warehouse_id,
                               quantity=Decimal("0"), avg_cost=unit_cost)
            db.add(level)
            await db.flush()

        old_qty = Decimal(str(level.quantity))
        old_avg = Decimal(str(level.avg_cost))
        new_qty = old_qty + qty
        if new_qty > 0:
            new_avg = (old_qty * old_avg + qty * unit_cost) / new_qty
        else:
            new_avg = unit_cost
        level.quantity = new_qty.quantize(QTYQ)
        level.avg_cost = _q(new_avg)

        db.add(StockMovement(
            company_id=company_id, product_id=product.id,
            warehouse_id=warehouse_id, direction="in", quantity=qty,
            unit_cost=unit_cost, ref_type="bill", ref_id=bill.id,
        ))

    await db.flush()
    return bill
