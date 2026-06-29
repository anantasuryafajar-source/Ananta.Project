from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import User
from ..deps import current_user
from ..services import reports

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/profit-loss")
async def profit_loss(
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports.profit_loss(db, user.company_id, start, end)


@router.get("/balance-sheet")
async def balance_sheet(
    as_of: date = Query(default_factory=date.today),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports.balance_sheet(db, user.company_id, as_of)


@router.get("/trial-balance")
async def trial_balance(
    as_of: date = Query(default_factory=date.today),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports.trial_balance(db, user.company_id, as_of)


@router.get("/ar-aging")
async def ar_aging(
    as_of: date = Query(default_factory=date.today),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports.ar_aging(db, user.company_id, as_of)


@router.get("/stock-valuation")
async def stock_valuation(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports.stock_valuation(db, user.company_id)
