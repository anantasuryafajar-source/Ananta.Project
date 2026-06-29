"""Resolusi akun default per perusahaan berdasarkan kode CoA standar."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Account

# Kode akun default (lihat seed.py)
DEFAULT_CODES = {
    "ar": "1-1200",          # Piutang Usaha
    "inventory": "1-1400",   # Persediaan Barang
    "cogs": "5-1000",        # Harga Pokok Penjualan
    "sales": "4-1000",       # Pendapatan Penjualan
    "vat_out": "2-1300",     # PPN Keluaran (utang)
    "vat_in": "1-1300",      # PPN Masukan (aset)
    "cash": "1-1000",        # Kas
    "bank": "1-1100",        # Bank
    "ap": "2-1000",          # Utang Usaha
}


async def code_to_id(db: AsyncSession, company_id: str) -> dict[str, str]:
    rows = (
        await db.execute(
            select(Account.code, Account.id).where(Account.company_id == company_id)
        )
    ).all()
    by_code = {code: _id for code, _id in rows}
    return {key: by_code[code] for key, code in DEFAULT_CODES.items() if code in by_code}
