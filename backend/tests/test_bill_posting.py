from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.models import (
    Company, Warehouse, Contact, Product, StockLevel, Account,
    Journal, JournalEntry,
)
from app.services.purchase_service import create_and_post_bill
from app.services.accounts_map import DEFAULT_CODES


async def _setup(db):
    c = Company(name="T", currency="IDR", costing_method="average")
    db.add(c)
    await db.flush()
    # Buat akun dengan tipe yang benar agar peta akun resolve.
    types = {
        "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
        "vat_out": "liability", "vat_in": "asset", "cash": "asset",
        "bank": "asset", "ap": "liability",
    }
    for key, code in DEFAULT_CODES.items():
        db.add(Account(company_id=c.id, code=code, name=key,
                       type=types[key],
                       normal_balance="credit" if types[key] in ("liability", "income") else "debit"))
    wh = Warehouse(company_id=c.id, code="GD1", name="Utama", is_default=True)
    sup = Contact(company_id=c.id, type="supplier", name="Supplier A", payment_term_days=14)
    p = Product(company_id=c.id, sku="A1", name="Barang A", kind="good",
                sale_price=Decimal("10000"), purchase_price=Decimal("6000"))
    db.add_all([wh, sup, p])
    await db.flush()
    # Stok awal: 10 unit @ 6.000
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=Decimal("10"), avg_cost=Decimal("6000")))
    await db.flush()
    return c, wh, sup, p


async def test_bill_posts_balanced_journal_and_adds_stock(db):
    c, wh, sup, p = await _setup(db)
    # Beli 10 unit @ 8.000 -> average baru = (10*6000 + 10*8000)/20 = 7.000
    bill = await create_and_post_bill(
        db, company_id=c.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": "10", "unit_cost": "8000",
                   "tax_rate": "11"}],
    )
    assert bill.subtotal == Decimal("80000.00")
    assert bill.tax_total == Decimal("8800.00")
    assert bill.total == Decimal("88800.00")

    entries = (await db.execute(
        select(JournalEntry).join(Journal).where(Journal.id == bill.journal_id)
    )).scalars().all()
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)

    lvl = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == p.id)
    )).scalar_one()
    assert Decimal(str(lvl.quantity)) == Decimal("20.0000")
    assert Decimal(str(lvl.avg_cost)) == Decimal("7000.00")
