"""Posting faktur penjualan: hitung total, jurnal otomatis, potong stok.

Semua dijalankan dalam SATU transaksi DB (atomik). Bila ada langkah gagal,
seluruh operasi di-rollback oleh caller (router) — faktur tidak setengah jadi.

Jurnal penjualan (barang):
    Dr  Piutang Usaha            total
        Cr  Pendapatan Penjualan        subtotal
        Cr  PPN Keluaran                tax_total
    Dr  HPP                      cost
        Cr  Persediaan                  cost
"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Invoice, InvoiceLine, Product, StockLevel, StockMovement, Contact,
)
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import code_to_id

CENT = Decimal("0.01")


def _q(v) -> Decimal:
    return Decimal(v).quantize(CENT)


def compute_line(qty: Decimal, price: Decimal, discount: Decimal, tax_rate: Decimal):
    base = _q(Decimal(qty) * Decimal(price) - Decimal(discount))
    tax = _q(base * Decimal(tax_rate) / Decimal(100))
    return base, tax


async def create_and_post_invoice(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    contact_id: str, on_date: date, warehouse_id: str | None,
    lines_in: list[dict], notes: str | None = None,
) -> Invoice:
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id,
                              Contact.company_id == company_id)
    )).scalar_one()

    acc = await code_to_id(db, company_id)
    number = await next_number(
        db, company_id=company_id, doc_type="invoice", on_date=on_date,
        prefix="INV", reset="monthly",
    )

    subtotal = Decimal("0")
    tax_total = Decimal("0")
    cogs_total = Decimal("0")
    inv_lines: list[InvoiceLine] = []
    stock_ops: list[tuple[Product, Decimal, Decimal]] = []  # (product, qty, unit_cost)

    for raw in lines_in:
        qty = Decimal(str(raw["quantity"]))
        price = Decimal(str(raw["unit_price"]))
        discount = Decimal(str(raw.get("discount", 0)))
        tax_rate = Decimal(str(raw.get("tax_rate", 0)))
        base, tax = compute_line(qty, price, discount, tax_rate)
        subtotal += base
        tax_total += tax

        product = None
        if raw.get("product_id"):
            product = (await db.execute(
                select(Product).where(Product.id == raw["product_id"])
            )).scalar_one()

        inv_lines.append(InvoiceLine(
            product_id=raw.get("product_id"),
            description=raw.get("description") or (product.name if product else ""),
            quantity=qty, unit_price=price, discount=discount,
            tax_rate=tax_rate, line_total=_q(base + tax),
        ))

        # Potong stok hanya untuk barang (good), bukan jasa
        if product and product.kind == "good" and warehouse_id:
            level = (await db.execute(
                select(StockLevel).where(
                    StockLevel.product_id == product.id,
                    StockLevel.warehouse_id == warehouse_id,
                )
            )).scalar_one_or_none()
            unit_cost = Decimal(str(level.avg_cost)) if level else Decimal("0")
            cogs_total += _q(unit_cost * qty)
            stock_ops.append((product, qty, unit_cost))

    subtotal, tax_total = _q(subtotal), _q(tax_total)
    total = _q(subtotal + tax_total)

    invoice = Invoice(
        company_id=company_id, number=number, contact_id=contact_id,
        date=on_date,
        due_date=on_date + timedelta(days=contact.payment_term_days or 0),
        warehouse_id=warehouse_id, status="posted",
        subtotal=subtotal, tax_total=tax_total, total=total, paid_total=0,
        notes=notes, created_by=user_id, lines=inv_lines,
    )
    db.add(invoice)
    await db.flush()

    # --- Jurnal pendapatan ---
    j_lines = [Line(acc["ar"], debit=total, description="Piutang faktur")]
    if subtotal > 0:
        j_lines.append(Line(acc["sales"], credit=subtotal, description="Pendapatan"))
    if tax_total > 0:
        j_lines.append(Line(acc["vat_out"], credit=tax_total, description="PPN Keluaran"))

    # --- Jurnal HPP (jika ada barang) ---
    if cogs_total > 0:
        j_lines.append(Line(acc["cogs"], debit=cogs_total, description="HPP"))
        j_lines.append(Line(acc["inventory"], credit=cogs_total, description="Persediaan keluar"))

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("INV", "JV"),
        on_date=on_date, lines=j_lines,
        memo=f"Faktur {number}", source_type="invoice", source_id=invoice.id,
        created_by=user_id,
    )
    invoice.journal_id = journal.id

    # --- Mutasi & saldo stok ---
    for product, qty, unit_cost in stock_ops:
        level = (await db.execute(
            select(StockLevel).where(
                StockLevel.product_id == product.id,
                StockLevel.warehouse_id == warehouse_id,
            )
        )).scalar_one_or_none()
        if level:
            level.quantity = Decimal(str(level.quantity)) - qty
        db.add(StockMovement(
            company_id=company_id, product_id=product.id,
            warehouse_id=warehouse_id, direction="out", quantity=qty,
            unit_cost=unit_cost, ref_type="invoice", ref_id=invoice.id,
        ))

    await db.flush()
    return invoice
