"""Helper parsing murni untuk bot (tanpa dependensi telegram / DB).

Dipisah agar bisa diuji langsung di CI.
"""
import re
from decimal import Decimal, InvalidOperation

CODE_RE = re.compile(r"^\d-\d{4}$")

# Daftar akun beban umum yang ditawarkan di alur terpandu (nomor 1..N).
EXPENSE_ACCOUNTS = [
    ("6-2400", "Bensin"),
    ("6-2000", "Ekspedisi & Ongkir"),
    ("6-2100", "Entertainment & Nongkrong"),
    ("6-2300", "Perawatan Kendaraan"),
    ("6-2500", "Perlengkapan Kantor"),
    ("6-2600", "Listrik, Air & Internet"),
    ("6-1000", "Gaji & Bonus"),
    ("6-3000", "Sewa"),
    ("6-2900", "Operasional Lainnya"),
]
DEFAULT_EXPENSE_CODE = "6-2900"

PAYMENT_ACCOUNTS = [
    ("1-1000", "Kas"),
    ("1-1110", "Bank BCA"),
    ("1-1120", "Bank OCBC"),
]
DEFAULT_PAID_CODE = "1-1000"

# Kata kunci -> kode akun beban (untuk mode sekali-kirim).
_EXPENSE_KEYWORDS = {
    "bensin": "6-2400",
    "solar": "6-2400",
    "ongkir": "6-2000",
    "ekspedisi": "6-2000",
    "kirim": "6-2000",
    "entertain": "6-2100",
    "nongkrong": "6-2100",
    "representasi": "6-2200",
    "kendaraan": "6-2300",
    "servis": "6-2300",
    "perawatan": "6-2300",
    "perlengkapan": "6-2500",
    "kantor": "6-2500",
    "listrik": "6-2600",
    "air": "6-2600",
    "internet": "6-2600",
    "gaji": "6-1000",
    "bonus": "6-1000",
    "komisi": "6-1100",
    "sewa": "6-3000",
    "lainnya": "6-2900",
}

_PAYMENT_KEYWORDS = {
    "kas": "1-1000",
    "tunai": "1-1000",
    "cash": "1-1000",
    "bca": "1-1110",
    "ocbc": "1-1120",
    "bank": "1-1100",
}


def parse_amount(text: str):
    """Ubah teks jumlah jadi Decimal > 0. None bila tidak valid."""
    cleaned = (text or "").replace(".", "").replace(",", "").replace(" ", "").strip()
    if cleaned == "":
        return None
    try:
        val = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return val if val > 0 else None


def resolve_expense_account(value: str):
    """Kode akun beban dari kode langsung atau kata kunci. None bila tak dikenal."""
    v = (value or "").strip().lower()
    if CODE_RE.match(v):
        return v
    for kw, code in _EXPENSE_KEYWORDS.items():
        if kw in v:
            return code
    return None


def resolve_payment_account(value: str):
    """Kode akun kas/bank dari kode langsung atau kata kunci. None bila tak dikenal."""
    v = (value or "").strip().lower()
    if CODE_RE.match(v):
        return v
    for kw, code in _PAYMENT_KEYWORDS.items():
        if kw in v:
            return code
    return None


def parse_expense_block(block: str) -> dict:
    """Parse blok 'Kunci: Nilai' untuk pengeluaran sekali-kirim."""
    out: dict = {}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("jumlah", "amount", "nominal"):
            out["amount_raw"] = val
        elif key in ("untuk", "deskripsi", "description", "ket", "keterangan"):
            out["description"] = val[:255]
        elif key in ("beban", "akun", "kategori"):
            out["expense_raw"] = val
        elif key in ("bayar", "sumber", "dari"):
            out["paid_raw"] = val
    return out


# ===================== KONTAK (customer/supplier) =====================
# Untuk alur terpandu (nomor 1..N).
CONTACT_TYPES = [
    ("customer", "Customer / pelanggan"),
    ("supplier", "Supplier / pemasok"),
    ("both", "Keduanya"),
]

_CONTACT_TYPE_KEYWORDS = {
    "customer": "customer",
    "pelanggan": "customer",
    "outlet": "customer",
    "pembeli": "customer",
    "supplier": "supplier",
    "pemasok": "supplier",
    "vendor": "supplier",
    "both": "both",
    "keduanya": "both",
    "dua": "both",
}


def resolve_contact_type(value: str):
    """Tipe kontak (customer/supplier/both) dari kata kunci. None bila tak dikenal."""
    v = (value or "").strip().lower()
    if v in ("customer", "supplier", "both"):
        return v
    for kw, code in _CONTACT_TYPE_KEYWORDS.items():
        if kw in v:
            return code
    return None


def parse_contact_block(block: str) -> dict:
    """Parse blok 'Kunci: Nilai' untuk kontak sekali-kirim."""
    out: dict = {}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("tipe", "type", "jenis"):
            out["type_raw"] = val
        elif key in ("nama", "name"):
            out["name"] = val[:160]
        elif key in ("hp", "telp", "telpon", "telepon", "phone", "no", "nomor"):
            out["phone"] = val[:40]
    return out


# ===================== KASBON (pinjaman karyawan) =====================
def parse_loan_block(block: str) -> dict:
    """Parse blok 'Kunci: Nilai' untuk kasbon sekali-kirim."""
    out: dict = {}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("nama", "name", "karyawan"):
            out["name"] = val[:120]
        elif key in ("jumlah", "amount", "nominal"):
            out["amount_raw"] = val
        elif key in ("bayar", "sumber", "dari"):
            out["paid_raw"] = val
    return out


# ===================== PEMBAYARAN (by nomor faktur) =====================
def parse_payment_block(block: str) -> dict:
    """Parse blok 'Kunci: Nilai' untuk pembayaran sekali-kirim."""
    out: dict = {}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("faktur", "nota", "invoice", "nomor", "no", "ref"):
            out["ref"] = val[:40]
        elif key in ("jumlah", "amount", "nominal", "bayar"):
            out["amount_raw"] = val
    return out
