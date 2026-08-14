"""Transaksi barang TIDAK boleh melewati stok diam-diam.

Dulu `warehouse_id` boleh kosong dan langkah stok dilewati tanpa suara, padahal
jurnalnya tetap terbentuk:

- Pembelian: Persediaan didebit tapi stok tidak bertambah -> neraca dan gudang
  bercerita berbeda, dan valuasi stok tidak akan pernah cocok.
- Penjualan: omzet dicatat TANPA HPP sama sekali -> laba terlihat jauh lebih
  besar dari kenyataan.

Form Pembelian & Penjualan di web memang tidak pernah mengirim gudang, jadi
kedua jalur itu salah sejak lama. Sekarang gudang default dipakai bila tidak
disebut, dan ketiadaan gudang gagal dengan pesan jelas.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    Account, Company, Contact, JournalEntry, Product, StockLevel, Warehouse,
)
from app.services.accounts_map import DEFAULT_CODES
from app.services.invoice_service import create_and_post_invoice
from app.services.purchase_service import create_and_post_bill
from app.services.units import NoWarehouse

_TYPES = {
    "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
    "vat_out": "liability", "vat_in": "asset", "cash": "asset",
    "bank": "asset", "ap": "liability",
}


async def _setup(db, *, dengan_gudang=True):
    company = Company(name="ASF", currency="IDR", costing_method="average")
    db.add(company)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        kind = _TYPES[key]
        db.add(Account(
            company_id=company.id, code=code, name=key, type=kind,
            normal_balance="credit" if kind in ("liability", "income") else "debit",
        ))
    sup = Contact(company_id=company.id, type="supplier", name="EXA",
                  payment_term_days=14)
    cust = Contact(company_id=company.id, type="customer", name="Regar",
                   payment_term_days=30)
    prod = Product(company_id=company.id, sku="CHIVAS-200ML", name="Chivas 200ml",
                   kind="good", unit="botol", pack_unit="dus", pack_size=24,
                   pack_purchase_price=Decimal("1800000"),
                   purchase_price=Decimal("75000"))
    db.add_all([sup, cust, prod])
    if dengan_gudang:
        # sengaja dua gudang: yang default harus yang dipilih
        db.add(Warehouse(company_id=company.id, code="GD2", name="Cadangan",
                         is_default=False))
        db.add(Warehouse(company_id=company.id, code="GD1", name="Utama",
                         is_default=True))
    await db.flush()
    return company, sup, cust, prod


async def test_pembelian_tanpa_gudang_tetap_menambah_stok(db):
    """Inilah yang dilaporkan client: pembelian lewat web tidak mengisi stok."""
    company, sup, _, prod = await _setup(db)

    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=None,          # form web dulu begini
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_cost": "1800000"}],
    )
    await db.flush()

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == prod.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("24")

    # stok mendarat di gudang DEFAULT, bukan sembarang gudang
    wh = (await db.execute(
        select(Warehouse).where(Warehouse.id == level.warehouse_id)
    )).scalar_one()
    assert wh.is_default is True


async def test_penjualan_tanpa_gudang_tetap_memposting_hpp(db):
    """Tanpa HPP, laba terlihat 100% — ini yang paling berbahaya."""
    company, sup, cust, prod = await _setup(db)
    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=None,
        lines_in=[{"product_id": prod.id, "quantity": "2", "unit": "dus",
                   "unit_cost": "1800000"}],
    )
    await db.flush()

    await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=cust.id,
        on_date=date.today(), warehouse_id=None,          # form web dulu begini
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_price": "2400000"}],
    )
    await db.flush()

    cogs_id = (await db.execute(
        select(Account.id).where(Account.company_id == company.id,
                                Account.code == DEFAULT_CODES["cogs"])
    )).scalar_one()
    hpp = sum(
        (Decimal(str(d)) for d, in (await db.execute(
            select(JournalEntry.debit).where(JournalEntry.account_id == cogs_id)
        )).all()),
        Decimal("0"),
    )
    assert hpp == Decimal("1800000.00")     # 24 botol x 75.000, bukan nol

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == prod.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("24")   # 48 - 24


async def test_tanpa_gudang_sama_sekali_ditolak_dengan_pesan_jelas(db):
    company, sup, _, prod = await _setup(db, dengan_gudang=False)

    with pytest.raises(NoWarehouse) as err:
        await create_and_post_bill(
            db, company_id=company.id, user_id=None, contact_id=sup.id,
            on_date=date.today(), warehouse_id=None,
            lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                       "unit_cost": "1800000"}],
        )
    assert "gudang" in str(err.value).lower()
