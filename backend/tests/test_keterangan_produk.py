"""Keterangan kondisi barang menempel dari PEMBELIAN ke master produk.

Aturannya (dikonfirmasi client):
- keterangan baris pembelian disalin ke produk; yang TERBARU menimpa yang lama;
- keterangan penjualan TIDAK ikut — itu catatan pesanan pelanggan, bukan kondisi
  barang di gudang;
- mengubah/mengosongkan keterangan produk TIDAK menyentuh dokumen pembelian,
  karena dokumen adalah jejak audit.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Account, BillLine, Company, Contact, Product, StockLevel, Warehouse,
)
from app.services.accounts_map import DEFAULT_CODES
from app.services.invoice_service import create_and_post_invoice
from app.services.order_service import create_purchase_order, receive_purchase_order
from app.services.purchase_service import create_and_post_bill

_TYPES = {
    "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
    "vat_out": "liability", "vat_in": "asset", "cash": "asset",
    "bank": "asset", "ap": "liability",
}


async def _setup(db):
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
                      quantity=Decimal("240"), avg_cost=Decimal("75000")))
    await db.flush()
    return company, wh, sup, cust, prod


async def test_keterangan_pembelian_menempel_ke_produk(db):
    company, wh, sup, _, prod = await _setup(db)
    assert prod.note is None

    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_cost": "1800000", "note": "2 botol pecah"}],
    )
    await db.flush()
    assert prod.note == "2 botol pecah"


async def test_pembelian_berikutnya_menimpa_keterangan_lama(db):
    """Pilihan client: yang terbaru menang, supaya kolomnya tetap satu baris."""
    company, wh, sup, _, prod = await _setup(db)

    for keterangan in ("2 botol pecah", "beda batch, cek expired"):
        await create_and_post_bill(
            db, company_id=company.id, user_id=None, contact_id=sup.id,
            on_date=date.today(), warehouse_id=wh.id,
            lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                       "unit_cost": "1800000", "note": keterangan}],
        )
        await db.flush()
    assert prod.note == "beda batch, cek expired"

    # pembelian TANPA keterangan tidak menghapus yang sudah ada
    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_cost": "1800000"}],
    )
    await db.flush()
    assert prod.note == "beda batch, cek expired"


async def test_keterangan_penjualan_tidak_menempel(db):
    company, wh, _, cust, prod = await _setup(db)

    await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=cust.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_price": "2400000", "note": "bonus untuk pelanggan"}],
    )
    await db.flush()
    assert prod.note is None          # kondisi gudang tidak berubah oleh penjualan


async def test_keterangan_dari_po_yang_diterima_ikut_menempel(db):
    """PO -> Terima menghasilkan tagihan, jadi keterangannya ikut menempel."""
    company, wh, sup, _, prod = await _setup(db)

    po = await create_purchase_order(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), expected_date=None, warehouse_id=wh.id,
        freight_total=Decimal("0"), freight_supplier_share=Decimal("0"),
        notes=None,
        lines_in=[{"product_id": prod.id, "quantity": "2", "unit": "dus",
                   "unit_price": "1800000", "note": "segel rusak 1 dus"}],
    )
    await db.flush()
    assert prod.note is None          # PO saja belum menambah stok

    await receive_purchase_order(db, company_id=company.id, user_id=None,
                                po_id=po.id)
    await db.flush()
    assert prod.note == "segel rusak 1 dus"


async def test_mengubah_keterangan_produk_tidak_mengubah_dokumen(db):
    """Dokumen pembelian adalah jejak audit — harus tetap seperti saat dicatat."""
    company, wh, sup, _, prod = await _setup(db)

    bill = await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=sup.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": prod.id, "quantity": "1", "unit": "dus",
                   "unit_cost": "1800000", "note": "2 botol pecah"}],
    )
    await db.flush()

    # user mengedit lalu mengosongkan keterangan di form produk
    prod.note = "sudah diganti supplier"
    await db.flush()
    prod.note = None
    await db.flush()

    baris = (await db.execute(
        select(BillLine).where(BillLine.bill_id == bill.id)
    )).scalars().one()
    assert baris.note == "2 botol pecah"     # dokumen tidak ikut berubah
