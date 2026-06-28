from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Product, User
from ..deps import current_user, require_roles
from ..schemas.product import ProductIn, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(
    q: str | None = Query(None), limit: int = Query(50, le=200),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).where(Product.company_id == user.company_id)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Product.name).limit(limit)
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    body: ProductIn,
    user: User = Depends(require_roles("warehouse", "finance", "sales")),
    db: AsyncSession = Depends(get_db),
):
    product = Product(company_id=user.company_id, **body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product
