from datetime import date
from decimal import Decimal
from app.models import Company, Warehouse, Contact, Product, StockLevel, Account
from app.services.invoice_service import create_and_post_invoice
from app.services.accounts_map import DEFAULT_CODES


async def _setup(db):
    c = Company(name="T", currency="IDR", costing_method="average")
    db.add(c); await db.flush()
    for key, code in DEFAULT_CODES.items():
        db.add(Account(company_id=c.id, code=code, name=key, type="asset",
                       normal_balance="debit"))
    wh = Warehouse(company_id=c.id, code="GD1", name="Utama", is_default=True)
    ct = Contact(company_id=c.id, type="customer", name="Pelanggan A", payment_term_days=14)
    p = Product(company_id=c.id, sku="A1", name="Barang A", kind="good",
                sale_price=Decimal("10000"))
    db.add_all([wh, ct, p]); await db.flush()
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=Decimal("10"), avg_cost=Decimal("6000")))
    await db.flush()
    return c, wh, ct, p


async def test_invoice_posts_balanced_journal_and_cuts_stock(db):
    c, wh, ct, p = await _setup(db)
    inv = await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": "2", "unit_price": "10000",
                   "tax_rate": "11"}],
    )
    # 2 x 10.000 = 20.000 subtotal; PPN 11% = 2.200; total 22.200
    assert inv.subtotal == Decimal("20000.00")
    assert inv.tax_total == Decimal("2200.00")
    assert inv.total == Decimal("22200.00")

    # Jurnal balance
    from app.models import Journal, JournalEntry
    from sqlalchemy import select
    entries = (await db.execute(
        select(JournalEntry).join(Journal).where(Journal.id == inv.journal_id)
    )).scalars().all()
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)

    # Stok berkurang 10 -> 8
    lvl = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == p.id)
    )).scalar_one()
    assert Decimal(str(lvl.quantity)) == Decimal("8")
