"""Pembatalan & hapus permanen dokumen bersatuan CAMPUR (dus + botol).

Void bekerja dari catatan `StockMovement`, yang selalu dalam satuan dasar. Tes
ini memastikan asumsi itu tetap benar setelah satuan dus/botol ditambahkan:
stok harus kembali PERSIS ke posisi semula dan jurnal balik harus seimbang —
bukan mengembalikan "10" padahal yang keluar 240 botol.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Account, Bill, Company, Contact, Invoice, Journal, JournalEntry, Product,
    StockLevel, StockMovement, Warehouse,
)
from app.services.accounts_map import DEFAULT_CODES
from app.services.invoice_service import create_and_post_invoice
from app.services.purchase_service import create_and_post_bill
from app.services.void_service import (
    hard_delete_bill, hard_delete_invoice, void_bill, void_invoice,
)

_TYPES = {
    "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
    "vat_out": "liability", "vat_in": "asset", "cash": "asset",
    "bank": "asset", "ap": "liability",
}


async def _setup(db, *, stock="480", avg_cost="75000"):
    company = Company(name="ASF", currency="IDR", costing_method="average")
    db.add(company)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        kind = _TYPES[key]
        db.add(Account(
            company_id=company.id, code=code, name=key, type=kind,
            normal_balance="credit" if kind in ("liability", "income") else "debit",
        ))
    wh = Warehouse(company_id=company.id, code="GD1", name="Utama", is_default=True)
    sup = Contact(company_id=company.id, type="supplier", name="EXA",
                  payment_term_days=14)
    cust = Contact(company_id=company.id, type="customer", name="Regar",
                   payment_term_days=30)
    prod = Product(company_id=company.id, sku="CHIVAS-200ML", name="Chivas 200ml",
                   kind="good", unit="botol", pack_unit="dus", pack_size=24,
                   pack_purchase_price=Decimal("1800000"),
                   purchase_price=Decimal("75000"))
    db.add_all([wh, sup, cust, prod])
    await db.flush()
    db.add(StockLevel(product_id=prod.id, warehouse_id=wh.id,
                      quantity=Decimal(stock), avg_cost=Decimal(avg_cost)))
    await db.flush()
    return company, wh, sup, cust, prod


async def _stok(db, product_id) -> Decimal:
    return Decimal(str((await db.execute(
        select(StockLevel.quantity).where(StockLevel.product_id == product_id)
    )).scalar_one()))


async def _semua_jurnal_balance(db) -> bool:
    rows = (await db.execute(
        select(JournalEntry.journal_id, JournalEntry.debit, JournalEntry.credit)
    )).all()
    per_jurnal: dict[str, Decimal] = {}
    for jid, d, c in rows:
        per_jurnal[jid] = (per_jurnal.get(jid, Decimal("0"))
                           + Decimal(str(d)) - Decimal(str(c)))
    return all(v == 0 for v in per_jurnal.values())


async def test_void_faktur_campur_mengembalikan_stok_persis(db):
    company, wh, _, cust, prod = await _setup(db)
    awal = await _stok(db, prod.id)

    invoice = await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=cust.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[
            {"product_id": prod.id, "quantity": "10", "unit": "dus",
             "unit_price": "2400000"},
            {"product_id": prod.id, "quantity": "5", "unit": "botol",
             "unit_price": "110000"},
        ],
    )
    await db.flush()
    assert await _stok(db, prod.id) == awal - Decimal("245")   # 240 + 5

    await void_invoice(db, company_id=company.id, user_id=None,
                       invoice_id=invoice.id)
    await db.flush()

    assert await _stok(db, prod.id) == awal          # kembali PERSIS
    assert invoice.status == "void"
    assert await _semua_jurnal_balance(db)

    # jurnal asli + jurnal balik -> dampak bersih ke akun HPP nol
    cogs_id = (await db.execute(
        select(Account.id).where(Account.company_id == company.id,
                                Account.code == DEFAULT_CODES["cogs"])
    )).scalar_one()
    rows = (await db.execute(
        select(JournalEntry.debit, JournalEntry.credit)
        .where(JournalEntry.account_id == cogs_id)
    )).all()
    netto = sum((Decimal(str(d)) - Decimal(str(c)) for d, c in rows), Decimal("0"))
    assert netto == 0


async def test_void_tagihan_campur_menarik_stok_persis(db):
    company, wh, sup, _, prod = await _setup(db, stock="0", avg_cost="0")

    bill = await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[
            {"product_id": prod.id, "quantity": "10", "unit": "dus",
             "unit_cost": "1800000"},
            {"product_id": prod.id, "quantity": "5", "unit": "botol",
             "unit_cost": "80000"},
        ],
    )
    await db.flush()
    assert await _stok(db, prod.id) == Decimal("245")

    await void_bill(db, company_id=company.id, user_id=None, bill_id=bill.id)
    await db.flush()

    assert await _stok(db, prod.id) == Decimal("0")   # ditarik kembali penuh
    assert bill.status == "void"
    assert await _semua_jurnal_balance(db)


async def test_hapus_permanen_membersihkan_stok_dan_jurnal(db):
    """Dipakai untuk data uji: dokumen, jurnal, dan mutasi stok hilang total."""
    company, wh, sup, cust, prod = await _setup(db)
    awal = await _stok(db, prod.id)

    bill = await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": prod.id, "quantity": "2", "unit": "dus",
                   "unit_cost": "1800000"}],
    )
    invoice = await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=cust.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_price": "2400000"}],
    )
    await db.flush()

    await hard_delete_invoice(db, company_id=company.id, invoice_id=invoice.id)
    await hard_delete_bill(db, company_id=company.id, bill_id=bill.id)
    await db.flush()

    assert await _stok(db, prod.id) == awal
    assert (await db.execute(select(Invoice))).scalars().all() == []
    assert (await db.execute(select(Bill))).scalars().all() == []
    assert (await db.execute(select(Journal))).scalars().all() == []
    assert (await db.execute(select(StockMovement))).scalars().all() == []
