from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Invoice, User
from ..deps import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    today = date.today()
    month_start = today.replace(day=1)

    revenue = (await db.execute(
        select(func.coalesce(func.sum(Invoice.subtotal), 0))
        .where(Invoice.company_id == user.company_id,
               Invoice.status.in_(["posted", "paid", "overdue"]),
               Invoice.date >= month_start)
    )).scalar_one()

    receivable = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total - Invoice.paid_total), 0))
        .where(Invoice.company_id == user.company_id,
               Invoice.status.in_(["posted", "overdue"]))
    )).scalar_one()

    return {
        "revenue_month": str(Decimal(revenue)),
        "receivable_total": str(Decimal(receivable)),
        "period": month_start.isoformat(),
    }
