"""Tes penyesuaian stok (opname & stok awal).

Fitur ini satu-satunya yang mengubah stok tanpa dokumen pembelian, jadi ia juga
satu-satunya tempat baru di mana valuasi persediaan bisa lepas dari saldo akun
Persediaan di jurnal. Tes terpenting di file ini adalah
`test_valuasi_cocok_dengan_saldo_persediaan` - kalau itu gagal, neraca dan
laporan stok saling bertentangan dan koreksinya harus lewat jurnal manual.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    Account, Company, JournalEntry, Product, StockAdjustment, StockLevel,
    StockMovement, Warehouse,
)
from app.services.accounts_map import AUTO_CREATE, DEFAULT_CODES
from app.services.stock_adjustment_service import (
    PenyesuaianError,
    create_and_post_adjustment,
    hitung_penyesuaian,
)
from app.services.units import base_price_from_pack

_TYPES = {
    "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
    "vat_out": "liability", "vat_in": "asset", "cash": "asset",
    "bank": "asset", "ap": "liability",
}


async def _setup(db):
    """Perusahaan + gudang + 2 produk berbeda isi/dus. Stok masih kosong."""
    company = Company(name="ASF Test", currency="IDR", costing_method="average")
    db.add(company)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        kind = _TYPES[key]
        db.add(Account(
            company_id=company.id, code=code, name=key, type=kind,
            normal_balance="credit" if kind in ("liability", "income") else "debit",
        ))
    wh = Warehouse(company_id=company.id, code="GD1", name="Surabaya",
                   is_default=True)
    chivas = Product(
        company_id=company.id, sku="CHIVAS-200ML", name="Chivas 200ml",
        kind="good", unit="botol", pack_unit="dus", pack_size=24,
        pack_purchase_price=Decimal("1800000"),
        purchase_price=base_price_from_pack(Decimal("1800000"), 24),
    )
    # Barang GRATIS - modal nol yang disengaja, bukan data yang belum diisi.
    absolut = Product(
        company_id=company.id, sku="ABSOLUT-VODKA", name="Absolut Vodka",
        kind="good", unit="botol", pack_unit="dus", pack_size=12,
        pack_purchase_price=Decimal("0"), purchase_price=Decimal("0"),
    )
    db.add_all([wh, chivas, absolut])
    await db.flush()
    return company, wh, chivas, absolut


async def _saldo(db, company_id: str, code: str) -> Decimal:
    """Saldo akun dari jurnal (debit - kredit)."""
    acc_id = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one()
    rows = (await db.execute(
        select(JournalEntry.debit, JournalEntry.credit)
        .where(JournalEntry.account_id == acc_id)
    )).all()
    return sum((Decimal(str(d)) - Decimal(str(k)) for d, k in rows), Decimal("0"))


async def _level(db, product_id: str) -> StockLevel | None:
    return (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product_id)
    )).scalar_one_or_none()


# ----------------------------------------------------------------- stok awal

async def test_stok_awal_dus_dan_botol_dijumlahkan(db):
    """'15 dus 11 botol' pada isi 24 harus jadi 371 botol, bukan 15 atau 11."""
    company, wh, chivas, _ = await _setup(db)

    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "15", "qty_botol": "11",
                   "modal_per_dus": "1800000",
                   "note": "4 botol sticker jelek"}],
    )
    await db.commit()

    level = await _level(db, chivas.id)
    assert Decimal(str(level.quantity)) == Decimal("371")
    # 1.800.000 / 24 = 75.000 per botol
    assert Decimal(str(level.avg_cost)) == Decimal("75000")


async def test_stok_awal_lawan_jurnalnya_ekuitas_bukan_pendapatan(db):
    """Stok awal TIDAK boleh menyentuh laba rugi.

    Kalau lawan jurnalnya pendapatan atau beban, laba periode pertama melonjak
    atau anjlok sebesar seluruh nilai persediaan pembuka - padahal tidak ada
    untung/rugi apa pun yang terjadi.
    """
    company, wh, chivas, _ = await _setup(db)

    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "10", "qty_botol": "0",
                   "modal_per_dus": "1800000"}],
    )
    await db.commit()

    nilai = Decimal("18000000")  # 10 dus x 1.800.000
    assert await _saldo(db, company.id, "1-1400") == nilai        # Persediaan
    assert await _saldo(db, company.id, "3-4000") == -nilai       # Saldo Awal (kredit)
    # Tidak ada beban selisih yang terbentuk.
    ada_beban = (await db.execute(
        select(Account.id).where(Account.company_id == company.id,
                                 Account.code == "5-2000")
    )).scalar_one_or_none()
    assert ada_beban is None


async def test_akun_lawan_dibuat_otomatis_bila_belum_ada(db):
    """CoA lama tidak punya akun ini; harus dibuat sendiri saat dibutuhkan."""
    company, wh, chivas, _ = await _setup(db)
    kode = AUTO_CREATE["inventory_opening"][0]

    sebelum = (await db.execute(
        select(Account.id).where(Account.company_id == company.id,
                                 Account.code == kode)
    )).scalar_one_or_none()
    assert sebelum is None

    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "1", "qty_botol": "0",
                   "modal_per_dus": "1800000"}],
    )
    await db.commit()

    sesudah = (await db.execute(
        select(Account).where(Account.company_id == company.id,
                              Account.code == kode)
    )).scalar_one()
    assert sesudah.type == "equity"
    assert sesudah.normal_balance == "credit"


# -------------------------------------------------------------- opname rutin

async def test_opname_kurang_membebani_selisih_persediaan(db):
    company, wh, chivas, _ = await _setup(db)
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "10", "qty_botol": "0",
                   "modal_per_dus": "1800000"}],
    )
    await db.commit()

    # Hitung ulang: ternyata tinggal 9 dus 20 botol = 236 botol (kurang 4).
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opname",
        lines_in=[{"product_id": chivas.id, "qty_dus": "9", "qty_botol": "20",
                   "note": "2 botol pecah"}],
    )
    await db.commit()

    level = await _level(db, chivas.id)
    assert Decimal(str(level.quantity)) == Decimal("236")
    # Barang hilang dinilai sebesar yang tercatat; avg_cost tidak bergeser.
    assert Decimal(str(level.avg_cost)) == Decimal("75000")

    hilang = Decimal("4") * Decimal("75000")
    assert await _saldo(db, company.id, "5-2000") == hilang       # beban selisih
    assert await _saldo(db, company.id, "1-1400") == Decimal("18000000") - hilang


async def test_opname_lebih_memakai_rata_rata_tertimbang(db):
    """Barang bertambah dengan modal berbeda harus mengubah avg_cost tertimbang."""
    company, wh, chivas, _ = await _setup(db)
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "0", "qty_botol": "100",
                   "modal_per_dus": "2400000"}],   # 100.000 / botol
    )
    await db.commit()

    # Ketemu 20 botol lagi, modalnya 1.200.000/dus -> 50.000/botol
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opname",
        lines_in=[{"product_id": chivas.id, "qty_dus": "5", "qty_botol": "0",
                   "modal_per_dus": "1200000"}],   # 5 dus x 24 = 120 botol
    )
    await db.commit()

    level = await _level(db, chivas.id)
    assert Decimal(str(level.quantity)) == Decimal("120")
    # (100 x 100.000 + 20 x 50.000) / 120 = 91.666,6667
    assert Decimal(str(level.avg_cost)) == Decimal("91666.6667")


# ------------------------------------------------------- barang bermodal nol

async def test_barang_gratis_menambah_stok_tanpa_jurnal(db):
    """Modal nol yang disengaja: kuantitas naik, nilai persediaan tidak.

    Tidak ada jurnal yang perlu diposting karena tidak ada rupiah yang
    berpindah - dan valuasi tetap cocok dengan saldo Persediaan (0 = 0).
    """
    company, wh, _, absolut = await _setup(db)

    hitung = await hitung_penyesuaian(
        db, company_id=company.id, warehouse_id=wh.id,
        lines_in=[{"product_id": absolut.id, "qty_dus": "1", "qty_botol": "0"}],
    )
    assert hitung["total_value"] == Decimal("0.00")
    assert len(hitung["warnings"]) == 1
    assert "HPP-nya nol" in hitung["warnings"][0]

    adj = await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": absolut.id, "qty_dus": "1", "qty_botol": "0"}],
    )
    await db.commit()

    assert adj.journal_id is None          # tidak ada rupiah -> tidak ada jurnal
    level = await _level(db, absolut.id)
    assert Decimal(str(level.quantity)) == Decimal("12")
    assert Decimal(str(level.avg_cost)) == Decimal("0")
    assert await _saldo(db, company.id, "1-1400") == Decimal("0")


# ------------------------------------------------------- hitungan lengkap

async def test_produk_tidak_tercantum_tidak_disentuh(db):
    """Bawaan aman: yang tidak dihitung tidak ikut dinolkan."""
    company, wh, chivas, absolut = await _setup(db)
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[
            {"product_id": chivas.id, "qty_dus": "5", "qty_botol": "0",
             "modal_per_dus": "1800000"},
            {"product_id": absolut.id, "qty_dus": "2", "qty_botol": "0"},
        ],
    )
    await db.commit()

    # Opname berikutnya hanya menyebut Chivas.
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opname",
        lines_in=[{"product_id": chivas.id, "qty_dus": "4", "qty_botol": "0"}],
    )
    await db.commit()

    assert Decimal(str((await _level(db, absolut.id)).quantity)) == Decimal("24")


async def test_hitungan_lengkap_menolkan_yang_tidak_tercantum(db):
    """Dengan pilihan eksplisit, yang tidak dihitung memang dianggap habis."""
    company, wh, chivas, absolut = await _setup(db)
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[
            {"product_id": chivas.id, "qty_dus": "5", "qty_botol": "0",
             "modal_per_dus": "1800000"},
            {"product_id": absolut.id, "qty_dus": "2", "qty_botol": "0"},
        ],
    )
    await db.commit()

    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opname", hitungan_lengkap=True,
        lines_in=[{"product_id": chivas.id, "qty_dus": "5", "qty_botol": "0"}],
    )
    await db.commit()

    assert Decimal(str((await _level(db, absolut.id)).quantity)) == Decimal("0")
    assert Decimal(str((await _level(db, chivas.id)).quantity)) == Decimal("120")


# ------------------------------------------------------------- invarian inti

async def test_valuasi_cocok_dengan_saldo_persediaan(db):
    """Valuasi stok harus cocok SAMPAI SEN dengan akun Persediaan di jurnal.

    Skenario sengaja memakai angka yang tidak bulat dan mencampur stok awal,
    penambahan bermodal lain, pengurangan, dan barang gratis.
    """
    company, wh, chivas, absolut = await _setup(db)

    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[
            # 101 botol senilai 7.600.000 -> 75.247,5248 per botol
            {"product_id": chivas.id, "qty_dus": "4", "qty_botol": "5",
             "modal_per_dus": "1806930"},
            {"product_id": absolut.id, "qty_dus": "1", "qty_botol": "7"},
        ],
    )
    await db.commit()

    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opname",
        lines_in=[
            {"product_id": chivas.id, "qty_dus": "3", "qty_botol": "17"},
            {"product_id": absolut.id, "qty_dus": "1", "qty_botol": "0"},
        ],
    )
    await db.commit()

    valuasi = Decimal("0")
    for produk in (chivas, absolut):
        level = await _level(db, produk.id)
        valuasi += (Decimal(str(level.quantity))
                    * Decimal(str(level.avg_cost))).quantize(Decimal("0.01"))

    assert valuasi == await _saldo(db, company.id, "1-1400")


async def test_mutasi_stok_bertanda_dan_tertaut_ke_dokumen(db):
    company, wh, chivas, _ = await _setup(db)
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "10", "qty_botol": "0",
                   "modal_per_dus": "1800000"}],
    )
    await db.commit()
    adj = await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opname",
        lines_in=[{"product_id": chivas.id, "qty_dus": "9", "qty_botol": "0"}],
    )
    await db.commit()

    m = (await db.execute(
        select(StockMovement).where(StockMovement.ref_id == adj.id)
    )).scalar_one()
    assert m.direction == "adjustment"
    assert Decimal(str(m.quantity)) == Decimal("-24")   # bertanda, bukan 24
    assert m.ref_type == "stock_adjustment"


# ------------------------------------------------------------------ validasi

async def test_produk_ganda_ditolak(db):
    company, wh, chivas, _ = await _setup(db)
    with pytest.raises(PenyesuaianError, match="hanya boleh muncul sekali"):
        await hitung_penyesuaian(
            db, company_id=company.id, warehouse_id=wh.id,
            lines_in=[
                {"product_id": chivas.id, "qty_dus": "1", "qty_botol": "0"},
                {"product_id": chivas.id, "qty_dus": "0", "qty_botol": "4"},
            ],
        )


async def test_hitungan_negatif_ditolak(db):
    company, wh, chivas, _ = await _setup(db)
    with pytest.raises(PenyesuaianError, match="tidak boleh negatif"):
        await hitung_penyesuaian(
            db, company_id=company.id, warehouse_id=wh.id,
            lines_in=[{"product_id": chivas.id, "qty_dus": "-1",
                       "qty_botol": "0"}],
        )


async def test_tanpa_selisih_ditolak(db):
    """Menyimpan dokumen tanpa efek apa pun hanya mengotori riwayat."""
    company, wh, chivas, _ = await _setup(db)
    await create_and_post_adjustment(
        db, company_id=company.id, user_id=None, on_date=date.today(),
        warehouse_id=wh.id, mode="opening",
        lines_in=[{"product_id": chivas.id, "qty_dus": "5", "qty_botol": "0",
                   "modal_per_dus": "1800000"}],
    )
    await db.commit()

    with pytest.raises(PenyesuaianError, match="Tidak ada selisih"):
        await create_and_post_adjustment(
            db, company_id=company.id, user_id=None, on_date=date.today(),
            warehouse_id=wh.id, mode="opname",
            lines_in=[{"product_id": chivas.id, "qty_dus": "5",
                       "qty_botol": "0"}],
        )


async def test_mode_salah_ditolak(db):
    company, wh, chivas, _ = await _setup(db)
    with pytest.raises(PenyesuaianError, match="Mode harus"):
        await create_and_post_adjustment(
            db, company_id=company.id, user_id=None, on_date=date.today(),
            warehouse_id=wh.id, mode="koreksi",
            lines_in=[{"product_id": chivas.id, "qty_dus": "1",
                       "qty_botol": "0"}],
        )


async def test_pratinjau_tidak_menyimpan_apa_pun(db):
    """Pratinjau harus benar-benar hanya menghitung."""
    company, wh, chivas, _ = await _setup(db)
    hitung = await hitung_penyesuaian(
        db, company_id=company.id, warehouse_id=wh.id,
        lines_in=[{"product_id": chivas.id, "qty_dus": "15", "qty_botol": "11",
                   "modal_per_dus": "1800000"}],
    )
    assert hitung["lines"][0]["counted_display"] == "15 dus 11 botol"
    assert hitung["lines"][0]["qty_diff"] == Decimal("371")

    assert (await db.execute(select(StockAdjustment))).first() is None
    assert (await db.execute(select(StockMovement))).first() is None
    assert await _level(db, chivas.id) is None
