"""Seed pelengkap untuk modul investor/beban/kasbon (Step 2-3).

Jalankan SEKALI setelah deploy paket ini:
    python -m app.seed_extras

Fungsi (idempotent, aman diulang):
  1) create_all -> membuat tabel baru (investors, investor_payouts,
     expenses, employee_loans) bila belum ada.
  2) memastikan akun 1-1600 "Piutang Karyawan" ada di CoA (untuk kasbon).
"""
import asyncio
from sqlalchemy import select
from .core.database import engine, SessionLocal
from .models import Base, Company, Account


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        company = (await db.execute(select(Company))).scalars().first()
        if company is None:
            print("Belum ada perusahaan. Jalankan `python -m app.seed_asf` dulu.")
            return

        exists = (await db.execute(
            select(Account).where(Account.company_id == company.id,
                                  Account.code == "1-1600")
        )).scalar_one_or_none()
        if exists is None:
            db.add(Account(
                company_id=company.id, code="1-1600",
                name="Piutang Karyawan", type="asset", normal_balance="debit",
            ))
            await db.commit()
            print("Akun 1-1600 Piutang Karyawan dibuat.")
        else:
            print("Akun 1-1600 sudah ada, dilewati.")

    print("seed_extras selesai. Tabel investor/beban/kasbon siap.")


if __name__ == "__main__":
    asyncio.run(run())
