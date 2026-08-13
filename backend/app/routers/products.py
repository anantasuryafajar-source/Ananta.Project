from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Product, User
from ..deps import current_user, require_roles
from ..schemas.product import ProductIn, ProductOut
from ..services.product_service import create_product as create_product_svc
from ..services.units import base_price_from_pack, clean_pack_size

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
    # Lewat service supaya SKU otomatis & konversi modal dus->botol seragam
    # dengan jalur bot Telegram.
    return await create_product_svc(
        db,
        company_id=user.company_id,
        name=body.name,
        sku=body.sku,
        kind=body.kind,
        unit=body.unit,
        pack_unit=body.pack_unit,
        pack_size=body.pack_size,
        pack_purchase_price=body.pack_purchase_price,
        min_stock=body.min_stock,
    )


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

    data = body.model_dump()
    # SKU tidak diketik user: kosong berarti "pertahankan yang sudah ada".
    new_sku = data.pop("sku", None)
    if new_sku:
        product.sku = new_sku

    size = clean_pack_size(data.pop("pack_size"))
    pack_modal = data.pop("pack_purchase_price")
    for k, v in data.items():
        setattr(product, k, v)

    # Mengubah isi/dus AMAN untuk stok: saldo tersimpan dalam botol dan setiap
    # baris transaksi menyimpan faktornya sendiri, jadi riwayat tidak bergeser.
    product.pack_size = size
    product.pack_purchase_price = pack_modal
    product.purchase_price = base_price_from_pack(pack_modal, size)

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
