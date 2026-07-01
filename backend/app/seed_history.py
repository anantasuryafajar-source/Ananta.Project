"""Runner backfill histori. Jalankan SETELAH seed_asf & (opsional) seed_master.

    python -m app.import_history extract /path/ASF_MASTER_DATA.xlsx
    python -m app.seed_history

Idempotent: jurnal historis yang sudah ada akan dilewati.
"""
import asyncio
from sqlalchemy import select
from .core.database import SessionLocal
from .models import Company
from .import_history import post_history


async def run():
    async with SessionLocal() as db:
        company = (await db.execute(select(Company))).scalars().first()
        if company is None:
            print("Belum ada perusahaan. Jalankan `python -m app.seed_asf` dulu.")
            return
        result = await post_history(db, company.id)
        print(f"Backfill histori selesai: {result}")


if __name__ == "__main__":
    asyncio.run(run())
