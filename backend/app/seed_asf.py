"""Seed khusus PT ASF — diturunkan dari ASF_MASTER_DATA.xlsx.

Menggantikan seed generic dengan:
- Bagan Akun (CoA) yang cocok dengan akun beban riil ASF.
- Master produk (SKU) lengkap dengan modal & harga jual nyata.
- Master customer hasil ekstraksi dari sheet penjualan.
- Supplier contoh, gudang, peran, dan user admin.
- Saldo stok awal (opsional) supaya HPP langsung jalan.

Skema TIDAK lagi dibuat di sini — itu tugas Alembic. Jalankan berurutan:

    alembic upgrade head          # buat/ubah tabel
    python -m app.seed_asf        # isi data awal

Aman dijalankan ulang: kalau company sudah ada, proses dilewati.

Reset TOTAL (buang semua data, termasuk master — dulu dipakai saat data masih
dummy):  alembic downgrade base && alembic upgrade head && python -m app.seed_asf
"""
import asyncio
from decimal import Decimal
from sqlalchemy import select
from .core.config import settings
from .core.database import SessionLocal
from .core.security import hash_password
from .models import (
    Company, Warehouse, User, Role, UserRole, Account,
    Contact, Product, StockLevel,
)
from .services.product_service import slug_sku
from .services.units import base_price_from_pack

COMPANY_NAME = "PT ASF"

# (code, name, type, normal_balance) — disusun mengikuti P&L & cashflow ASF.
COA = [
    # ASET
    ("1-1000", "Kas", "asset", "debit"),
    ("1-1100", "Bank", "asset", "debit"),
    ("1-1110", "Bank BCA - Silo", "asset", "debit"),
    ("1-1120", "Bank OCBC - Silo", "asset", "debit"),
    ("1-1200", "Piutang Usaha", "asset", "debit"),
    ("1-1300", "PPN Masukan", "asset", "debit"),
    ("1-1400", "Persediaan Barang", "asset", "debit"),
    ("1-1500", "Dana Darurat", "asset", "debit"),
    ("1-2000", "Aset Tetap - Kendaraan", "asset", "debit"),
    ("1-2900", "Akumulasi Penyusutan Kendaraan", "asset", "credit"),
    # LIABILITAS
    ("2-1000", "Utang Usaha", "liability", "credit"),
    ("2-1300", "PPN Keluaran", "liability", "credit"),
    ("2-2000", "Utang Pajak", "liability", "credit"),
    ("2-3000", "Utang Investor", "liability", "credit"),
    # EKUITAS
    ("3-1000", "Modal - Silo", "equity", "credit"),
    ("3-1100", "Modal - Abay", "equity", "credit"),
    ("3-1200", "Modal - Fei", "equity", "credit"),
    ("3-1300", "Modal - Ido", "equity", "credit"),
    ("3-2000", "Laba Ditahan", "equity", "credit"),
    ("3-3000", "Prive / Dividen", "equity", "debit"),
    # PENDAPATAN
    ("4-1000", "Pendapatan Penjualan", "income", "credit"),
    ("4-1100", "Retur Penjualan", "income", "debit"),
    ("4-1200", "Diskon Penjualan", "income", "debit"),
    ("4-2000", "Pendapatan Lain", "income", "credit"),
    # HPP
    ("5-1000", "Harga Pokok Penjualan", "expense", "debit"),
    # BEBAN OPERASIONAL (akun riil ASF)
    ("6-1000", "Beban Gaji & Bonus", "expense", "debit"),
    ("6-1100", "Beban Komisi", "expense", "debit"),
    ("6-2000", "Beban Ekspedisi & Ongkir", "expense", "debit"),
    ("6-2100", "Beban Entertainment & Nongkrong", "expense", "debit"),
    ("6-2200", "Beban Representasi", "expense", "debit"),
    ("6-2300", "Beban Perawatan Kendaraan", "expense", "debit"),
    ("6-2400", "Beban Bensin", "expense", "debit"),
    ("6-2500", "Beban Perlengkapan Kantor", "expense", "debit"),
    ("6-2600", "Beban Listrik, Air & Internet", "expense", "debit"),
    ("6-2700", "Beban Penyusutan Kendaraan", "expense", "debit"),
    ("6-2900", "Beban Operasional Lainnya", "expense", "debit"),
    ("6-3000", "Beban Sewa", "expense", "debit"),
    ("6-4000", "Beban Investor", "expense", "debit"),
    ("6-5000", "Beban Piutang Tidak Tertagih", "expense", "debit"),
]

# (name, modal_per_dus, isi_per_dus) — dikonfirmasi client 2026-08-13,
# ditambah Absolut Vodka & Captain Morgan Apple pada 2026-08-18.
#
# PENTING: kolom modal adalah **harga per DUS**, bukan per botol. Sistem membagi
# ke per-botol sendiri (lihat services/units.py). Salah membaca kolom ini sebagai
# harga per botol membuat HPP & valuasi salah 12-48x.
#
# Isi per dus: Chivas 200ml = 24, Robinson Vodka = 48, sisanya 12.
# SKU tidak diketik siapa pun — dibuat otomatis dari nama.
PRODUCTS = [
    # Urutan mengikuti daftar resmi client (alfabetis) supaya bisa dicocokkan
    # baris per baris saat client mengirim pembaruan berikutnya.
    #
    # Absolut Vodka bermodal 0 karena barangnya didapat GRATIS — ini angka
    # yang benar, bukan data yang belum diisi. Jangan "diperbaiki" dengan
    # menebak harga pasar. Akibat yang sudah diketahui & diterima client:
    # laporan Komisi & GPM (yang memakai modal ACUAN dari master) menghitung
    # marginnya 100%, sehingga komisi sales atas barang ini paling besar.
    # HPP di Laba Rugi TIDAK terpengaruh — angka itu dari avg_cost hasil
    # pembelian nyata.
    ("Absolut Vodka",                       0, 12),
    ("Azul Reposado",              30_000_000, 12),
    ("Captain Morgan Apple",        1_740_000, 12),
    ("Captain Morgan Spiced Gold",  1_600_000, 12),
    ("Chivas 200ml",                1_800_000, 24),
    ("Chivas Regal 12 YO",          3_700_000, 12),
    ("Codigo Reposado",             8_500_000, 12),
    ("Glenfiddich 12 YO",           5_000_000, 12),
    ("Glenlivet 12 YO",             5_000_000, 12),
    ("Hennessy VSOP",               7_000_000, 12),
    ("Jack Daniel's",               3_200_000, 12),
    ("Jameson",                     3_200_000, 12),
    ("Jose Cuervo",                 2_800_000, 12),
    # Catatan: client menyebut JW Black = 2.800.000, sama dengan JW Red.
    # Sudah dikonfirmasi lewat daftar resmi client; kalau ternyata salah ketik,
    # cukup ubah angka di baris ini lalu jalankan ulang seed.
    ("JW Black Label",              2_800_000, 12),
    ("JW Red Label",                2_800_000, 12),
    ("Macallan 12 Double Cask",    13_500_000, 12),
    ("Macallan 12 Sherry Oak",     14_000_000, 12),
    ("Macallan 12 Triple Cask",    13_500_000, 12),
    ("Mansion Vodka",               1_100_000, 12),
    ("Mansion Whisky",              1_100_000, 12),
    ("Martell Noblige",             6_000_000, 12),
    ("Martell VSOP",                6_000_000, 12),
    ("Robinson Vodka",              1_300_000, 48),
    ("Singleton 12 Glenord",        5_500_000, 12),
    ("Singleton 12 Lucious Nectar", 4_000_000, 12),
]

# Customer riil hasil ekstraksi (noise seperti RETUR/SAMPLING dibuang).
CUSTOMERS = [
    "AGUNG", "AGUS MALANG", "ALDI", "ANDRE", "Atal", "BANG ADE", "BOY", "BPN",
    "BR", "BUDI", "Bpk Regar", "Capella Cafe", "Cempal", "DENATSU", "DOYOK",
    "EXA", "GILANG", "HARYONO", "INKOPAD", "JOSUA", "KIEL SORONG", "KIMOB",
    "KO RICI", "KOMANG", "PABLO", "PAPPING", "PASKAH", "PETER", "PK", "Padot",
    "RONI", "RUSDI", "STEVE", "TAHAN MARPAUNG", "TIAN", "Tepen",
    "Bapak Mangatur", "Gio", "Indrajayapura", "Ivan", "Jason", "Jorj", "Luis",
    "Marko", "Okii", "Polmer", "Rafli", "Rama", "Reyhan", "Romian Cafe",
    "Sibarani", "Steven", "Tulang Ruli Marbun", "Victor Bogor",
]

SUPPLIERS = ["EXA (Distributor)", "Supplier Pengadaan Umum"]

ROLES = [
    ("owner", "Owner/Admin"),
    ("finance", "Finance/Akuntan"),
    ("sales", "Sales"),
    ("warehouse", "Gudang"),
    ("viewer", "Viewer"),
]


async def run(seed_opening_stock: bool = False):
    # Tabel dibuat oleh `alembic upgrade head` (dijalankan entrypoint.sh lebih
    # dulu), bukan di sini. Menambah model baru WAJIB punya revisi Alembik —
    # jangan mengandalkan seed seperti dulu.
    async with SessionLocal() as db:
        existing = (await db.execute(
            select(Company).where(Company.name == COMPANY_NAME)
        )).scalar_one_or_none()
        if existing:
            print("Seed ASF sudah ada, dilewati.")
            return

        company = Company(name=COMPANY_NAME, currency="IDR",
                          costing_method="average")
        db.add(company)
        await db.flush()

        wh = Warehouse(company_id=company.id, code="GD1",
                       name="Gudang Utama", is_default=True)
        db.add(wh)

        for code, name, type_, nb in COA:
            db.add(Account(company_id=company.id, code=code, name=name,
                           type=type_, normal_balance=nb))

        roles = {}
        for name, label in ROLES:
            r = Role(name=name, label=label)
            db.add(r)
            roles[name] = r

        for name in CUSTOMERS:
            db.add(Contact(company_id=company.id, type="customer", name=name,
                           payment_term_days=30))
        for name in SUPPLIERS:
            db.add(Contact(company_id=company.id, type="supplier", name=name,
                           payment_term_days=14))

        await db.flush()

        products: list[Product] = []
        for name, modal_per_dus, pack_size in PRODUCTS:
            pack_modal = Decimal(modal_per_dus)
            p = Product(
                company_id=company.id, sku=slug_sku(name), name=name,
                kind="good",
                # Stok & HPP dalam BOTOL; dus hanya satuan input/tampilan.
                unit="botol", pack_unit="dus", pack_size=pack_size,
                pack_purchase_price=pack_modal,
                purchase_price=base_price_from_pack(pack_modal, pack_size),
                # Harga jual TIDAK di master: ditentukan per customer saat faktur.
                sale_price=Decimal("0"),
                income_account_id=None, inventory_account_id=None,
                cogs_account_id=None,
            )
            db.add(p)
            products.append(p)
        await db.flush()

        if seed_opening_stock:
            # avg_cost per BOTOL (purchase_price sudah per botol).
            for p in products:
                db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                                  quantity=Decimal("0"),
                                  avg_cost=p.purchase_price))

        admin = User(
            company_id=company.id, email=settings.SEED_ADMIN_EMAIL,
            full_name="Administrator ASF",
            password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
        )
        db.add(admin)
        await db.flush()
        db.add(UserRole(user_id=admin.id, role_id=roles["owner"].id))

        await db.commit()
        print(f"Seed ASF selesai. {len(COA)} akun, {len(PRODUCTS)} produk, "
              f"{len(CUSTOMERS)} customer.")
        print(f"Login: {settings.SEED_ADMIN_EMAIL} / {settings.SEED_ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(run())
