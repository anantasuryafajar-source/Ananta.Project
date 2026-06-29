from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Invoice, Bill, StockLevel, Product, User
from ..deps import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    cid = user.company_id
    today = date.today()
    month_start = today.replace(day=1)

    revenue = (await db.execute(
        select(func.coalesce(func.sum(Invoice.subtotal), 0))
        .where(Invoice.company_id == cid,
               Invoice.status.in_(["posted", "paid", "overdue"]),
               Invoice.date >= month_start)
    )).scalar_one()

    receivable = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total - Invoice.paid_total), 0))
        .where(Invoice.company_id == cid,
               Invoice.status.in_(["posted", "overdue"]))
    )).scalar_one()

    payable = (await db.execute(
        select(func.coalesce(func.sum(Bill.total - Bill.paid_total), 0))
        .where(Bill.company_id == cid,
               Bill.status.in_(["posted", "overdue"]))
    )).scalar_one()

    stock_value = (await db.execute(
        select(func.coalesce(func.sum(StockLevel.quantity * StockLevel.avg_cost), 0))
        .join(Product, Product.id == StockLevel.product_id)
        .where(Product.company_id == cid)
    )).scalar_one()

    return {
        "revenue_month": str(Decimal(revenue)),
        "receivable_total": str(Decimal(receivable)),
        "payable_total": str(Decimal(payable)),
        "stock_value": str(Decimal(stock_value)),
        "period": month_start.isoformat(),
    }
