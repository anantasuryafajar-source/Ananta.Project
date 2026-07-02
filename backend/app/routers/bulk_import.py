"""Import massal master data dari Excel (baris sudah diparse frontend jadi JSON).

- POST /products/import : upsert produk by SKU (baru dibuat, lama diperbarui)
- POST /contacts/import : upsert kontak by nama (case-insensitive)

Baris gagal dilaporkan per-baris; baris lain tetap diproses.
"""
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Product, Contact, User
from ..deps import require_roles

router = APIRouter(tags=["bulk-import"])


def _num(v, default="0") -> Decimal:
    if v is None or str(v).strip() == "":
        return Decimal(default)
    s = str(v).replace("Rp", "").replace(" ", "").strip()
    try:
        return Decimal(s.replace(",", ""))            # 1,250,000 / 1250000.5
    except InvalidOperation:
        try:
            return Decimal(s.replace(".", "").replace(",", "."))  # 1.250.000,50
        except InvalidOperation:
            raise ValueError(f"Angka tidak valid: {v}")


class RowsIn(BaseModel):
    rows: list[dict]


@router.post("/products/import")
async def import_products(
    body: RowsIn,
    user: User = Depends(require_roles("finance", "warehouse")),
    db: AsyncSession = Depends(get_db),
):
    created = updated = 0
    failed: list[dict] = []
    for i, r in enumerate(body.rows, start=1):
        try:
            sku = str(r.get("sku") or "").strip()
            name = str(r.get("name") or "").strip()
            if not sku or not name:
                raise ValueError("Kolom sku dan name wajib diisi.")
            existing = (await db.execute(
                select(Product).where(Product.company_id == user.company_id,
                                      Product.sku == sku)
            )).scalar_one_or_none()
            vals = {
                "name": name,
                "unit": str(r.get("unit") or "").strip() or "pcs",
                "sale_price": _num(r.get("sale_price")),
                "purchase_price": _num(r.get("purchase_price")),
                "min_stock": _num(r.get("min_stock")),
            }
            if existing:
                for k, v in vals.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Product(company_id=user.company_id, sku=sku,
                               kind="good", **vals))
                created += 1
            await db.commit()
        except Exception as e:
            await db.rollback()
            failed.append({"row": i, "reason": str(e)})
    return {"created": created, "updated": updated, "failed": failed}


@router.post("/contacts/import")
async def import_contacts(
    body: RowsIn,
    user: User = Depends(require_roles("finance", "sales")),
    db: AsyncSession = Depends(get_db),
):
    created = updated = 0
    failed: list[dict] = []
    VALID_TYPE = {"customer", "supplier", "both"}
    for i, r in enumerate(body.rows, start=1):
        try:
            name = str(r.get("name") or "").strip()
            if not name:
                raise ValueError("Kolom name wajib diisi.")
            ctype = str(r.get("type") or "customer").strip().lower()
            if ctype not in VALID_TYPE:
                ctype = "customer"
            existing = (await db.execute(
                select(Contact).where(
                    Contact.company_id == user.company_id,
                    func.lower(Contact.name) == name.lower())
            )).scalar_one_or_none()
            vals = {
                "type": ctype,
                "phone": (str(r.get("phone") or "").strip() or None),
                "email": (str(r.get("email") or "").strip() or None),
                "address": (str(r.get("address") or "").strip() or None),
                "npwp": (str(r.get("npwp") or "").strip() or None),
                "credit_limit": _num(r.get("credit_limit")),
            }
            if existing:
                for k, v in vals.items():
                    if v is not None:
                        setattr(existing, k, v)
                updated += 1
            else:
                db.add(Contact(company_id=user.company_id, name=name,
                               payment_term_days=30, **vals))
                created += 1
            await db.commit()
        except Exception as e:
            await db.rollback()
            failed.append({"row": i, "reason": str(e)})
    return {"created": created, "updated": updated, "failed": failed}
