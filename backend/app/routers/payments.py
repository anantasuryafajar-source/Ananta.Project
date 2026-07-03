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


# ============================= LIST & VOID PEMBAYARAN =============================
from sqlalchemy import select
from ..models import PaymentReceived, PaymentMade
from ..deps import current_user
from ..services.payment_void_service import (
    void_payment_received, void_payment_made, PaymentVoidError,
)


@router.get("/received")
async def list_received(
    invoice_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(PaymentReceived)
        .where(PaymentReceived.company_id == user.company_id,
               PaymentReceived.invoice_id == invoice_id)
        .order_by(PaymentReceived.date.desc())
    )).scalars().all()
    return [{"id": p.id, "number": p.number, "date": str(p.date),
             "amount": str(p.amount)} for p in rows]


@router.get("/made")
async def list_made(
    bill_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(PaymentMade)
        .where(PaymentMade.company_id == user.company_id,
               PaymentMade.bill_id == bill_id)
        .order_by(PaymentMade.date.desc())
    )).scalars().all()
    return [{"id": p.id, "number": p.number, "date": str(p.date),
             "amount": str(p.amount)} for p in rows]


@router.post("/received/{payment_id}/void")
async def void_received(
    payment_id: str,
    user: User = Depends(require_roles()),  # owner
    db: AsyncSession = Depends(get_db),
):
    try:
        number = await void_payment_received(
            db, company_id=user.company_id, user_id=user.id,
            payment_id=payment_id)
        await db.commit()
    except PaymentVoidError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return {"ok": True, "voided": number}


@router.post("/made/{payment_id}/void")
async def void_made(
    payment_id: str,
    user: User = Depends(require_roles()),  # owner
    db: AsyncSession = Depends(get_db),
):
    try:
        number = await void_payment_made(
            db, company_id=user.company_id, user_id=user.id,
            payment_id=payment_id)
        await db.commit()
    except PaymentVoidError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return {"ok": True, "voided": number}
