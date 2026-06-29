"""Seed khusus PT ASF — diturunkan dari ASF_MASTER_DATA.xlsx.

Menggantikan seed generic dengan:
- Bagan Akun (CoA) yang cocok dengan akun beban riil ASF.
- Master produk (SKU) lengkap dengan modal & harga jual nyata.
- Master customer hasil ekstraksi dari sheet penjualan.
- Supplier contoh, gudang, peran, dan user admin.
- Saldo stok awal (opsional) supaya HPP langsung jalan.

Jalankan:  python -m app.seed_asf
Aman dijalankan ulang: kalau company sudah ada, proses dilewati.
"""
import asyncio
from decimal import Decimal
from sqlalchemy import select
from .core.config import settings
from .core.database import engine, SessionLocal
from .core.security import hash_password
from .models import (
    Base, Company, Warehouse, User, Role, UserRole, Account,
    Contact, Product, StockLevel,
)

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

# (sku_code, name, modal/purchase_price, harga_jual/sale_price) — dari sheet KOMISI.
PRODUCTS = [
    ("CM",   "Captain Morgan Spiced Rum",   1600000, 2500000),
    ("RBV",  "Robinson Vodka",              1300000, 3000000),
    ("B",    "JW Black Label 750ml",        3700000, 4350000),
    ("CHO",  "Chivas Regal 12 YO 750ml",    3700000, 4400000),
    ("R",    "JW Red Label 750ml",          2800000, 3600000),
    ("M",    "Martell VSOP",                6000000, 7800000),
    ("H",    "Hennessy VSOP EU",            6500000, 8300000),
    ("JMS30","Jameson 750ml",               3000000, 3700000),
    ("JDO",  "Jack Daniel's",               3200000, 4000000),
    ("SG",   "Singleton 12 Glenord",        5600000, 7000000),
    ("GF",   "Glenfiddich 12 YO",           5500000, 6900000),
    ("JS",   "Jose Cuervo Tequila",         2800000, 4000000),
    ("GLV",  "Glenlivet 12 YO",             5000000, 6500000),
    ("MCDC", "Macallan 12 Double Cask",    13500000,17000000),
    ("MCTC", "Macallan 12 Triple Cask",    13500000,17000000),
    ("MCSO", "Macallan 12 Sherry Oak",     14000000,18000000),
    ("MTN",  "Martell Noblige",             6000000, 8000000),
    ("SGN",  "Singleton 12 Lucious Nectar", 4000000, 6500000),
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        for sku, name, modal, hj in PRODUCTS:
            p = Product(
                company_id=company.id, sku=sku, name=name, kind="good",
                unit="botol", sale_price=Decimal(hj), purchase_price=Decimal(modal),
                income_account_id=None, inventory_account_id=None,
                cogs_account_id=None,
            )
            db.add(p)
            products.append(p)
        await db.flush()

        if seed_opening_stock:
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
