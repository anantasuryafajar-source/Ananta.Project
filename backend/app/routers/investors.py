from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Investor, InvestorPayout, User
from ..deps import current_user, require_roles
from ..schemas.common import ORMModel
from ..services.investor_service import receive_funds, create_payout
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/investors", tags=["investors"])


class InvestorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scheme: str | None = None
    principal: Decimal = Decimal("0")
    roi_rate: Decimal = Decimal("0")
    start_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvestorOut(ORMModel):
    id: str
    name: str
    scheme: str | None
    principal: Decimal
    received_total: Decimal
    roi_rate: Decimal
    start_date: date | None
    due_date: date | None
    status: str


class FundsIn(BaseModel):
    date: date
    amount: Decimal = Field(gt=0)
    cash_account_code: str = "1-1100"


class PayoutIn(BaseModel):
    date: date
    type: str = Field(pattern="^(dividend|principal)$")
    amount: Decimal = Field(gt=0)
    cash_account_code: str = "1-1100"
    note: str | None = None


class PayoutOut(ORMModel):
    id: str
    investor_id: str
    number: str
    date: date
    type: str
    amount: Decimal


@router.get("", response_model=list[InvestorOut])
async def list_investors(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (select(Investor).where(Investor.company_id == user.company_id)
            .order_by(Investor.name))
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=InvestorOut, status_code=201)
async def create_investor(
    body: InvestorIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    inv = Investor(company_id=user.company_id, **body.model_dump())
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


@router.get("/payouts", response_model=list[PayoutOut])
async def list_payouts(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (select(InvestorPayout)
            .where(InvestorPayout.company_id == user.company_id)
            .order_by(InvestorPayout.date.desc(),
                      InvestorPayout.number.desc()).limit(200))
    return (await db.execute(stmt)).scalars().all()


@router.post("/{investor_id}/receive", response_model=InvestorOut)
async def receive(
    investor_id: str, body: FundsIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        inv = await receive_funds(
            db, company_id=user.company_id, user_id=user.id,
            investor_id=investor_id, on_date=body.date, amount=body.amount,
            cash_account_code=body.cash_account_code,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(inv)
    return inv


@router.post("/{investor_id}/payout", response_model=PayoutOut, status_code=201)
async def payout(
    investor_id: str, body: PayoutIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        p = await create_payout(
            db, company_id=user.company_id, user_id=user.id,
            investor_id=investor_id, on_date=body.date, ptype=body.type,
            amount=body.amount, cash_account_code=body.cash_account_code,
            note=body.note,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(p)
    return p
