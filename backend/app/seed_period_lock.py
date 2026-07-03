"""Menambahkan kolom period_lock_date ke tabel companies (idempotent).

Jalankan sekali setelah deploy paket ini:
    python -m app.seed_period_lock
"""
import asyncio
from sqlalchemy import text
from .core.database import engine


async def run():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS period_lock_date DATE"))
    print("Kolom period_lock_date siap. Fitur Tutup Buku aktif.")


if __name__ == "__main__":
    asyncio.run(run())
