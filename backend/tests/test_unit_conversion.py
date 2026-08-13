"""Tes konversi satuan dus <-> botol.

Ini invarian paling rawan di sistem: `avg_cost` HARUS per botol walau supplier
menagih per dus. Kalau tes di file ini gagal, HPP dan valuasi persediaan salah
12-48x dan koreksinya harus lewat jurnal manual (HPP sudah terposting).
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Account, Company, Contact, Journal, JournalEntry, Product, StockLevel,
    Warehouse,
)
from app.services.accounts_map import DEFAULT_CODES
from app.services.invoice_service import create_and_post_invoice
from app.services.order_service import create_purchase_order, receive_purchase_order
from app.services.purchase_service import create_and_post_bill
from app.services.units import (
    UnitError,
    base_price_from_pack,
    factor_for,
    format_qty,
    normalize_unit,
)

_TYPES = {
    "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
    "vat_out": "liability", "vat_in": "asset", "cash": "asset",
    "bank": "asset", "ap": "liability",
}


async def _setup(db, *, pack_size: int = 12, stock: str = "0",
                avg_cost: str = "0"):
    company = Company(name="ASF Test", currency="IDR", costing_method="average")
    db.add(company)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        kind = _TYPES[key]
        db.add(Account(
            company_id=company.id, code=code, name=key, type=kind,
            normal_balance="credit" if kind in ("liability", "income") else "debit",
        ))
    wh = Warehouse(company_id=company.id, code="GD1", name="Utama", is_default=True)
    supplier = Contact(company_id=company.id, type="supplier", name="EXA",
                       payment_term_days=14)
    customer = Contact(company_id=company.id, type="customer", name="Pak Regar",
                       payment_term_days=30)
    product = Product(
        company_id=company.id, sku="CHIVAS-200ML", name="Chivas 200ml",
        kind="good", unit="botol", pack_unit="dus", pack_size=pack_size,
        pack_purchase_price=Decimal("1800000"),
        purchase_price=base_price_from_pack(Decimal("1800000"), pack_size),
    )
    db.add_all([wh, supplier, customer, product])
    await db.flush()
    if Decimal(stock) > 0:
        db.add(StockLevel(product_id=product.id, warehouse_id=wh.id,
                          quantity=Decimal(stock), avg_cost=Decimal(avg_cost)))
        await db.flush()
    return company, wh, supplier, customer, product


# ------------------------------------------------------------------ helper murni
def test_factor_and_price_conversion():
    assert factor_for("dus", 24) == 24
    assert factor_for("DUS", 24) == 24        # tidak peka huruf besar
    assert factor_for("ctn", 24) == 24        # alias
    assert factor_for("botol", 24) == 1
    assert factor_for("btl", 24) == 1
    # Modal per dus -> per botol
    assert base_price_from_pack("1800000", 24) == Decimal("75000.00")
    assert base_price_from_pack("3700000", 12) == Decimal("308333.33")  # harga acuan tetap 2 desimal


def test_unknown_unit_is_rejected():
    """Bot TIDAK BOLEH menebak satuan: salah tebak = stok salah 24x."""
    for bad in ("", None, "lusin", "kg", "dusun"):
        try:
            normalize_unit(bad)
        except UnitError:
            continue
        raise AssertionError(f"satuan {bad!r} seharusnya ditolak")


def test_format_qty_shows_dus_and_botol():
    assert format_qty(Decimal("29"), 24) == "1 dus 5 botol"
    assert format_qty(Decimal("24"), 24) == "1 dus"
    assert format_qty(Decimal("5"), 24) == "5 botol"
    assert format_qty(Decimal("0"), 24) == "0 botol"
    assert format_qty(Decimal("48"), 48) == "1 dus"
    # produk tanpa kemasan (isi 1) tetap tampil dalam botol
    assert format_qty(Decimal("7"), 1) == "7 botol"


# ------------------------------------------------------- avg_cost campur satuan
async def test_avg_cost_per_botol_saat_beli_dus(db):
    """Beli 1 dus @ 3.700.000 (isi 12) -> avg_cost 308.333,3333 per BOTOL."""
    company, wh, supplier, _, product = await _setup(db, pack_size=12)

    bill = await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": product.id, "quantity": "1", "unit": "dus",
                   "unit_cost": "3700000"}],
    )
    # Nilai uang tetap mengikuti satuan yang diketik: 1 dus x 3.700.000.
    assert bill.subtotal == Decimal("3700000.00")

    line = bill.lines[0]
    assert Decimal(str(line.qty_input)) == Decimal("1.0000")
    assert line.unit == "dus"
    assert line.unit_factor == 12
    assert Decimal(str(line.quantity)) == Decimal("12.0000")   # tersimpan botol

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("12.0000")
    assert Decimal(str(level.avg_cost)) == Decimal("308333.3333")


async def test_avg_cost_campur_dus_lalu_botol(db):
    """Beli 1 dus lalu 5 botol — average harus tertimbang dalam satuan botol."""
    company, wh, supplier, _, product = await _setup(db, pack_size=12)

    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": product.id, "quantity": "1", "unit": "dus",
                   "unit_cost": "3700000"}],
    )
    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": product.id, "quantity": "5", "unit": "botol",
                   "unit_cost": "320000"}],
    )

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("17.0000")   # 12 + 5
    # (12 x 308.333,3333 + 5 x 320.000) / 17 = 311.764,7059
    assert Decimal(str(level.avg_cost)) == Decimal("311764.7059")


async def test_satu_bill_dua_baris_dus_dan_botol(db):
    """Pembelian campur dalam SATU tagihan (client minta bisa fleksibel)."""
    company, wh, supplier, _, product = await _setup(db, pack_size=24)

    bill = await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[
            {"product_id": product.id, "quantity": "1", "unit": "dus",
             "unit_cost": "1800000"},
            {"product_id": product.id, "quantity": "5", "unit": "botol",
             "unit_cost": "80000"},
        ],
    )
    assert bill.subtotal == Decimal("2200000.00")     # 1.800.000 + 400.000

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("29.0000")   # 24 + 5
    assert format_qty(level.quantity, product.pack_size) == "1 dus 5 botol"


# ------------------------------------------------------------- penjualan campur
async def test_penjualan_campur_dus_dan_botol_hpp_benar(db):
    """Jual '1 dus dan 5 botol Chivas 200ml' = dua baris; HPP dari 29 botol."""
    company, wh, _, customer, product = await _setup(
        db, pack_size=24, stock="48", avg_cost="75000")

    invoice = await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=customer.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[
            # harga dus lebih murah dari 24x harga botol (diskon grosir)
            {"product_id": product.id, "quantity": "1", "unit": "dus",
             "unit_price": "2400000"},
            {"product_id": product.id, "quantity": "5", "unit": "botol",
             "unit_price": "110000"},
        ],
    )
    assert invoice.subtotal == Decimal("2950000.00")   # 2.400.000 + 550.000
    assert not invoice.stock_warnings

    # HPP = 29 botol x 75.000 = 2.175.000
    entries = (await db.execute(
        select(JournalEntry, Account.code)
        .join(Account, Account.id == JournalEntry.account_id)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(Journal.id == invoice.journal_id)
    )).all()
    cogs = sum(Decimal(str(e.debit)) for e, code in entries
               if code == DEFAULT_CODES["cogs"])
    assert cogs == Decimal("2175000.00")
    # jurnal tetap balance
    assert (sum(Decimal(str(e.debit)) for e, _ in entries)
            == sum(Decimal(str(e.credit)) for e, _ in entries))

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("19.0000")   # 48 - 29


async def test_peringatan_stok_kurang_dalam_dus_botol(db):
    """Stok kurang dilaporkan sebagai 'dus + botol', bukan angka botol mentah."""
    company, wh, _, customer, product = await _setup(
        db, pack_size=24, stock="10", avg_cost="75000")

    invoice = await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=customer.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": product.id, "quantity": "1", "unit": "dus",
                   "unit_price": "2400000"}],
    )
    assert invoice.stock_warnings == [{
        "product": "Chivas 200ml",
        "diminta": "1 dus",
        "tersedia": "10 botol",
        "kurang": "14 botol",
    }]


# ------------------------------------- valuasi stok vs saldo jurnal (regresi)
async def test_valuasi_stok_cocok_dengan_saldo_persediaan_di_jurnal(db):
    """Laporan valuasi stok harus cocok SAMPAI SEN dengan akun Persediaan.

    Ini alasan `avg_cost` disimpan 4 desimal (UnitCost di models/base.py):
    pembagian dus->botol jarang bulat, dan dengan 2 desimal `qty * avg_cost`
    melenceng dari saldo jurnal — akuntan yang merekonsiliasi dua laporan itu
    akan melihat selisih yang tidak bisa dijelaskan.

    Skenario memakai angka yang TIDAK bulat: 7.600.000 / 101 botol.
    """
    company, wh, supplier, customer, product = await _setup(db, pack_size=24)

    # 3 dus @1.800.000 lalu campur 1 dus + 5 botol  -> 101 botol / Rp 7.600.000
    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[{"product_id": product.id, "quantity": "3", "unit": "dus",
                   "unit_cost": "1800000"}],
    )
    await create_and_post_bill(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[
            {"product_id": product.id, "quantity": "1", "unit": "dus",
             "unit_cost": "1800000"},
            {"product_id": product.id, "quantity": "5", "unit": "botol",
             "unit_cost": "80000"},
        ],
    )
    # jual sebagian supaya HPP ikut membebani persediaan
    await create_and_post_invoice(
        db, company_id=company.id, user_id=None, contact_id=customer.id,
        on_date=date.today(), warehouse_id=wh.id,
        lines_in=[
            {"product_id": product.id, "quantity": "2", "unit": "dus",
             "unit_price": "2400000"},
            {"product_id": product.id, "quantity": "7", "unit": "botol",
             "unit_price": "110000"},
        ],
    )

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id)
    )).scalar_one()
    valuasi = (Decimal(str(level.quantity))
               * Decimal(str(level.avg_cost))).quantize(Decimal("0.01"))

    inventory_id = (await db.execute(
        select(Account.id).where(Account.company_id == company.id,
                                Account.code == DEFAULT_CODES["inventory"])
    )).scalar_one()
    rows = (await db.execute(
        select(JournalEntry.debit, JournalEntry.credit)
        .where(JournalEntry.account_id == inventory_id)
    )).all()
    saldo_jurnal = sum(
        (Decimal(str(d)) - Decimal(str(c)) for d, c in rows), Decimal("0")
    ).quantize(Decimal("0.01"))

    assert valuasi == saldo_jurnal, (
        f"valuasi stok {valuasi} != saldo Persediaan {saldo_jurnal}"
    )


# ------------------------------------------------------- PO -> Bill (regresi)
async def test_po_ke_bill_tidak_konversi_dua_kali(db):
    """PO 1 dus yang diterima harus jadi 12 botol, BUKAN 144.

    Jebakan: kalau konversi PO->Bill mengirim `quantity` (sudah botol) alih-alih
    `qty_input` + satuan, faktor dikalikan dua kali.
    """
    company, wh, supplier, _, product = await _setup(db, pack_size=12)

    po = await create_purchase_order(
        db, company_id=company.id, user_id=None, contact_id=supplier.id,
        on_date=date.today(), expected_date=None, warehouse_id=wh.id,
        freight_total=Decimal("0"), freight_supplier_share=Decimal("0"),
        notes=None,
        lines_in=[{"product_id": product.id, "quantity": "1", "unit": "dus",
                   "unit_price": "3700000"}],
    )
    assert Decimal(str(po.lines[0].quantity)) == Decimal("12.0000")
    assert po.total == Decimal("3700000.00")

    await receive_purchase_order(db, company_id=company.id, user_id=None,
                                po_id=po.id)

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id)
    )).scalar_one()
    assert Decimal(str(level.quantity)) == Decimal("12.0000")
    assert Decimal(str(level.avg_cost)) == Decimal("308333.3333")
