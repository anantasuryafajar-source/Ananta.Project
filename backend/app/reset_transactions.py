"""Reset DATA TRANSAKSI production (master tetap: produk, kontak, akun, gudang, user).

Dipakai sekali sebelum go-live untuk membuang data percobaan:
    python -m app.reset_transactions

⚠️ Destruktif untuk transaksi. Jalankan hanya bila yakin (idealnya sesudah pg_dump).
Setelah ini, muat data asli: `python -m app.seed_history` (histori 17 bulan),
lalu koreksi master via Import Excel di menu Produk/Kontak bila perlu.
"""
import asyncio
from sqlalchemy import text
from .core.database import engine

TABLES = [
    "journal_entries", "journals",
    "payments_received", "invoice_lines", "invoices",
    "payments_made", "bill_lines", "bills",
    "purchase_order_lines", "purchase_orders",
    "sales_order_lines", "sales_orders",
    "courier_expenses", "investor_payouts", "expenses", "employee_loans",
    "stock_movements", "stock_levels",
    "document_sequences", "audit_logs",
]


async def run():
    async with engine.begin() as conn:
        existing = []
        for t in TABLES:
            ok = (await conn.execute(text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = :t"), {"t": t})).scalar()
            if ok:
                existing.append(t)
        if not existing:
            print("Tidak ada tabel transaksi ditemukan.")
            return
        await conn.execute(text(
            f'TRUNCATE TABLE {", ".join(existing)} RESTART IDENTITY CASCADE'))
        print(f"Reset selesai — {len(existing)} tabel transaksi dikosongkan:")
        for t in existing:
            print("  -", t)
        print("Master (produk/kontak/akun/gudang/user/investor) tetap utuh.")


if __name__ == "__main__":
    asyncio.run(run())
