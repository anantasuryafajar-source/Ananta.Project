from decimal import Decimal

from sqlalchemy import select

from app.models import Company, Product
from app.services.product_service import create_product


async def test_create_product_minimal(db):
    c = Company(name="T", currency="IDR")
    db.add(c)
    await db.flush()

    p = await create_product(
        db,
        company_id=c.id,
        sku="MNS-WHK",
        name="Mansion Whisky",
        unit="botol",
        sale_price=Decimal("250000"),
    )

    assert p.id
    assert p.sku == "MNS-WHK"
    assert p.kind == "good"  # default
    assert p.is_active is True  # default model

    got = (
        await db.execute(select(Product).where(Product.id == p.id))
    ).scalar_one()
    assert got.name == "Mansion Whisky"
    assert got.unit == "botol"
    assert got.sale_price == Decimal("250000")
