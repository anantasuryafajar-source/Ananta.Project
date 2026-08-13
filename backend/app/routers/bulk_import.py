"""Import massal master data dari Excel (baris sudah diparse frontend jadi JSON).

- POST /products/import : upsert produk by SKU, atau by nama bila SKU kosong
  (kolom modal dibaca sebagai modal per DUS, sama seperti form & bot)
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
from ..services.product_service import generate_sku
from ..services.units import BASE_UNIT, PACK_UNIT, base_price_from_pack, clean_pack_size

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
            name = str(r.get("name") or "").strip()
            if not name:
                raise ValueError("Kolom name wajib diisi.")
            # SKU opsional: dipakai sebagai kunci upsert bila ada, kalau tidak
            # produk dicocokkan per nama lalu SKU dibuat otomatis.
            sku = str(r.get("sku") or "").strip()
            stmt = select(Product).where(Product.company_id == user.company_id)
            stmt = (stmt.where(Product.sku == sku) if sku
                    else stmt.where(func.lower(Product.name) == name.lower()))
            existing = (await db.execute(stmt)).scalar_one_or_none()

            # Modal di Excel ditulis per DUS (cara client mencatat). Kolom
            # `pack_size` = isi per dus; kosong -> default 12.
            pack_size = clean_pack_size(r.get("pack_size") or r.get("isi_dus"))
            pack_modal = _num(r.get("pack_purchase_price")
                              or r.get("purchase_price"))
            vals = {
                "name": name,
                "unit": str(r.get("unit") or "").strip() or BASE_UNIT,
                "pack_unit": PACK_UNIT,
                "pack_size": pack_size,
                "pack_purchase_price": pack_modal,
                "purchase_price": base_price_from_pack(pack_modal, pack_size),
                "min_stock": _num(r.get("min_stock")),
            }
            if existing:
                for k, v in vals.items():
                    setattr(existing, k, v)
                if sku:
                    existing.sku = sku
                updated += 1
            else:
                db.add(Product(
                    company_id=user.company_id, kind="good",
                    sku=sku or await generate_sku(db, user.company_id, name),
                    **vals))
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
