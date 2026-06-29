from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import User
from ..deps import require_roles
from ..schemas.purchase import PaymentIn, PaymentOut
from ..services.payment_service import receive_payment, pay_bill
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/receive", response_model=PaymentOut, status_code=201)
async def receive(
    body: PaymentIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Terima pelunasan piutang dari customer."""
    if not body.invoice_id:
        raise HTTPException(status_code=422, detail="invoice_id wajib diisi.")
    try:
        pay = await receive_payment(
            db, company_id=user.company_id, user_id=user.id,
            invoice_id=body.invoice_id, on_date=body.date,
            amount=body.amount, cash_account_id=body.cash_account_id,
        )
        await db.commit()
    except (JournalNotBalanced, Exception) as e:
        await db.rollback()
        if isinstance(e, JournalNotBalanced):
            raise HTTPException(status_code=422, detail=str(e))
        raise
    await db.refresh(pay)
    return pay


@router.post("/pay", response_model=PaymentOut, status_code=201)
async def pay(
    body: PaymentIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Bayar utang ke supplier."""
    if not body.bill_id:
        raise HTTPException(status_code=422, detail="bill_id wajib diisi.")
    try:
        pay = await pay_bill(
            db, company_id=user.company_id, user_id=user.id,
            bill_id=body.bill_id, on_date=body.date,
            amount=body.amount, cash_account_id=body.cash_account_id,
        )
        await db.commit()
    except (JournalNotBalanced, Exception) as e:
        await db.rollback()
        if isinstance(e, JournalNotBalanced):
            raise HTTPException(status_code=422, detail=str(e))
        raise
    await db.refresh(pay)
    return pay
