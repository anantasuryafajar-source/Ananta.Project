"""Penjaga kerapian Neraca & AR Aging saat kesepakatan pembayaran bervariasi.

Yang dijaga:
  - DP tidak pernah menyentuh Pendapatan
  - piutang tidak pernah negatif karena DP
  - total outstanding faktur SELALU sama dengan saldo akun Piutang di neraca
  - termin "tagih di PO berikutnya" tidak dilaporkan menunggak
  - skema komisi per botol memakai BOTOL, bukan dus
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models import (
    Company, Warehouse, Contact, Product, StockLevel, Account, CommissionScheme,
)
from app.services.invoice_service import create_and_post_invoice
from app.services.accounts_map import DEFAULT_CODES
from app.services import (
    advance_service, terms_service, reports, payment_service,
    commission_service,
)


async def _setup(db):
    c = Company(name="T", currency="IDR", costing_method="average")
    db.add(c)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        db.add(Account(company_id=c.id, code=code, name=key, type="asset",
                       normal_balance="debit"))
    # Piutang & Pendapatan perlu tipe/saldo normal yang benar untuk laporan.
    await db.flush()
    for code, tipe, nb in (("1-1200", "asset", "debit"),
                           ("4-1000", "income", "credit"),
                           ("1-1000", "asset", "debit")):
        acc = (await db.execute(select(Account).where(
            Account.company_id == c.id, Account.code == code))).scalar_one()
        acc.type, acc.normal_balance = tipe, nb
    db.add(Account(company_id=c.id, code="6-1100", name="Beban Komisi",
                   type="expense", normal_balance="debit"))
    wh = Warehouse(company_id=c.id, code="GD1", name="Utama", is_default=True)
    ct = Contact(company_id=c.id, type="customer", name="Pelanggan A",
                 payment_term_days=0)
    # 1 dus = 12 botol, modal 6.000/botol
    p = Product(company_id=c.id, sku="A1", name="Barang A", kind="good",
                pack_size=12, purchase_price=Decimal("6000"))
    db.add_all([wh, ct, p])
    await db.flush()
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=Decimal("1000"), avg_cost=Decimal("6000")))
    await db.flush()
    return c, wh, ct, p


async def _faktur(db, c, wh, ct, p, qty="10", harga="10000", unit="botol"):
    return await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 10), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": qty, "unit": unit,
                   "unit_price": harga}],
    )


async def _saldo_akun(db, company_id, code, as_of=date(2026, 12, 31)) -> Decimal:
    neraca = await reports.balance_sheet(db, company_id, as_of)
    for grup in ("assets", "liabilities", "equity"):
        for baris in neraca[grup]:
            if baris["code"] == code:
                return Decimal(baris["amount"])
    return Decimal("0")


# ------------------------------------------------------------ UANG MUKA
async def test_dp_tidak_menyentuh_pendapatan(db):
    """DP adalah kewajiban menyerahkan barang, bukan penghasilan."""
    c, wh, ct, p = await _setup(db)
    await advance_service.receive_advance(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 5), amount=Decimal("1000000"),
    )
    pl = await reports.profit_loss(db, c.id, date(2026, 1, 1), date(2026, 1, 31))
    assert pl["total_income"] == "0.00"
    # Uangnya ada di kewajiban, bukan menguap.
    assert await _saldo_akun(db, c.id, "2-1500") == Decimal("1000000.00")


async def test_alokasi_dp_mengurangi_piutang_tanpa_kas_bergerak(db):
    c, wh, ct, p = await _setup(db)
    adv = await advance_service.receive_advance(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 5), amount=Decimal("60000"),
    )
    kas_sebelum = await _saldo_akun(db, c.id, "1-1000")
    inv = await _faktur(db, c, wh, ct, p)  # 10 x 10.000 = 100.000

    await advance_service.allocate_to_invoice(
        db, company_id=c.id, user_id=None, advance_id=adv.id,
        invoice_id=inv.id, on_date=date(2026, 1, 10), amount=Decimal("60000"),
    )
    await db.refresh(inv)
    assert Decimal(str(inv.paid_total)) == Decimal("60000.00")
    assert await _saldo_akun(db, c.id, "1-1200") == Decimal("40000.00")
    assert await _saldo_akun(db, c.id, "2-1500") == Decimal("0.00")
    # Alokasi bukan penerimaan kas — saldo kas tidak boleh berubah.
    assert await _saldo_akun(db, c.id, "1-1000") == kas_sebelum


async def test_dp_berlebih_tidak_bikin_piutang_negatif(db):
    """Kelebihan DP harus tetap jadi kewajiban, bukan piutang minus."""
    c, wh, ct, p = await _setup(db)
    adv = await advance_service.receive_advance(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 5), amount=Decimal("500000"),
    )
    inv = await _faktur(db, c, wh, ct, p)  # 100.000

    with pytest.raises(ValueError, match="melebihi sisa piutang"):
        await advance_service.allocate_to_invoice(
            db, company_id=c.id, user_id=None, advance_id=adv.id,
            invoice_id=inv.id, on_date=date(2026, 1, 10),
            amount=Decimal("500000"),
        )
    saldo = await advance_service.advance_balance(db, c.id, ct.id)
    assert saldo == Decimal("500000.00")


async def test_saldo_piutang_cocok_dengan_neraca(db):
    """Invarian paling penting: laporan piutang == akun piutang di jurnal.

    Sepadan dengan test_valuasi_stok_cocok_dengan_saldo_persediaan_di_jurnal.
    Ini yang menangkap kalau alokasi DP mengambil jalur yang salah.
    """
    c, wh, ct, p = await _setup(db)
    inv1 = await _faktur(db, c, wh, ct, p)                       # 100.000
    inv2 = await _faktur(db, c, wh, ct, p, qty="5")              # 50.000
    adv = await advance_service.receive_advance(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 5), amount=Decimal("30000"),
    )
    await advance_service.allocate_to_invoice(
        db, company_id=c.id, user_id=None, advance_id=adv.id,
        invoice_id=inv1.id, on_date=date(2026, 1, 10), amount=Decimal("30000"),
    )
    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv2.id,
        on_date=date(2026, 1, 15), amount=Decimal("20000"),
    )

    aging = await reports.ar_aging(db, c.id, date(2026, 1, 31))
    assert Decimal(aging["total"]) == await _saldo_akun(db, c.id, "1-1200")
    assert Decimal(aging["total"]) == Decimal("100000.00")


# ------------------------------------------------------------ TERMIN
async def test_total_termin_wajib_sama_dengan_faktur(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)  # 100.000
    with pytest.raises(ValueError, match="tidak sama dengan total faktur"):
        await terms_service.set_terms(db, invoice_id=inv.id, terms=[
            {"kind": "dp", "due_date": date(2026, 1, 10), "amount": "30000"},
            {"kind": "tempo", "due_date": date(2026, 2, 9), "amount": "50000"},
        ])


async def test_dp_lalu_tempo_dicatat_sebagai_dua_termin(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    rows = await terms_service.set_terms(db, invoice_id=inv.id, terms=[
        {"kind": "dp", "due_date": date(2026, 1, 10), "amount": "30000"},
        {"kind": "tempo", "due_date": date(2026, 2, 9), "amount": "70000"},
    ])
    assert len(rows) == 2
    await db.refresh(inv)
    assert inv.due_date == date(2026, 2, 9)


async def test_po_berikutnya_tidak_dihitung_menunggak(db):
    """Kesepakatan "tagih saat order berikutnya" bukan tunggakan."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    await terms_service.set_terms(db, invoice_id=inv.id, terms=[
        {"kind": "po_berikutnya", "due_date": None, "amount": "100000"},
    ])
    # Setahun kemudian pun tidak boleh masuk ember 90+ hari.
    aging = await reports.ar_aging(db, c.id, date(2027, 1, 10))
    assert aging["buckets"]["tanpa_tempo"] == "100000.00"
    assert aging["buckets"]["d90_plus"] == "0.00"
    assert Decimal(aging["total"]) == await _saldo_akun(db, c.id, "1-1200")


async def test_pembayaran_menutup_termin_berurutan(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    await terms_service.set_terms(db, invoice_id=inv.id, terms=[
        {"kind": "dp", "due_date": date(2026, 1, 10), "amount": "30000"},
        {"kind": "tempo", "due_date": date(2026, 2, 9), "amount": "70000"},
    ])
    await payment_service.receive_payment(
        db, company_id=c.id, user_id=None, invoice_id=inv.id,
        on_date=date(2026, 1, 12), amount=Decimal("50000"),
    )
    from app.models import InvoiceTerm
    rows = (await db.execute(
        select(InvoiceTerm).where(InvoiceTerm.invoice_id == inv.id)
        .order_by(InvoiceTerm.sequence)
    )).scalars().all()
    assert Decimal(str(rows[0].settled_amount)) == Decimal("30000.00")
    assert Decimal(str(rows[1].settled_amount)) == Decimal("20000.00")


async def test_faktur_lama_tanpa_jadwal_tetap_jalan(db):
    """Tidak ada backfill — faktur lama dihitung dengan due_date-nya sendiri."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    aging = await reports.ar_aging(db, c.id, date(2026, 1, 31))
    assert Decimal(aging["total"]) == Decimal("100000.00")
    assert aging["buckets"]["tanpa_tempo"] == "0.00"


# ------------------------------------------------------------ SKEMA KOMISI
async def test_skema_per_botol_memakai_botol_bukan_dus(db):
    """Faktur "2 dus" = 24 botol. Tarif 1.000/botol harus jadi 24.000.

    Kalau suatu saat kode ini memakai qty_input, hasilnya 2.000 — salah 12x.
    """
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p, qty="2", harga="120000", unit="dus")
    sk = CommissionScheme(company_id=c.id, name="Per botol",
                          type="per_botol", value=Decimal("1000"))
    db.add(sk)
    await db.flush()
    nilai = await commission_service.hitung_dari_skema(db, c.id, sk, inv.id)
    assert nilai == Decimal("24000.00")


async def test_skema_nominal_dan_persen(db):
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)  # omzet 100.000, modal 60.000
    flat = CommissionScheme(company_id=c.id, name="Flat 50rb",
                            type="nominal", value=Decimal("50000"))
    omzet = CommissionScheme(company_id=c.id, name="2% omzet",
                             type="persen_omzet", value=Decimal("2"))
    margin = CommissionScheme(company_id=c.id, name="5% margin",
                              type="persen_margin", value=Decimal("5"))
    db.add_all([flat, omzet, margin])
    await db.flush()
    assert await commission_service.hitung_dari_skema(db, c.id, flat, inv.id) \
        == Decimal("50000.00")
    assert await commission_service.hitung_dari_skema(db, c.id, omzet, inv.id) \
        == Decimal("2000.00")
    assert await commission_service.hitung_dari_skema(db, c.id, margin, inv.id) \
        == Decimal("2000.00")


async def test_skema_manual_tidak_menghitung_apa_pun(db):
    """Pintu darurat kasus khusus: menyimpan angka, bukan aturan."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    sk = CommissionScheme(company_id=c.id, name="Kasus khusus",
                          type="manual", value=Decimal("0"))
    db.add(sk)
    await db.flush()
    assert await commission_service.hitung_dari_skema(db, c.id, sk, inv.id) \
        == Decimal("0")


async def test_skema_di_snapshot_ke_komisi(db):
    """Tarif berubah nanti tidak boleh menggeser komisi yang sudah disepakati."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    sk = CommissionScheme(company_id=c.id, name="Per botol",
                          type="per_botol", value=Decimal("1000"))
    db.add(sk)
    await db.flush()

    kom = await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("10000"),
        scheme_id=sk.id,
    )
    sk.value = Decimal("9999")   # tarif naik belakangan
    await db.flush()

    assert Decimal(str(kom.scheme_value)) == Decimal("1000.00")
    assert kom.scheme_type == "per_botol"
    assert Decimal(str(kom.amount)) == Decimal("10000.00")


# ------------------------------------------------------------ JADWAL OTOMATIS
async def test_setiap_faktur_langsung_punya_jadwal(db):
    """Tidak ada faktur tanpa jadwal — AR Aging tidak perlu menebak."""
    from app.models import InvoiceTerm
    c, wh, ct, p = await _setup(db)
    ct.payment_term_days = 30
    await db.flush()
    inv = await _faktur(db, c, wh, ct, p)
    rows = (await db.execute(
        select(InvoiceTerm).where(InvoiceTerm.invoice_id == inv.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "tempo"
    assert rows[0].due_date == date(2026, 1, 10) + timedelta(days=30)
    assert Decimal(str(rows[0].amount)) == Decimal(str(inv.total))


async def test_jadwal_dp_dikirim_saat_faktur_dibuat(db):
    """Kesepakatan "DP 30% lalu tempo" bisa langsung ikut saat faktur dibuat."""
    from app.models import InvoiceTerm
    c, wh, ct, p = await _setup(db)
    inv = await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 10), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": "10", "unit_price": "10000"}],
        terms=[
            {"kind": "dp", "due_date": date(2026, 1, 10), "amount": "30000"},
            {"kind": "tempo", "due_date": date(2026, 2, 9), "amount": "70000"},
        ],
    )
    rows = (await db.execute(
        select(InvoiceTerm).where(InvoiceTerm.invoice_id == inv.id)
        .order_by(InvoiceTerm.sequence)
    )).scalars().all()
    assert [r.kind for r in rows] == ["dp", "tempo"]


async def test_jadwal_salah_jumlah_membatalkan_seluruh_faktur(db):
    """Invarian ditegakkan sebelum commit — tidak boleh ada faktur setengah jadi.

    Jurnal faktur sudah dibuat saat validasi termin gagal, jadi seluruh
    transaksi harus dibatalkan oleh pemanggil (router melakukan rollback).
    Yang dijaga di sini: kesalahannya benar-benar terdeteksi, bukan lolos diam.
    """
    c, wh, ct, p = await _setup(db)
    with pytest.raises(ValueError, match="tidak sama dengan total faktur"):
        await create_and_post_invoice(
            db, company_id=c.id, user_id=None, contact_id=ct.id,
            on_date=date(2026, 1, 10), warehouse_id=wh.id,
            lines_in=[{"product_id": p.id, "quantity": "10",
                       "unit_price": "10000"}],
            terms=[{"kind": "tunai", "due_date": date(2026, 1, 10),
                    "amount": "999"}],
        )
    await db.rollback()


# --------------------------------------------- KOMISI BERTINGKAT (margin - ongkir)
async def test_persen_margin_min_ongkir_kasus_nyata(db):
    """Kasus client 2026-08-21: margin 360rb, ongkir 50rb/dus x 2 dus, lalu 4%.

    (360.000 - 100.000) x 4% = 10.400.

    Angka-angkanya dipilih supaya cocok dengan contoh yang diberikan client,
    jadi kalau perhitungannya bergeser, tes ini yang memberi tahu.
    """
    c, wh, ct, p = await _setup(db)
    # 2 dus x 12 botol; modal 6.000/botol = 144.000.
    # Harga jual dipasang supaya margin persis 360.000 -> omzet 504.000.
    inv = await _faktur(db, c, wh, ct, p, qty="2", harga="252000", unit="dus")
    sk = CommissionScheme(company_id=c.id, name="4% setelah ongkir",
                          type="persen_margin_min_ongkir", value=Decimal("4"),
                          ongkir_per_dus=Decimal("50000"))
    db.add(sk)
    await db.flush()

    r = await commission_service.rincian_skema(db, c.id, sk, inv.id)
    assert r["amount"] == Decimal("10400.00")
    # Rincian harus bisa dibaca manusia untuk memeriksa angkanya.
    labels = [l["label"] for l in r["langkah"]]
    assert "Margin" in labels and "Dasar komisi" in labels


async def test_ongkir_lebih_besar_dari_margin_tidak_jadi_komisi_negatif(db):
    """Komisi negatif berarti menagih uang ke sales — tidak boleh terjadi."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p, qty="1", harga="80000", unit="dus")
    sk = CommissionScheme(company_id=c.id, name="4% setelah ongkir",
                          type="persen_margin_min_ongkir", value=Decimal("4"),
                          ongkir_per_dus=Decimal("500000"))
    db.add(sk)
    await db.flush()
    assert await commission_service.hitung_dari_skema(db, c.id, sk, inv.id) \
        == Decimal("0")


async def test_dus_dihitung_pecahan_bukan_dibulatkan(db):
    """18 botol dari dus isi 12 = 1,5 dus, bukan 2.

    Keputusan bisnis, bukan kebetulan implementasi — dikunci di sini supaya
    tidak berubah diam-diam.
    """
    c, wh, ct, p = await _setup(db)
    # 18 botol @ 30.000 = omzet 540.000; modal 18 x 6.000 = 108.000
    # margin 432.000 - (1,5 x 50.000 = 75.000) = 357.000 x 10% = 35.700
    inv = await _faktur(db, c, wh, ct, p, qty="18", harga="30000", unit="botol")
    sk = CommissionScheme(company_id=c.id, name="10% setelah ongkir",
                          type="persen_margin_min_ongkir", value=Decimal("10"),
                          ongkir_per_dus=Decimal("50000"))
    db.add(sk)
    await db.flush()
    assert await commission_service.hitung_dari_skema(db, c.id, sk, inv.id) \
        == Decimal("35700.00")
