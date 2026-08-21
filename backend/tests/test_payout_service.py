"""Penyambungan mesin hitung ke buku besar.

Yang dijaga paling ketat: komisi TIDAK boleh terjurnal dua kali. Lembar
hitung sudah mengakuinya penuh saat disetujui; prorata cuma membuka kunci
transfer, bukan membuat jurnal baru.
"""
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models import (
    Company, Warehouse, Contact, Product, StockLevel, Account, Payout,
)
from app.services.invoice_service import create_and_post_invoice
from app.services.accounts_map import DEFAULT_CODES
from app.services import (
    payout_service as po, profit_sheet_service as ps, reports, payment_service,
)
from app.services.incentive_engine import MonthData, PaymentRecord

D = Decimal


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
    wh = Warehouse(company_id=c.id, code="GD1", name="U", is_default=True)
    ct = Contact(company_id=c.id, type="customer", name="Toko", payment_term_days=0)
    p = Product(company_id=c.id, sku="A1", name="A", kind="good",
                pack_size=1, purchase_price=D("600"))
    db.add_all([wh, ct, p])
    await db.flush()
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=D("10000"), avg_cost=D("600")))
    await db.flush()
    return c, wh, ct, p


async def _faktur(db, c, wh, ct, p, qty="1", harga="1000"):
    return await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 3, 5), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": qty, "unit_price": harga}])


async def _saldo(db, cid, code, grup="pnl", akhir=date(2026, 12, 31)):
    if grup == "pnl":
        pl = await reports.profit_loss(db, cid, date(2026, 1, 1), akhir)
        for bag in ("income", "expense"):
            for b in pl[bag]:
                if b["code"] == code:
                    return D(b["amount"])
        return D("0")
    n = await reports.balance_sheet(db, cid, akhir)
    for g in ("assets", "liabilities", "equity"):
        for b in n[g]:
            if b["code"] == code:
                return D(b["amount"])
    return D("0")


# ============================================ ANTI DOBEL AKRUAL
def test_porsi_komisi_cair_tidak_membuat_jurnal():
    """Fungsi murni — hanya membuka kunci, tidak menambah beban."""
    cair = po.porsi_komisi_cair(D("16000000"), D("76000"), D("10000000"))
    assert cair == D("47500.00")


def test_pelepasan_prorata_berjumlah_pas_saat_lunas():
    """Cicilan pelunas menyerap sisa pembulatan."""
    total, pengurang = D("208000000"), D("41000000")
    dicairkan = D("0")
    for cicilan, lunas in ((D("10000000"), False), (D("99000000"), False),
                           (D("99000000"), True)):
        dicairkan += po.porsi_komisi_cair(total, pengurang, cicilan,
                                          sudah_dicairkan=dicairkan,
                                          lunas=lunas)
    assert dicairkan == pengurang


async def test_komisi_tidak_terjurnal_dua_kali(db):
    """Lembar hitung mengakui penuh; cicilan tidak menambah beban komisi."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 3, 5),
        baris=[{"payee_name": "Rusdi", "jenis": "komisi",
                "dasar": "margin_riil", "persen": "10"}])
    await ps.approve_sheet(db, company_id=c.id, user_id=None, sheet_id=s.id,
                           on_date=date(2026, 3, 5))
    beban_awal = await _saldo(db, c.id, "6-1100")
    assert beban_awal == D("40.00")          # 10% x (1000 - 600)

    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 3, 10), amount=D("500"))
    # Cicilan masuk TIDAK boleh menambah beban komisi.
    assert await _saldo(db, c.id, "6-1100") == beban_awal


# ============================================ INSENTIF
async def test_akrual_insentif_per_cicilan(db):
    """Dasarnya uang masuk bersih, jadi diakui saat uangnya masuk."""
    c, wh, ct, p = await _setup(db)
    await po.accrue_insentif(
        db, company_id=c.id, user_id=None, on_date=date(2026, 3, 10),
        payee_name="Sales", net_basis=D("100000000"))
    assert await _saldo(db, c.id, "6-1400") == D("4300000.00")   # 4,3%
    assert await _saldo(db, c.id, "2-1800", "neraca") == D("4300000.00")


async def test_bayar_insentif_hanya_menutup_utang(db):
    c, wh, ct, p = await _setup(db)
    x = await po.accrue_insentif(
        db, company_id=c.id, user_id=None, on_date=date(2026, 3, 10),
        payee_name="Sales", net_basis=D("100000000"))
    await po.pay_payout(db, company_id=c.id, user_id=None, payout_id=x.id,
                        on_date=date(2026, 3, 16))
    assert await _saldo(db, c.id, "6-1400") == D("4300000.00")   # tetap
    assert await _saldo(db, c.id, "2-1800", "neraca") == D("0.00")


# ============================================ TUTUP BUKU
def _bayar(hari, basis):
    return PaymentRecord(tanggal=date(2026, 3, hari), net_basis=D(basis),
                         commission_released=D("0"))


async def test_tutup_buku_pratinjau_tidak_menjurnal(db):
    """Tutup buku memindahkan ratusan juta — harus dilihat orang dulu."""
    c, wh, ct, p = await _setup(db)
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
                     pembayaran=[_bayar(10, "300000000"), _bayar(20, "250000000")])
    r = await po.close_month(db, company_id=c.id, user_id=None, data=data,
                             on_date=date(2026, 4, 1))
    assert r["mode"] == "pratinjau"
    assert r["dijurnalkan"] == []
    assert await _saldo(db, c.id, "6-1500") == D("0")


async def test_tutup_buku_terapkan_menjurnal_bonus_dan_bagi_hasil(db):
    c, wh, ct, p = await _setup(db)
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
                     pembayaran=[_bayar(10, "300000000"), _bayar(20, "250000000")])
    r = await po.close_month(db, company_id=c.id, user_id=None, data=data,
                             on_date=date(2026, 4, 1), terapkan=True)
    assert len(r["dijurnalkan"]) == 4     # Term2, Booster, Sam, Delvina
    # 13.250.000 + 3.000.000
    assert await _saldo(db, c.id, "6-1400") == D("16250000.00")
    # 108.000.000 + 84.000.000
    assert await _saldo(db, c.id, "6-1500") == D("192000000.00")
    assert await _saldo(db, c.id, "2-1900", "neraca") == D("192000000.00")


async def test_tutup_buku_aman_diulang(db):
    """Dijalankan dua kali tidak boleh menggandakan beban."""
    c, wh, ct, p = await _setup(db)
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
                     pembayaran=[_bayar(10, "300000000"), _bayar(20, "250000000")])
    for _ in range(2):
        r = await po.close_month(db, company_id=c.id, user_id=None, data=data,
                                 on_date=date(2026, 4, 1), terapkan=True)
    assert r["dijurnalkan"] == []
    assert await _saldo(db, c.id, "6-1500") == D("192000000.00")


async def test_target_meleset_tidak_menjurnal_apa_pun(db):
    """All-or-nothing: tidak ada beban yang diakui kalau target tak tercapai."""
    c, wh, ct, p = await _setup(db)
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("100000000"),
                     pembayaran=[_bayar(10, "80000000")])
    r = await po.close_month(db, company_id=c.id, user_id=None, data=data,
                             on_date=date(2026, 4, 1), terapkan=True)
    assert r["dijurnalkan"] == []
    assert await _saldo(db, c.id, "6-1500") == D("0")
    assert await _saldo(db, c.id, "6-1400") == D("0")


async def test_batalkan_hak_menutup_utang(db):
    c, wh, ct, p = await _setup(db)
    x = await po.accrue_insentif(
        db, company_id=c.id, user_id=None, on_date=date(2026, 3, 10),
        payee_name="Sales", net_basis=D("10000000"))
    await po.void_payout(db, company_id=c.id, user_id=None, payout_id=x.id,
                         on_date=date(2026, 3, 20), reason="salah input")
    assert await _saldo(db, c.id, "2-1800", "neraca") == D("0.00")
    assert await _saldo(db, c.id, "6-1400") == D("0.00")


async def test_hak_terbayar_tidak_bisa_dibatalkan(db):
    """Kalau boleh, utang terhapus padahal uangnya sudah keluar."""
    c, wh, ct, p = await _setup(db)
    x = await po.accrue_insentif(
        db, company_id=c.id, user_id=None, on_date=date(2026, 3, 10),
        payee_name="Sales", net_basis=D("10000000"))
    await po.pay_payout(db, company_id=c.id, user_id=None, payout_id=x.id,
                        on_date=date(2026, 3, 16))
    with pytest.raises(ValueError, match="tarik kembali dananya"):
        await po.void_payout(db, company_id=c.id, user_id=None,
                             payout_id=x.id, on_date=date(2026, 3, 20))


# ============================================ AKRUAL OTOMATIS
async def test_receive_payment_mengakui_insentif_otomatis(db):
    """Kasir mencatat kas masuk -> Utang Insentif langsung terbentuk."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p, harga="1000")   # total 1000
    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 3, 10), amount=D("500"))
    # Tanpa lembar hitung, pengurang 0 -> dasar = 500; 4,3% = 21,50
    assert await _saldo(db, c.id, "6-1400") == D("21.50")
    assert await _saldo(db, c.id, "2-1800", "neraca") == D("21.50")


async def test_dasar_insentif_dipotong_pengurang_lembar_hitung(db):
    """Komisi & hak mitra dipotong dulu sebelum bonus dihitung."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p, harga="1000")
    s = await ps.create_sheet(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 3, 5), modal_perjanjian="700",
        baris=[{"payee_name": "Andre", "jenis": "bagi_hasil",
                "dasar": "profit_bersama", "persen": "50"},
               {"payee_name": "Silo", "jenis": "komisi",
                "dasar": "bagian_asf", "persen": "4"},
               {"payee_name": "Elias", "jenis": "komisi",
                "dasar": "bagian_asf", "persen": "6"}])
    await ps.approve_sheet(db, company_id=c.id, user_id=None, sheet_id=s.id,
                           on_date=date(2026, 3, 5))
    # Pengurang = 150 + 6 + 9 = 165 -> rasio bersih 835/1000
    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 3, 10), amount=D("1000"))
    payout = (await db.execute(
        select(Payout).where(Payout.invoice_id == inv.id))).scalars().all()
    assert len(payout) == 1
    assert D(str(payout[0].dasar)) == D("835.00")
    assert D(str(payout[0].amount)) == D("35.91")     # 4,3% x 835


async def test_cicilan_pelunas_menyerap_pembulatan_dasar_insentif(db):
    """Jumlah dasar lintas cicilan harus persis (Total - Pengurang)."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p, qty="3", harga="1000")   # total 3000
    for cicilan in (D("1000"), D("1000"), D("1000")):
        await payment_service.receive_payment(
            db, company_id=c.id, user_id=None, invoice_id=inv.id,
            on_date=date(2026, 3, 10), amount=cicilan)
    rows = (await db.execute(
        select(Payout.dasar).where(Payout.invoice_id == inv.id))).scalars().all()
    assert sum((D(str(r)) for r in rows), D("0")) == D("3000.00")


# ============================================ DATA & DISBURSEMENT
async def test_build_month_data_dari_transaksi_nyata(db):
    """Angka tutup buku disusun server, bukan dikirim UI."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p, qty="2", harga="1000")   # subtotal 2000
    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 3, 10), amount=D("2000"))
    data = await po.build_month_data(db, c.id, 2026, 3)
    assert data.omzet_penjualan == D("2000.00")
    assert data.laba_kotor == D("800.00")          # 2000 - (2 x 600)
    assert len(data.pembayaran) == 1
    assert data.pembayaran[0].net_basis == D("2000.00")
    assert data.pembayaran[0].invoice_lunas is True


async def test_disbursement_memisahkan_lunas_dan_tertahan(db):
    """Yang boleh ditransfer hanya dari faktur PAID."""
    c, wh, ct, p = await _setup(db)
    lunas = await _faktur(db, c, wh, ct, p, harga="1000")
    belum = await _faktur(db, c, wh, ct, p, harga="1000")
    for inv in (lunas, belum):
        s = await ps.create_sheet(
            db, company_id=c.id, user_id=None, invoice_id=inv.id,
            on_date=date(2026, 3, 5),
            baris=[{"payee_name": "Rusdi", "jenis": "komisi",
                    "dasar": "margin_riil", "persen": "10"}])
        await ps.approve_sheet(db, company_id=c.id, user_id=None,
                               sheet_id=s.id, on_date=date(2026, 3, 5))
    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=lunas.id,
        on_date=date(2026, 3, 10), amount=D("1000"))

    d = await po.daftar_disbursement(db, c.id)
    assert len(d["komisi_siap_transfer"]) == 1
    assert len(d["komisi_tertahan"]) == 1
    assert d["komisi_siap_transfer"][0]["invoice_number"] == lunas.number
    assert d["total_siap"] == "40.00"
    # Insentif dari pembayaran tadi ikut muncul sebagai hak internal.
    assert any(h["jenis"] == "insentif" for h in d["hak_internal"])
