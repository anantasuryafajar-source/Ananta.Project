"""Penjaga Lembar Hitung — bagi hasil & komisi bertingkat.

Angka-angkanya sengaja memakai contoh nyata dari client (2026-08-21) supaya
kalau perhitungannya bergeser, tes ini yang memberi tahu, bukan orang yang
protes soal bayarannya.
"""
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models import (
    Company, Warehouse, Contact, Product, StockLevel, Account, Invoice,
    ProfitSheet,
)
from app.services.invoice_service import create_and_post_invoice
from app.services.accounts_map import DEFAULT_CODES
from app.services import profit_sheet_service as ps, reports, payment_service


async def _setup(db):
    c = Company(name="ASF", currency="IDR", costing_method="average")
    db.add(c)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        db.add(Account(company_id=c.id, code=code, name=key, type="asset",
                       normal_balance="debit"))
    await db.flush()
    for code, tipe, nb in (("1-1200", "asset", "debit"),
                           ("1-1000", "asset", "debit"),
                           ("4-1000", "income", "credit"),
                           ("5-1000", "expense", "debit")):
        a = (await db.execute(select(Account).where(
            Account.company_id == c.id, Account.code == code))).scalar_one()
        a.type, a.normal_balance = tipe, nb
    wh = Warehouse(company_id=c.id, code="GD1", name="Utama", is_default=True)
    ct = Contact(company_id=c.id, type="customer", name="Toko A",
                 payment_term_days=0)
    # pack_size 1 supaya jumlah botol = jumlah unit; modal 600/unit.
    p = Product(company_id=c.id, sku="A1", name="Barang A", kind="good",
                pack_size=1, purchase_price=Decimal("600"))
    db.add_all([wh, ct, p])
    await db.flush()
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=Decimal("1000"), avg_cost=Decimal("600")))
    await db.flush()
    return c, wh, ct, p


async def _faktur(db, c, wh, ct, p, qty="1", harga="1000"):
    """Default: omzet 1.000, HPP riil 600 — angka contoh client."""
    return await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 10), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": qty, "unit_price": harga}],
    )


async def _akun(db, cid, code, grup, as_of=date(2026, 12, 31)) -> Decimal:
    if grup == "pnl":
        pl = await reports.profit_loss(db, cid, date(2026, 1, 1), as_of)
        for bagian in ("income", "expense"):
            for b in pl[bagian]:
                if b["code"] == code:
                    return Decimal(b["amount"])
        return Decimal("0")
    n = await reports.balance_sheet(db, cid, as_of)
    for g in ("assets", "liabilities", "equity"):
        for b in n[g]:
            if b["code"] == code:
                return Decimal(b["amount"])
    return Decimal("0")


BARIS_ANDRE = [
    {"payee_name": "Andre", "jenis": "bagi_hasil",
     "dasar": "profit_bersama", "persen": "50"},
    {"payee_name": "Bokap Silo", "jenis": "komisi",
     "dasar": "bagian_asf", "persen": "4"},
    {"payee_name": "Elias", "jenis": "komisi",
     "dasar": "bagian_asf", "persen": "6"},
]


# ------------------------------------------------------------ ANDRE
async def test_andre_kasus_nyata(db):
    """Omzet 1.000, HPP riil 600, modal perjanjian 700.

    Profit bersama 300 -> Andre 150, bagian ASF 150.
    Silo 4% x 150 = 6. Elias 6% x 150 = 9.
    Laba ASF = 1.000 - 600 - 150 - 15 = 235.
    """
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), baris=BARIS_ANDRE,
        modal_perjanjian="700",
    )
    nilai = {b.payee_name: Decimal(str(b.amount)) for b in s.lines}
    assert nilai["Andre"] == Decimal("150.00")
    assert nilai["Bokap Silo"] == Decimal("6.00")
    assert nilai["Elias"] == Decimal("9.00")

    await ps.approve_sheet(db, company_id=c.id, user_id=None,
                           sheet_id=s.id, on_date=date(2026, 1, 10))
    pl = await reports.profit_loss(db, c.id, date(2026, 1, 1), date(2026, 1, 31))
    assert Decimal(pl["net_profit"]) == Decimal("235.00")


async def test_komisi_pihak_ketiga_dari_bagian_asf_bukan_profit_bersama(db):
    """Urutan evaluasi: kalau salah, nilainya DUA KALI LIPAT (12, bukan 6)."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), baris=BARIS_ANDRE, modal_perjanjian="700",
    )
    silo = next(b for b in s.lines if b.payee_name == "Bokap Silo")
    assert Decimal(str(silo.amount)) == Decimal("6.00")
    assert Decimal(str(silo.amount)) != Decimal("12.00")


async def test_hidden_margin_tidak_pernah_dijurnal(db):
    """Modal perjanjian cuma dasar hitung — pendapatan & HPP tak boleh bergerak."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), baris=BARIS_ANDRE, modal_perjanjian="700",
    )
    await ps.approve_sheet(db, company_id=c.id, user_id=None,
                           sheet_id=s.id, on_date=date(2026, 1, 10))
    # Pendapatan tetap 1.000 (bukan 1.000 + hidden margin 100).
    assert await _akun(db, c.id, "4-1000", "pnl") == Decimal("1000.00")
    # HPP tetap 600 (bukan modal perjanjian 700).
    assert await _akun(db, c.id, "5-1000", "pnl") == Decimal("600.00")


async def test_hpp_dasar_komisi_tidak_menggeser_hpp_jurnal(db):
    """Custom di lembar tidak boleh merembes ke pembukuan."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), hpp_dasar_komisi="800",
        baris=[{"payee_name": "Rusdi", "jenis": "komisi",
                "dasar": "margin_komisi", "persen": "10"}],
    )
    # (1.000 - 800) x 10% = 20
    assert Decimal(str(s.lines[0].amount)) == Decimal("20.00")
    await ps.approve_sheet(db, company_id=c.id, user_id=None,
                           sheet_id=s.id, on_date=date(2026, 1, 10))
    assert await _akun(db, c.id, "5-1000", "pnl") == Decimal("600.00")
    assert Decimal(str(s.hpp_riil)) == Decimal("600.00")


async def test_lembar_tidak_mengubah_laba_kotor(db):
    """Anti-double-counting: komisi hidup di OPEX saja."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    # Laba kotor dihitung manual: reports.profit_loss tidak memisahkannya,
    # HPP ikut sebagai beban. Justru itu yang mau diuji — komisi & bagi hasil
    # boleh menambah beban, tapi TIDAK boleh menyentuh penjualan atau HPP.
    async def laba_kotor():
        return (await _akun(db, c.id, "4-1000", "pnl")
                - await _akun(db, c.id, "5-1000", "pnl"))
    kotor_sebelum = await laba_kotor()

    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), baris=BARIS_ANDRE, modal_perjanjian="700",
    )
    await ps.approve_sheet(db, company_id=c.id, user_id=None,
                           sheet_id=s.id, on_date=date(2026, 1, 10))
    assert await laba_kotor() == kotor_sebelum == Decimal("400.00")


# ------------------------------------------------------------ RUSDI
async def test_rusdi_pengurang_per_dus(db):
    """(Penjualan - HPP - 50.000/dus x dus) x 4%.

    Skala penuh: 2 dus x 12 = 24 unit. Omzet 504.000, HPP riil 144.000,
    margin 360.000, potong 100.000, sisa 260.000 x 4% = 10.400.
    """
    c = Company(name="ASF", currency="IDR", costing_method="average")
    db.add(c)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        db.add(Account(company_id=c.id, code=code, name=key, type="asset",
                       normal_balance="debit"))
    await db.flush()
    for code, tipe, nb in (("4-1000", "income", "credit"),
                           ("5-1000", "expense", "debit")):
        a = (await db.execute(select(Account).where(
            Account.company_id == c.id, Account.code == code))).scalar_one()
        a.type, a.normal_balance = tipe, nb
    wh = Warehouse(company_id=c.id, code="GD1", name="U", is_default=True)
    ct = Contact(company_id=c.id, type="customer", name="Toko", payment_term_days=0)
    p = Product(company_id=c.id, sku="B1", name="B", kind="good",
                pack_size=12, purchase_price=Decimal("6000"))
    db.add_all([wh, ct, p])
    await db.flush()
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=Decimal("500"), avg_cost=Decimal("6000")))
    await db.flush()
    inv = await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 10), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": "2", "unit": "dus",
                   "unit_price": "252000"}],
    )
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), pengurang_per_dus="50000",
        baris=[{"payee_name": "Rusdi", "jenis": "komisi",
                "dasar": "margin_min_pengurang", "persen": "4"}],
    )
    assert Decimal(str(s.jumlah_dus)) == Decimal("2.0000")
    assert Decimal(str(s.lines[0].amount)) == Decimal("10400.00")


# ------------------------------------------------------------ GERBANG & BATAL
async def test_transfer_terkunci_sebelum_faktur_lunas(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), baris=BARIS_ANDRE, modal_perjanjian="700",
    )
    await ps.approve_sheet(db, company_id=c.id, user_id=None,
                           sheet_id=s.id, on_date=date(2026, 1, 10))
    andre = next(b for b in s.lines if b.payee_name == "Andre")

    with pytest.raises(ValueError, match="belum lunas"):
        await ps.transfer_line(db, company_id=c.id, user_id=None,
                               line_id=andre.id, on_date=date(2026, 1, 11))

    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 12), amount=Decimal(str(inv.total)))

    # Menerima kas MENAMBAH beban insentif (4,3% x dasar bersih) — itu memang
    # titik pengakuannya. Yang diuji di bawah: TRANSFER-nya sendiri tidak
    # menggerakkan laba sedikit pun, karena hanya menutup utang.
    pl_sebelum = await reports.profit_loss(db, c.id, date(2026, 1, 1),
                                           date(2026, 1, 31))
    await ps.transfer_line(db, company_id=c.id, user_id=None,
                           line_id=andre.id, on_date=date(2026, 1, 12))
    pl_sesudah = await reports.profit_loss(db, c.id, date(2026, 1, 1),
                                           date(2026, 1, 31))
    assert pl_sesudah["net_profit"] == pl_sebelum["net_profit"]
    assert await _akun(db, c.id, "2-1700", "neraca") == Decimal("0.00")


async def test_batalkan_lembar_menutup_utang(db):
    """Faktur yang tak akan pernah lunas: utang tidak boleh menggantung."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 10), baris=BARIS_ANDRE, modal_perjanjian="700",
    )
    await ps.approve_sheet(db, company_id=c.id, user_id=None,
                           sheet_id=s.id, on_date=date(2026, 1, 10))
    assert await _akun(db, c.id, "2-1700", "neraca") == Decimal("150.00")

    await ps.void_sheet(db, company_id=c.id, user_id=None, sheet_id=s.id,
                        on_date=date(2026, 2, 1), reason="faktur batal")
    assert await _akun(db, c.id, "2-1700", "neraca") == Decimal("0.00")
    assert await _akun(db, c.id, "2-1600", "neraca") == Decimal("0.00")
    assert await _akun(db, c.id, "6-1300", "pnl", date(2026, 12, 31)) == Decimal("0.00")


async def test_total_hak_tidak_boleh_melebihi_margin(db):
    """Jaring pengaman salah ketik persen."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    with pytest.raises(ValueError, match="melebihi margin riil"):
        await ps.create_sheet(
            db, company_id=c.id, user_id=None, invoice_id=inv.id,
            on_date=date(2026, 1, 10),
            baris=[{"payee_name": "X", "jenis": "komisi",
                    "dasar": "omzet", "persen": "90"}],
        )


async def test_bagi_hasil_butuh_modal_perjanjian(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    with pytest.raises(ValueError, match="Modal Perjanjian"):
        await ps.create_sheet(
            db, company_id=c.id, user_id=None, invoice_id=inv.id,
            on_date=date(2026, 1, 10),
            baris=[{"payee_name": "Andre", "jenis": "bagi_hasil",
                    "dasar": "profit_bersama", "persen": "50"}],
        )


async def test_satu_faktur_satu_lembar(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    baris = [{"payee_name": "R", "jenis": "komisi",
              "dasar": "margin_riil", "persen": "5"}]
    await ps.create_sheet(db, company_id=c.id, user_id=None,
                          invoice_id=inv.id, on_date=date(2026, 1, 10),
                          baris=baris)
    with pytest.raises(ValueError, match="sudah punya lembar"):
        await ps.create_sheet(db, company_id=c.id, user_id=None,
                              invoice_id=inv.id, on_date=date(2026, 1, 10),
                              baris=baris)
