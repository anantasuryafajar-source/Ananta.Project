"""Menambahkan kolom reset_token & reset_expires ke tabel users (idempotent).

Jalankan sekali setelah deploy:
    python -m app.seed_reset_token
"""
import asyncio
from sqlalchemy import text
from .core.database import engine


async def run():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64)"))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_expires TIMESTAMPTZ"))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_users_reset_token ON users (reset_token)"))
    print("Kolom reset_token & reset_expires siap. Fitur Lupa Kata Sandi aktif.")


if __name__ == "__main__":
    asyncio.run(run())
