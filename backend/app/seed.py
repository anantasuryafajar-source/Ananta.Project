"""Seed data awal: perusahaan, peran, admin, gudang default, dan CoA Indonesia.

Jalankan: python -m app.seed
Untuk dev cepat, fungsi ini juga create_all tabel bila belum ada.
"""
import asyncio
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from .core.config import settings
from .core.database import engine, SessionLocal
from .core.security import hash_password
from .models import (
    Base, Company, Warehouse, User, Role, UserRole, Account,
)

# CoA standar Indonesia (ringkas namun cukup untuk transaksi inti).
# (code, name, type, normal_balance)
COA = [
    ("1-1000", "Kas", "asset", "debit"),
    ("1-1100", "Bank", "asset", "debit"),
    ("1-1200", "Piutang Usaha", "asset", "debit"),
    ("1-1300", "PPN Masukan", "asset", "debit"),
    ("1-1400", "Persediaan Barang", "asset", "debit"),
    ("1-2000", "Aset Tetap", "asset", "debit"),
    ("2-1000", "Utang Usaha", "liability", "credit"),
    ("2-1300", "PPN Keluaran", "liability", "credit"),
    ("2-2000", "Utang Pajak", "liability", "credit"),
    ("3-1000", "Modal Pemilik", "equity", "credit"),
    ("3-2000", "Laba Ditahan", "equity", "credit"),
    ("4-1000", "Pendapatan Penjualan", "income", "credit"),
    ("4-2000", "Pendapatan Lain", "income", "credit"),
    ("5-1000", "Harga Pokok Penjualan", "expense", "debit"),
    ("6-1000", "Beban Gaji", "expense", "debit"),
    ("6-2000", "Beban Operasional", "expense", "debit"),
    ("6-3000", "Beban Sewa", "expense", "debit"),
]

ROLES = [
    ("owner", "Owner/Admin"),
    ("finance", "Finance/Akuntan"),
    ("sales", "Sales"),
    ("warehouse", "Gudang"),
    ("viewer", "Viewer"),
]


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        existing = (await db.execute(
            select(Company).where(Company.name == settings.SEED_COMPANY_NAME)
        )).scalar_one_or_none()
        if existing:
            print("Seed sudah ada, lewati.")
            return

        company = Company(name=settings.SEED_COMPANY_NAME, currency="IDR",
                          costing_method="average")
        db.add(company)
        await db.flush()

        db.add(Warehouse(company_id=company.id, code="GD1",
                         name="Gudang Utama", is_default=True))

        for code, name, type_, nb in COA:
            db.add(Account(company_id=company.id, code=code, name=name,
                           type=type_, normal_balance=nb))

        roles = {}
        for name, label in ROLES:
            r = Role(name=name, label=label)
            db.add(r)
            roles[name] = r
        await db.flush()

        admin = User(
            company_id=company.id, email=settings.SEED_ADMIN_EMAIL,
            full_name="Administrator",
            password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
        )
        db.add(admin)
        await db.flush()
        db.add(UserRole(user_id=admin.id, role_id=roles["owner"].id))

        await db.commit()
        print(f"Seed selesai. Login: {settings.SEED_ADMIN_EMAIL} / "
              f"{settings.SEED_ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(run())
