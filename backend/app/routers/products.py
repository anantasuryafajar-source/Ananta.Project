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


# ============================= EDIT & HAPUS =============================
from fastapi import HTTPException
from ..models import StockMovement, InvoiceLine, BillLine


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, body: ProductIn,
    user: User = Depends(require_roles("warehouse", "finance", "sales")),
    db: AsyncSession = Depends(get_db),
):
    product = (await db.execute(
        select(Product).where(Product.id == product_id,
                              Product.company_id == user.company_id)
    )).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
    for k, v in body.model_dump().items():
        setattr(product, k, v)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    user: User = Depends(require_roles()),  # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    product = (await db.execute(
        select(Product).where(Product.id == product_id,
                              Product.company_id == user.company_id)
    )).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")

    used_stock = (await db.execute(
        select(StockMovement.id).where(StockMovement.product_id == product_id).limit(1)
    )).scalar_one_or_none()
    used_inv = (await db.execute(
        select(InvoiceLine.id).where(InvoiceLine.product_id == product_id).limit(1)
    )).scalar_one_or_none()
    used_bill = (await db.execute(
        select(BillLine.id).where(BillLine.product_id == product_id).limit(1)
    )).scalar_one_or_none()
    if used_stock or used_inv or used_bill:
        raise HTTPException(
            status_code=422,
            detail="Produk sudah dipakai transaksi/stok — tidak bisa dihapus "
                   "(riwayat harus tetap utuh). Ubah namanya bila perlu.")
    await db.delete(product)
    await db.commit()
    return {"ok": True}
