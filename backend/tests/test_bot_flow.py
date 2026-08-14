"""Tes alur BOT sungguhan: dari teks perintah sampai jurnal & stok di database.

Sebelum file ini, `app/bot/handlers.py` (1.600 baris) tidak tertutup tes sama
sekali karena butuh paket `telegram`. Akibatnya sebuah bug parah lolos: satuan
sudah diparse dengan benar tetapi DIBUANG di langkah konfirmasi, sehingga
"10 dus" tercatat 10 botol — salah 12-48x dan langsung masuk jurnal.

Yang diuji di sini adalah perintah yang menulis ke buku besar: /pengadaan,
/jual, dan /tambah_produk. Bot memakai `SessionLocal` sendiri (bukan sesi dari
fixture), jadi modul itu di-patch ke database uji.
"""
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.bot import handlers as H
from app.models import (
    Account, Bill, Company, Contact, Invoice, Product, Role, StockLevel,
    TelegramLink, User, UserRole, Warehouse,
)
from app.services.accounts_map import DEFAULT_CODES
from app.services.units import format_qty

CHAT_ID = 987654321

_TYPES = {
    "ar": "asset", "inventory": "asset", "cogs": "expense", "sales": "income",
    "vat_out": "liability", "vat_in": "asset", "cash": "asset",
    "bank": "asset", "ap": "liability",
}


class _Pesan:
    """Pengganti telegram.Message — merekam balasan bot."""

    def __init__(self, text: str, balasan: list[str]):
        self.text = text
        self._balasan = balasan

    async def reply_text(self, teks, *a, **k):
        self._balasan.append(teks)


class _Update:
    """Pengganti telegram.Update seperlunya saja."""

    def __init__(self, text: str, balasan: list[str]):
        self.message = _Pesan(text, balasan)
        self.effective_chat = type("Chat", (), {"id": CHAT_ID})()


@pytest_asyncio.fixture
async def bot(monkeypatch):
    """Database uji + akun bot tertaut. Mengembalikan pengirim pesan."""
    # StaticPool: satu koneksi dipakai bersama, supaya SessionLocal milik bot
    # melihat data yang sama dengan fixture.
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(H, "SessionLocal", Session)

    async with Session() as db:
        company = Company(name="PT ASF", currency="IDR", costing_method="average")
        db.add(company)
        await db.flush()
        for key, code in DEFAULT_CODES.items():
            kind = _TYPES[key]
            db.add(Account(
                company_id=company.id, code=code, name=key, type=kind,
                normal_balance="credit" if kind in ("liability", "income") else "debit",
            ))
        wh = Warehouse(company_id=company.id, code="GD1", name="Gudang Utama",
                       is_default=True)
        sup = Contact(company_id=company.id, type="supplier", name="EXA",
                      payment_term_days=14)
        cust = Contact(company_id=company.id, type="customer", name="Bpk Regar",
                       payment_term_days=30)
        prod = Product(
            company_id=company.id, sku="CHIVAS-200ML", name="Chivas 200ml",
            kind="good", unit="botol", pack_unit="dus", pack_size=24,
            pack_purchase_price=Decimal("1800000"),
            purchase_price=Decimal("75000"),
        )
        role = Role(name="owner", label="Owner")
        db.add_all([wh, sup, cust, prod, role])
        await db.flush()
        user = User(company_id=company.id, email="admin@ananta.local",
                    full_name="Admin", password_hash="x")
        db.add(user)
        await db.flush()
        db.add_all([
            UserRole(user_id=user.id, role_id=role.id),
            TelegramLink(user_id=user.id, telegram_chat_id=CHAT_ID, is_active=True),
            StockLevel(product_id=prod.id, warehouse_id=wh.id,
                       quantity=Decimal("240"), avg_cost=Decimal("75000")),
        ])
        await db.commit()

    balasan: list[str] = []

    async def kirim(handler, teks: str) -> str:
        """Kirim satu pesan ke handler, kembalikan balasan terakhir bot."""
        balasan.clear()
        await handler(_Update(teks, balasan), None)
        return balasan[-1] if balasan else ""

    yield kirim, Session
    await engine.dispose()


# ------------------------------------------------------------------ /pengadaan
async def test_pengadaan_satuan_dus_tidak_hilang_saat_konfirmasi(bot):
    """REGRESI UTAMA: '10 dus' harus jadi 240 botol, bukan 10.

    Bug lamanya: ringkasan konfirmasi menampilkan "10 dus" dengan benar, tetapi
    yang tersimpan hanya 10 botol karena `unit` dibuang saat menyusun input service.
    """
    kirim, Session = bot

    ringkas = await kirim(H.cmd_pengadaan, (
        "/pengadaan\n"
        "Supplier: EXA\n"
        "Catatan: kiriman susulan\n"
        "Item: CHIVAS-200ML x 10 dus @ 1800000 # 2 botol pecah\n"
        "Item: CHIVAS-200ML x 5 botol @ 80000"
    ))
    assert "10 dus" in ringkas
    assert "2 botol pecah" in ringkas          # keterangan tampil di konfirmasi

    hasil = await kirim(H.on_text, "YA")
    assert "gagal" not in hasil.lower()

    async with Session() as db:
        bill = (await db.execute(select(Bill))).scalars().one()
        assert bill.notes == "kiriman susulan"
        baris = sorted(bill.lines, key=lambda l: l.unit)   # botol, dus
        assert baris[1].unit == "dus"
        assert Decimal(str(baris[1].qty_input)) == Decimal("10")
        assert Decimal(str(baris[1].quantity)) == Decimal("240")   # 10 x 24
        assert baris[1].note == "2 botol pecah"
        assert baris[0].unit == "botol" and baris[0].note is None

        prod = (await db.execute(select(Product))).scalars().one()
        lvl = (await db.execute(select(StockLevel))).scalars().one()
        # stok awal 240 + 240 + 5
        assert Decimal(str(lvl.quantity)) == Decimal("485")
        assert format_qty(lvl.quantity, prod.pack_size) == "20 dus 5 botol"


async def test_pengadaan_menolak_baris_tanpa_satuan(bot):
    """Bot TIDAK boleh menebak satuan — pesan error harus menyebutkan sebabnya."""
    kirim, Session = bot

    balas = await kirim(H.cmd_pengadaan, (
        "/pengadaan\nSupplier: EXA\nItem: CHIVAS-200ML x 10 @ 1800000"
    ))
    assert "satuan" in balas.lower()

    async with Session() as db:
        assert (await db.execute(select(Bill))).scalars().all() == []


# ----------------------------------------------------------------------- /jual
async def test_jual_campur_dus_dan_botol(bot):
    kirim, Session = bot

    ringkas = await kirim(H.cmd_jual, (
        "/jual\n"
        "Customer: Bpk Regar\n"
        "Item: CHIVAS-200ML x 1 dus @ 2400000\n"
        "Item: CHIVAS-200ML x 5 botol @ 110000 # bonus"
    ))
    assert "1 dus" in ringkas

    hasil = await kirim(H.on_text, "YA")
    assert "gagal" not in hasil.lower()

    async with Session() as db:
        inv = (await db.execute(select(Invoice))).scalars().one()
        baris = sorted(inv.lines, key=lambda l: l.unit)
        assert Decimal(str(baris[1].quantity)) == Decimal("24")   # 1 dus
        assert baris[0].note == "bonus"
        # omzet dari satuan yang diketik: 2.400.000 + 5 x 110.000
        assert Decimal(str(inv.subtotal)) == Decimal("2950000.00")

        lvl = (await db.execute(select(StockLevel))).scalars().one()
        assert Decimal(str(lvl.quantity)) == Decimal("211")       # 240 - 29


# -------------------------------------------------------------- /tambah_produk
async def test_tambah_produk_menyimpan_modal_per_dus(bot):
    """Bug lama: harga dari bot tersimpan sebagai harga JUAL, sehingga modal
    produk selalu kosong di web."""
    kirim, Session = bot

    balas = await kirim(H.cmd_tambah_produk, (
        "/tambah_produk\n"
        "Nama: Robinson Vodka\n"
        "Isi per dus: 48\n"
        "Modal per dus: 1300000"
    ))
    assert "Tersimpan" in balas

    async with Session() as db:
        p = (await db.execute(
            select(Product).where(Product.name == "Robinson Vodka")
        )).scalar_one()
        assert p.pack_size == 48
        assert Decimal(str(p.pack_purchase_price)) == Decimal("1300000")
        assert Decimal(str(p.purchase_price)) == Decimal("27083.33")  # per botol
        assert Decimal(str(p.sale_price)) == Decimal("0")   # harga jual TIDAK diisi
        assert p.sku                                        # dibuat otomatis


async def test_tambah_produk_menolak_isi_dus_tidak_masuk_akal(bot):
    kirim, Session = bot

    balas = await kirim(H.cmd_tambah_produk, (
        "/tambah_produk\nNama: Uji\nIsi per dus: nol\nModal per dus: 100000"
    ))
    assert "isi per dus" in balas.lower()

    async with Session() as db:
        assert (await db.execute(
            select(Product).where(Product.name == "Uji")
        )).scalar_one_or_none() is None
