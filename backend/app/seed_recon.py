"""Membuat tabel bank_recon_marks (idempotent).

Jalankan sekali setelah deploy paket ini:
    python -m app.seed_recon
"""
import asyncio
from .core.database import engine
from .models import Base


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tabel bank_recon_marks siap. Fitur Rekonsiliasi Bank aktif.")


if __name__ == "__main__":
    asyncio.run(run())
