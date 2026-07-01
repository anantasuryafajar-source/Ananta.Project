from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Warehouse, StockLevel, Product, User
from ..deps import current_user, require_roles
from ..schemas.distribusi import (
    WarehouseIn, WarehouseOut, StockRow, TransferIn, TransferOut,
)
from ..services.transfer_service import transfer_stock, TransferError

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@router.get("", response_model=list[WarehouseOut])
async def list_warehouses(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (select(Warehouse)
            .where(Warehouse.company_id == user.company_id)
            .order_by(Warehouse.is_default.desc(), Warehouse.name))
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=WarehouseOut, status_code=201)
async def create_warehouse(
    body: WarehouseIn,
    user: User = Depends(require_roles("finance", "warehouse")),
    db: AsyncSession = Depends(get_db),
):
    wh = Warehouse(company_id=user.company_id, **body.model_dump())
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.get("/{warehouse_id}/stock", response_model=list[StockRow])
async def warehouse_stock(
    warehouse_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(StockLevel, Product)
        .join(Product, Product.id == StockLevel.product_id)
        .where(StockLevel.warehouse_id == warehouse_id,
               Product.company_id == user.company_id)
        .order_by(Product.name)
    )
    rows = (await db.execute(stmt)).all()
    return [
        StockRow(product_id=p.id, sku=p.sku, name=p.name,
                 warehouse_id=warehouse_id, quantity=lvl.quantity, avg_cost=lvl.avg_cost)
        for lvl, p in rows
    ]


# --- Transfer antar-gudang ---
transfer_router = APIRouter(prefix="/transfers", tags=["transfers"])


@transfer_router.post("", response_model=TransferOut, status_code=201)
async def create_transfer(
    body: TransferIn,
    user: User = Depends(require_roles("warehouse", "finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        moved = await transfer_stock(
            db, company_id=user.company_id,
            from_wh=body.from_warehouse_id, to_wh=body.to_warehouse_id,
            on_date=body.date, lines=[l.model_dump() for l in body.lines],
        )
        await db.commit()
    except TransferError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return TransferOut(moved=moved, from_warehouse_id=body.from_warehouse_id,
                       to_warehouse_id=body.to_warehouse_id)
