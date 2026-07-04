"""Service pembuatan produk.

Master-data murni: TIDAK menyentuh jurnal maupun stok. Dipakai oleh bot
Telegram agar ada satu jalur pembuatan produk yang tervalidasi & bisa diuji.
"""
from decimal import Decimal
from ..models import Product


async def create_product(
    db,
    *,
    company_id: str,
    sku: str,
    name: str,
    kind: str = "good",
    unit: str = "pcs",
    sale_price: Decimal = Decimal("0"),
    purchase_price: Decimal = Decimal("0"),
    min_stock: Decimal = Decimal("0"),
) -> Product:
    product = Product(
        company_id=company_id,
        sku=sku,
        name=name,
        kind=kind,
        unit=unit,
        sale_price=sale_price,
        purchase_price=purchase_price,
        min_stock=min_stock,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product
