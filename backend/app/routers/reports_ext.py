from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import User
from ..deps import current_user
from ..services import reports_ext

router = APIRouter(prefix="/reports", tags=["reports-ext"])


@router.get("/cashflow")
async def cashflow(
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports_ext.cashflow(db, user.company_id, start, end)


@router.get("/ar-limit")
async def ar_limit(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports_ext.ar_limit(db, user.company_id)


@router.get("/commission")
async def commission(
    start: date = Query(...), end: date = Query(...),
    rate: float = Query(0.05, ge=0, le=1),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports_ext.commission(db, user.company_id, start, end, rate)


@router.get("/quarterly-recap")
async def quarterly_recap(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports_ext.quarterly_recap(db, user.company_id)


@router.get("/gpm")
async def gpm(
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await reports_ext.gpm(db, user.company_id, start, end)
