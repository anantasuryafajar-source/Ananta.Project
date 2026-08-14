"""Purchase Order & Sales Order: pembuatan + konversi ke Bill/Invoice.

PO dan SO adalah tahap 'pesanan' sebelum barang/uang bergerak. Konversi
memakai service yang sudah teruji:
  - PO -> Bill  via purchase_service.create_and_post_bill (stok masuk + jurnal)
  - SO -> Invoice via invoice_service.create_and_post_invoice (stok keluar + jurnal)
Jadi logika akuntansi tetap satu sumber, tidak diduplikasi.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    PurchaseOrder, POLine, SalesOrder, SOLine, Product, Contact,
)
from .numbering import next_number
from .purchase_service import create_and_post_bill, compute_line
from .invoice_service import create_and_post_invoice
from .units import BASE_UNIT, factor_for, to_base, try_normalize_unit

CENT = Decimal("0.01")


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


async def _prep_lines(db, lines_in: list[dict]):
    """Hitung total per baris + siapkan objek line (dipakai PO & SO).

    Satuan diperlakukan sama seperti di faktur/tagihan: uang dari satuan yang
    dipilih, `quantity` disimpan dalam botol, faktor di-snapshot.
    """
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    prepared = []
    for raw in lines_in:
        qty_input = Decimal(str(raw["quantity"]))
        price = Decimal(str(raw["unit_price"]))
        disc = Decimal(str(raw.get("discount", 0)))
        rate = Decimal(str(raw.get("tax_rate", 0)))
        base, tax = compute_line(qty_input, price, disc, rate)
        subtotal += base
        tax_total += tax

        product = None
        if raw.get("product_id"):
            product = (await db.execute(
                select(Product).where(Product.id == raw["product_id"])
            )).scalar_one_or_none()
        desc = raw.get("description") or (product.name if product else "")

        unit = try_normalize_unit(raw.get("unit")) or BASE_UNIT
        factor = factor_for(unit, product.pack_size if product else 1)

        prepared.append({
            "product_id": raw.get("product_id"), "description": desc or "",
            "quantity": to_base(qty_input, factor), "qty_input": qty_input,
            "unit": unit, "unit_factor": factor,
            "price": price, "discount": disc,
            "tax_rate": rate, "line_total": _q(base + tax),
            "note": (raw.get("note") or None),
        })
    return _q(subtotal), _q(tax_total), prepared


# ============================= PURCHASE ORDER =============================
async def create_purchase_order(
    db, *, company_id, user_id, contact_id, on_date, expected_date,
    warehouse_id, freight_total, freight_supplier_share, notes, lines_in,
) -> PurchaseOrder:
    subtotal, tax_total, prepared = await _prep_lines(db, lines_in)
    number = await next_number(db, company_id=company_id, doc_type="po",
                               on_date=on_date, prefix="PO", reset="monthly")
    po = PurchaseOrder(
        company_id=company_id, number=number, contact_id=contact_id,
        date=on_date, expected_date=expected_date, warehouse_id=warehouse_id,
        status="draft", subtotal=subtotal, tax_total=tax_total,
        total=_q(subtotal + tax_total),
        freight_total=_q(freight_total), freight_supplier_share=_q(freight_supplier_share),
        notes=notes, created_by=user_id,
        lines=[POLine(
            product_id=p["product_id"], description=p["description"],
            quantity=p["quantity"], qty_input=p["qty_input"], unit=p["unit"],
            unit_factor=p["unit_factor"],
            unit_cost=p["price"], discount=p["discount"],
            tax_rate=p["tax_rate"], line_total=p["line_total"],
            note=p["note"],
        ) for p in prepared],
    )
    db.add(po)
    await db.flush()
    return po


async def receive_purchase_order(db, *, company_id, user_id, po_id) -> PurchaseOrder:
    """Konversi PO -> Bill (barang masuk gudang + jurnal utang)."""
    po = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id,
                                    PurchaseOrder.company_id == company_id)
    )).scalar_one()
    if po.status in ("received", "cancelled"):
        raise ValueError(f"PO sudah {po.status}, tidak bisa diterima lagi.")
    # PENTING: kirim jumlah SEPERTI DIKETIK (`qty_input`) + satuannya, bukan
    # `quantity` yang sudah dalam botol — kalau tidak, create_and_post_bill akan
    # mengalikan faktor untuk KEDUA kalinya (1 dus jadi 144 botol).
    lines_in = [{
        "product_id": l.product_id, "description": l.description,
        "quantity": l.qty_input, "unit": l.unit, "unit_cost": l.unit_cost,
        "discount": l.discount, "tax_rate": l.tax_rate,
        # Keterangan ikut terbawa; tanpa ini ia hilang diam-diam saat dikonversi.
        "note": l.note,
    } for l in po.lines]
    bill = await create_and_post_bill(
        db, company_id=company_id, user_id=user_id, contact_id=po.contact_id,
        on_date=po.date, warehouse_id=po.warehouse_id, lines_in=lines_in,
        notes=f"Dari {po.number}",
    )
    po.status = "received"
    po.bill_id = bill.id
    await db.flush()
    return po


# ============================= SALES ORDER =============================
async def create_sales_order(
    db, *, company_id, user_id, contact_id, on_date, warehouse_id,
    courier_name, notes, lines_in,
) -> SalesOrder:
    subtotal, tax_total, prepared = await _prep_lines(db, lines_in)
    number = await next_number(db, company_id=company_id, doc_type="so",
                               on_date=on_date, prefix="SO", reset="monthly")
    so = SalesOrder(
        company_id=company_id, number=number, contact_id=contact_id,
        date=on_date, warehouse_id=warehouse_id, status="draft",
        subtotal=subtotal, tax_total=tax_total, total=_q(subtotal + tax_total),
        courier_name=courier_name, notes=notes, created_by=user_id,
        lines=[SOLine(
            product_id=p["product_id"], description=p["description"],
            quantity=p["quantity"], qty_input=p["qty_input"], unit=p["unit"],
            unit_factor=p["unit_factor"],
            unit_price=p["price"], discount=p["discount"],
            tax_rate=p["tax_rate"], line_total=p["line_total"],
            note=p["note"],
        ) for p in prepared],
    )
    db.add(so)
    await db.flush()
    return so


async def invoice_sales_order(db, *, company_id, user_id, so_id) -> SalesOrder:
    """Konversi SO -> Invoice (stok keluar + jurnal piutang)."""
    so = (await db.execute(
        select(SalesOrder).where(SalesOrder.id == so_id,
                                 SalesOrder.company_id == company_id)
    )).scalar_one()
    if so.status in ("invoiced", "cancelled"):
        raise ValueError(f"SO sudah {so.status}.")
    # Sama seperti PO -> Bill: kirim `qty_input` + satuan, jangan `quantity`.
    lines_in = [{
        "product_id": l.product_id, "description": l.description,
        "quantity": l.qty_input, "unit": l.unit, "unit_price": l.unit_price,
        "discount": l.discount, "tax_rate": l.tax_rate,
        "note": l.note,
    } for l in so.lines]
    invoice = await create_and_post_invoice(
        db, company_id=company_id, user_id=user_id, contact_id=so.contact_id,
        on_date=so.date, warehouse_id=so.warehouse_id, lines_in=lines_in,
        notes=f"Dari {so.number}",
    )
    so.status = "invoiced"
    so.invoice_id = invoice.id
    await db.flush()
    return so
