from ..services.audit_service import write_audit
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Invoice, InvoiceLine, User, Contact, Warehouse
from ..deps import current_user, require_roles
from ..schemas.invoice import InvoiceCreatedOut, InvoiceIn, InvoiceOut
from ..services.invoice_service import create_and_post_invoice
from ..services.journal import JournalNotBalanced
from ..services.units import NoWarehouse

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceOut])
async def list_invoices(
    q: str | None = Query(default=None, description="cari nomor faktur"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Invoice)
        .where(Invoice.company_id == user.company_id)
        .order_by(Invoice.date.desc(), Invoice.number.desc())
    )
    if q:
        stmt = stmt.where(Invoice.number.ilike(f"%{q.strip()}%"))
    stmt = stmt.offset(offset).limit(limit)
    return (await db.execute(stmt)).scalars().all()


@router.get("/last-prices")
async def last_prices(
    contact_id: str = Query(..., description="customer yang mau dibuatkan faktur"),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Harga jual TERAKHIR untuk customer ini, per produk & satuan.

    Harga jual tidak disimpan di master produk karena berbeda tiap customer dan
    dinegosiasi per transaksi. Endpoint ini menggantikan peran "harga acuan":
    form penjualan memakainya sebagai nilai awal, sales tetap bisa mengubah.
    """
    rows = (await db.execute(
        select(InvoiceLine.product_id, InvoiceLine.unit,
               InvoiceLine.unit_price, Invoice.date)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(Invoice.company_id == user.company_id,
               Invoice.contact_id == contact_id,
               Invoice.status.in_(("posted", "paid", "overdue")),
               InvoiceLine.product_id.isnot(None))
        .order_by(Invoice.date.desc(), Invoice.created_at.desc())
    )).all()

    # Ambil yang paling baru per (produk, satuan) — hasil sudah terurut menurun.
    seen: dict[tuple[str, str], dict] = {}
    for product_id, unit, price, on_date in rows:
        key = (product_id, unit)
        if key not in seen:
            seen[key] = {"product_id": product_id, "unit": unit,
                         "unit_price": str(price), "date": on_date.isoformat()}
    return list(seen.values())


@router.get("/{invoice_id}/detail")
async def invoice_detail(
    invoice_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Detail lengkap untuk cetak faktur / surat jalan."""
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id,
                              Invoice.company_id == user.company_id)
    )).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Faktur tidak ditemukan.")

    contact = (await db.execute(
        select(Contact).where(Contact.id == inv.contact_id)
    )).scalar_one_or_none()
    wh_name = None
    if inv.warehouse_id:
        wh_name = (await db.execute(
            select(Warehouse.name).where(Warehouse.id == inv.warehouse_id)
        )).scalar_one_or_none()

    return {
        "id": inv.id, "number": inv.number, "date": str(inv.date),
        "due_date": str(inv.due_date) if inv.due_date else None,
        "status": inv.status, "notes": inv.notes,
        "subtotal": str(inv.subtotal), "tax_total": str(inv.tax_total),
        "total": str(inv.total), "paid_total": str(inv.paid_total),
        "warehouse": wh_name,
        "contact": {
            "name": contact.name if contact else "—",
            "address": contact.address if contact else None,
            "phone": contact.phone if contact else None,
            "npwp": contact.npwp if contact else None,
        },
        "lines": [{
            "description": l.description,
            # quantity = botol (satuan dasar); qty_input & unit dipakai cetakan
            # supaya faktur menampilkan "1 dus" & "5 botol" terpisah.
            "quantity": str(l.quantity),
            "qty_input": str(l.qty_input),
            "unit": l.unit,
            "unit_price": str(l.unit_price),
            "note": l.note,
            "discount": str(l.discount),
            "tax_rate": str(l.tax_rate),
            "line_total": str(l.line_total),
        } for l in inv.lines],
    }


@router.post("", response_model=InvoiceCreatedOut, status_code=201)
async def create_invoice(
    body: InvoiceIn,
    user: User = Depends(require_roles("sales", "finance")),
    db: AsyncSession = Depends(get_db),
):
    """Terbitkan faktur: hitung total, jurnal otomatis, potong stok — atomik."""
    try:
        invoice = await create_and_post_invoice(
            db, company_id=user.company_id, user_id=user.id,
            contact_id=body.contact_id, on_date=body.date,
            warehouse_id=body.warehouse_id,
            lines_in=[l.model_dump() for l in body.lines], notes=body.notes,
            terms=[t.model_dump() for t in body.terms] if body.terms else None,
        )
        await db.commit()
    except (JournalNotBalanced, NoWarehouse) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    warnings = getattr(invoice, "stock_warnings", [])
    await db.refresh(invoice)
    data = {
        "id": invoice.id, "number": invoice.number,
        "status": invoice.status, "stock_warnings": warnings,
    }
    return data


@router.post("/{invoice_id}/void")
async def void_invoice_endpoint(
    invoice_id: str,
    user: User = Depends(require_roles()),  # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    from ..services.void_service import void_invoice, VoidError
    try:
        inv = await void_invoice(db, company_id=user.company_id,
                                 user_id=user.id, invoice_id=invoice_id)
        await write_audit(db, company_id=user.company_id, user_id=user.id, action="void_invoice", entity="invoice", entity_id=invoice_id)
        await db.commit()
    except (VoidError, JournalNotBalanced) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return {"ok": True, "status": inv.status}


@router.delete("/{invoice_id}/hard")
async def hard_delete_invoice_endpoint(
    invoice_id: str,
    user: User = Depends(require_roles()),  # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    """HAPUS PERMANEN (untuk data uji): dokumen, jurnal, pembayaran, dan
    mutasi stok dihapus total; stok dikembalikan."""
    from ..services.void_service import hard_delete_invoice, VoidError
    try:
        number = await hard_delete_invoice(db, company_id=user.company_id,
                                           invoice_id=invoice_id)
        await write_audit(db, company_id=user.company_id, user_id=user.id, action="hard_delete_invoice", entity="invoice", entity_id=invoice_id)
        await db.commit()
    except VoidError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return {"ok": True, "deleted": number}
