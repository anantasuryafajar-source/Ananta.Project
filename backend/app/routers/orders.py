from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import PurchaseOrder, SalesOrder, User
from ..deps import current_user, require_roles
from ..schemas.distribusi import (
    PurchaseOrderIn, PurchaseOrderOut, SalesOrderIn, SalesOrderOut,
)
from ..services.order_service import (
    create_purchase_order, receive_purchase_order,
    create_sales_order, invoice_sales_order,
)
from ..services.journal import JournalNotBalanced

# ============================= PURCHASE ORDERS =============================
po_router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@po_router.get("", response_model=list[PurchaseOrderOut])
async def list_po(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    stmt = (select(PurchaseOrder).where(PurchaseOrder.company_id == user.company_id)
            .order_by(PurchaseOrder.date.desc(), PurchaseOrder.number.desc()).limit(100))
    return (await db.execute(stmt)).scalars().all()


@po_router.post("", response_model=PurchaseOrderOut, status_code=201)
async def create_po(
    body: PurchaseOrderIn,
    user: User = Depends(require_roles("finance", "warehouse")),
    db: AsyncSession = Depends(get_db),
):
    po = await create_purchase_order(
        db, company_id=user.company_id, user_id=user.id, contact_id=body.contact_id,
        on_date=body.date, expected_date=body.expected_date, warehouse_id=body.warehouse_id,
        freight_total=body.freight_total, freight_supplier_share=body.freight_supplier_share,
        notes=body.notes, lines_in=[l.model_dump() for l in body.lines],
    )
    await db.commit()
    await db.refresh(po)
    return po


@po_router.post("/{po_id}/receive", response_model=PurchaseOrderOut)
async def receive_po(
    po_id: str,
    user: User = Depends(require_roles("finance", "warehouse")),
    db: AsyncSession = Depends(get_db),
):
    try:
        po = await receive_purchase_order(db, company_id=user.company_id,
                                          user_id=user.id, po_id=po_id)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(po)
    return po


# ============================= SALES ORDERS =============================
so_router = APIRouter(prefix="/sales-orders", tags=["sales-orders"])


@so_router.get("", response_model=list[SalesOrderOut])
async def list_so(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    stmt = (select(SalesOrder).where(SalesOrder.company_id == user.company_id)
            .order_by(SalesOrder.date.desc(), SalesOrder.number.desc()).limit(100))
    return (await db.execute(stmt)).scalars().all()


@so_router.post("", response_model=SalesOrderOut, status_code=201)
async def create_so(
    body: SalesOrderIn,
    user: User = Depends(require_roles("sales", "finance")),
    db: AsyncSession = Depends(get_db),
):
    so = await create_sales_order(
        db, company_id=user.company_id, user_id=user.id, contact_id=body.contact_id,
        on_date=body.date, warehouse_id=body.warehouse_id, courier_name=body.courier_name,
        notes=body.notes, lines_in=[l.model_dump() for l in body.lines],
    )
    await db.commit()
    await db.refresh(so)
    return so


@so_router.post("/{so_id}/invoice", response_model=SalesOrderOut)
async def invoice_so(
    so_id: str,
    user: User = Depends(require_roles("sales", "finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        so = await invoice_sales_order(db, company_id=user.company_id,
                                       user_id=user.id, so_id=so_id)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(so)
    return so
