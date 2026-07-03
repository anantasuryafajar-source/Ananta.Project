from ..services.audit_service import write_audit
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Invoice, User, Contact, Warehouse
from ..deps import current_user, require_roles
from ..schemas.invoice import InvoiceIn, InvoiceOut
from ..services.invoice_service import create_and_post_invoice
from ..services.journal import JournalNotBalanced

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
            "quantity": str(l.quantity),
            "unit_price": str(l.unit_price),
            "discount": str(l.discount),
            "tax_rate": str(l.tax_rate),
            "line_total": str(l.line_total),
        } for l in inv.lines],
    }


@router.post("", response_model=InvoiceOut, status_code=201)
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
        )
        await db.commit()
    except JournalNotBalanced as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(invoice)
    return invoice


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
