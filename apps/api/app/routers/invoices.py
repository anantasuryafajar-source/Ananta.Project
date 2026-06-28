from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Invoice, User
from ..deps import current_user, require_roles
from ..schemas.invoice import InvoiceIn, InvoiceOut
from ..services.invoice_service import create_and_post_invoice
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceOut])
async def list_invoices(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Invoice)
        .where(Invoice.company_id == user.company_id)
        .order_by(Invoice.date.desc(), Invoice.number.desc())
        .limit(100)
    )
    return (await db.execute(stmt)).scalars().all()


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
