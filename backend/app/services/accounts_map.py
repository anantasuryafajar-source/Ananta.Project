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


# Akun yang BOLEH dibuat otomatis saat pertama dibutuhkan.
#
# Alasannya: bagan akun perusahaan yang sudah berjalan di-seed sebelum fitur
# penyesuaian stok ada, jadi akun-akun ini tidak akan pernah ada di sana.
# Menambahkannya lewat migrasi berarti setiap database baru maupun lama harus
# diurus terpisah; membuatnya saat dibutuhkan bersifat idempoten dan tidak
# mungkin gagal separuh jalan. Yang dibuat hanya BARIS BAGAN AKUN — tidak ada
# jurnal, saldo, atau apa pun yang menyentuh angka.
AUTO_CREATE: dict[str, tuple[str, str, str, str]] = {
    # kunci: (kode, nama, tipe, saldo normal)
    "inventory_opening": ("3-4000", "Saldo Awal Persediaan", "equity", "credit"),
    "inventory_variance": ("5-2000", "Selisih Persediaan", "expense", "debit"),
    # Uang muka pelanggan (DP): kewajiban menyerahkan barang, BUKAN pendapatan.
    # Tanpa akun ini DP tidak punya tempat yang benar dan pasti akan
    # diakal-akali jadi sesuatu yang merusak neraca.
    "customer_advance": ("2-1500", "Uang Muka Pelanggan", "liability", "credit"),
    # Komisi yang sudah disepakati tapi belum dibayar. Tanpa akun ini,
    # kewajiban itu tidak muncul di mana pun dan laba terlihat lebih besar
    # dari kenyataan.
    "commission_payable": ("2-1600", "Utang Komisi", "liability", "credit"),
}


async def ensure_account(db: AsyncSession, company_id: str, key: str) -> str:
    """id akun untuk `key`; dibuat lebih dulu bila belum ada di CoA perusahaan."""
    try:
        code, name, tipe, normal = AUTO_CREATE[key]
    except KeyError:
        raise KeyError(
            f"'{key}' bukan akun yang boleh dibuat otomatis. "
            f"Pilihan: {', '.join(sorted(AUTO_CREATE))}."
        ) from None

    acc_id = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if acc_id:
        return acc_id

    akun = Account(company_id=company_id, code=code, name=name,
                   type=tipe, normal_balance=normal, is_active=True)
    db.add(akun)
    await db.flush()
    return akun.id
