"""Migrasi + seed dari ASF_MASTER_DATA.

Fungsi:
  1) create_all  -> membuat tabel modul baru (courier, PO, SO) bila belum ada.
  2) memastikan minimal satu gudang default.
  3) upsert produk & kontak dari seed_data/*.json (hasil import_master_data extract).

Cara pakai (jalankan SETELAH `python -m app.seed_asf`):
    python -m app.import_master_data extract /path/ASF_MASTER_DATA.xlsx
    python -m app.seed_master

Idempotent: aman dijalankan berulang (produk dicocokkan by SKU, kontak by nama).
"""
import asyncio
from sqlalchemy import select
from .core.database import engine, SessionLocal
from .models import Base, Company, Warehouse
from .import_master_data import seed_from_master


async def run():
    # 1) buat tabel yang belum ada (termasuk modul distribusi baru)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        company = (await db.execute(select(Company))).scalars().first()
        if company is None:
            print("Belum ada perusahaan. Jalankan `python -m app.seed_asf` dulu.")
            return

        # 2) pastikan ada gudang default
        wh = (await db.execute(
            select(Warehouse).where(Warehouse.company_id == company.id)
        )).scalars().first()
        if wh is None:
            db.add(Warehouse(company_id=company.id, code="GD1",
                             name="Gudang Utama", is_default=True))
            await db.commit()
            print("Gudang default dibuat.")

        # 3) upsert produk & kontak dari master data
        added = await seed_from_master(db, company.id)
        print(f"Seed master selesai: +{added['products']} produk, "
              f"+{added['contacts']} kontak (yang sudah ada dilewati).")


if __name__ == "__main__":
    asyncio.run(run())
