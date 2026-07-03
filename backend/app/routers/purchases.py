from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Bill, User
from ..deps import current_user, require_roles
from ..schemas.purchase import BillIn, BillOut
from ..services.purchase_service import create_and_post_bill
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/bills", tags=["purchases"])


@router.get("", response_model=list[BillOut])
async def list_bills(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Bill)
        .where(Bill.company_id == user.company_id)
        .order_by(Bill.date.desc(), Bill.number.desc())
        .limit(100)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=BillOut, status_code=201)
async def create_bill(
    body: BillIn,
    user: User = Depends(require_roles("warehouse", "finance")),
    db: AsyncSession = Depends(get_db),
):
    """Catat pengadaan: jurnal otomatis + stok masuk + update average cost — atomik."""
    try:
        bill = await create_and_post_bill(
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
    await db.refresh(bill)
    return bill


@router.post("/{bill_id}/void")
async def void_bill_endpoint(
    bill_id: str,
    user: User = Depends(require_roles()),  # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    from ..services.void_service import void_bill, VoidError
    try:
        bill = await void_bill(db, company_id=user.company_id,
                               user_id=user.id, bill_id=bill_id)
        await db.commit()
    except (VoidError, JournalNotBalanced) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return {"ok": True, "status": bill.status}


@router.delete("/{bill_id}/hard")
async def hard_delete_bill_endpoint(
    bill_id: str,
    user: User = Depends(require_roles()),  # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    from ..services.void_service import hard_delete_bill, VoidError
    try:
        number = await hard_delete_bill(db, company_id=user.company_id,
                                        bill_id=bill_id)
        await db.commit()
    except VoidError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return {"ok": True, "deleted": number}
