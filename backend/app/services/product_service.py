"""Service pembuatan produk.

Master-data murni: TIDAK menyentuh jurnal maupun stok. Dipakai oleh bot
Telegram & router agar ada satu jalur pembuatan produk yang tervalidasi.

Dua hal yang diurus di sini supaya tidak diulang di setiap pemanggil:

1. **SKU dibuat otomatis** dari nama. User tidak pernah mengetiknya, tapi kode
   tetap ada karena dipakai untuk membedakan produk bernama nyaris identik
   (Macallan 12 DC / TC / SO) di bot dan sebagai kunci di laporan & import Excel.
2. **Modal diinput per DUS**, disimpan sekaligus sebagai modal per botol
   (`purchase_price`) yang dipakai laporan margin. Lihat services/units.py.
"""
import re
from decimal import Decimal

from sqlalchemy import func, select

from ..models import Product
from .units import (
    BASE_UNIT,
    PACK_UNIT,
    base_price_from_pack,
    clean_pack_size,
)

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
# Kata umum yang dibuang agar SKU tetap pendek & khas.
_STOPWORDS = {"THE", "DAN", "AND", "OF", "ML", "YO"}
_SKU_MAX = 32  # sisakan ruang untuk sufiks anti-tabrakan (kolom = 40 char)


def slug_sku(name: str) -> str:
    """'Macallan 12 Double Cask' -> 'MACALLAN-12-DOUBLE-CASK'."""
    words = [w for w in _NON_ALNUM.split((name or "").upper()) if w]
    words = [w for w in words if w not in _STOPWORDS] or words
    slug = "-".join(words)[:_SKU_MAX].strip("-")
    return slug or "PRODUK"


async def generate_sku(db, company_id: str, name: str) -> str:
    """SKU unik per perusahaan, diturunkan dari nama produk.

    Bila slug sudah dipakai (mis. dua produk bernama mirip), ditambah sufiks
    angka: MANSION-VODKA, MANSION-VODKA-2, dst.
    """
    base = slug_sku(name)
    taken = set(
        (await db.execute(
            select(func.upper(Product.sku)).where(
                Product.company_id == company_id,
                func.upper(Product.sku).like(f"{base}%"),
            )
        )).scalars().all()
    )
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


async def create_product(
    db,
    *,
    company_id: str,
    name: str,
    sku: str | None = None,
    kind: str = "good",
    unit: str = BASE_UNIT,
    pack_unit: str = PACK_UNIT,
    pack_size=12,
    pack_purchase_price: Decimal = Decimal("0"),
    sale_price: Decimal = Decimal("0"),
    min_stock: Decimal = Decimal("0"),
    commit: bool = True,
) -> Product:
    """Buat produk. `pack_purchase_price` adalah modal per DUS (bukan per botol)."""
    size = clean_pack_size(pack_size)
    pack_modal = Decimal(str(pack_purchase_price or 0))
    product = Product(
        company_id=company_id,
        sku=sku or await generate_sku(db, company_id, name),
        name=name,
        kind=kind,
        unit=unit,
        pack_unit=pack_unit,
        pack_size=size,
        pack_purchase_price=pack_modal,
        purchase_price=base_price_from_pack(pack_modal, size),
        sale_price=sale_price,
        min_stock=min_stock,
    )
    db.add(product)
    if commit:
        await db.commit()
        await db.refresh(product)
    else:
        await db.flush()
    return product
