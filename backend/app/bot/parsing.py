"""Helper parsing murni untuk bot (tanpa dependensi telegram / DB).

Dipisah agar bisa diuji langsung di CI.
"""
import re
from decimal import Decimal, InvalidOperation

DEC0 = Decimal("0")
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


# ===================== PENGADAAN (faktur pembelian multi-baris) =====================
# 'SKU x QTY SATUAN @ HARGA [# keterangan]' — satuan WAJIB (dus/botol & alias).
# Bot tidak boleh menebak satuan: salah tebak membuat stok salah 12-48x dan
# langsung masuk jurnal. Lihat services/units.py.
#
# Keterangan setelah '#' bersifat OPSIONAL dan setara dengan kotak "Keterangan
# item" di web. Aman dipisah dengan '#' karena bagian harga hanya menerima
# angka/titik/koma, jadi parser berhenti sendiri sebelum tanda itu.
_ITEM_RE = re.compile(
    r"^\s*(.+?)\s*[xX*]\s*([\d.,]+)\s*([A-Za-z]+)\s*@\s*([\d.,]+)"
    r"\s*(?:#\s*(.*?))?\s*$"
)
# Bentuk lama tanpa satuan — dikenali khusus supaya pesan errornya jelas.
_ITEM_NO_UNIT_RE = re.compile(
    r"^\s*(.+?)\s*[xX*]\s*([\d.,]+)\s*@\s*([\d.,]+)\s*(?:#.*)?$"
)


def parse_price_nonneg(text: str):
    """Harga >= 0 (unit_cost boleh 0). None bila tak valid."""
    cleaned = (text or "").replace(".", "").replace(",", "").replace(" ", "").strip()
    if cleaned == "":
        return DEC0
    try:
        val = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return val if val >= 0 else None


class ItemUnitMissing(ValueError):
    """Baris item ditulis tanpa satuan — harus ditolak, tidak boleh ditebak."""


def parse_item_line(line: str):
    """'SKU x QTY SATUAN @ HARGA [# keterangan]'
    -> (sku, qty>0, unit, harga>=0, keterangan|None) atau None.

    Satuan wajib ditulis ('dus' atau 'botol'). Bila baris memakai bentuk lama
    tanpa satuan, fungsi ini melempar ItemUnitMissing supaya pemanggil bisa
    memberi pesan yang jelas — bukan menebak dan salah 12-48x.

    Keterangan setelah '#' opsional; kosong dianggap tidak ada.
    """
    from ..services.units import UnitError, normalize_unit

    m = _ITEM_RE.match(line or "")
    if not m:
        if _ITEM_NO_UNIT_RE.match(line or ""):
            raise ItemUnitMissing(line or "")
        return None
    sku = m.group(1).strip()[:40]
    qty = parse_amount(m.group(2))          # > 0
    try:
        unit = normalize_unit(m.group(3))
    except UnitError:
        return None
    price = parse_price_nonneg(m.group(4))  # >= 0
    note = (m.group(5) or "").strip()[:255] or None
    if not sku or qty is None or price is None:
        return None
    return (sku, qty, unit, price, note)


def parse_pengadaan_block(block: str) -> dict:
    """Parse blok pengadaan. Baris 'Item:' bisa banyak."""
    out = {"supplier": None, "warehouse": None, "items": [], "notes": None}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("supplier", "pemasok", "vendor"):
            out["supplier"] = val[:160]
        elif key in ("gudang", "warehouse"):
            out["warehouse"] = val[:120]
        elif key in ("item", "barang", "produk"):
            out["items"].append(val)
        elif key in ("catatan", "note", "ket", "keterangan"):
            out["notes"] = val[:500]
    return out


# ===================== PENJUALAN / Omzet Lempar (faktur jual multi-baris) =====================
def parse_penjualan_block(block: str) -> dict:
    """Parse blok penjualan. Sama seperti pengadaan tapi 'Customer' bukan 'Supplier'."""
    out = {"customer": None, "warehouse": None, "items": [], "notes": None}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("customer", "pelanggan", "outlet", "pembeli"):
            out["customer"] = val[:160]
        elif key in ("gudang", "warehouse"):
            out["warehouse"] = val[:120]
        elif key in ("item", "barang", "produk"):
            out["items"].append(val)
        elif key in ("catatan", "note", "ket", "keterangan"):
            out["notes"] = val[:500]
    return out


# ===================== PRODUK (/tambah_produk) =====================
def parse_product_block(block: str) -> dict:
    """Parse blok multi-baris 'Kunci: Nilai' jadi dict field produk.

    Toleran: tanda '-' di depan, spasi bebas, kunci Indonesia/Inggris.

    Catatan: kunci "Harga"/"Modal" dibaca sebagai **modal per dus**. Dulu nilai
    ini salah tersimpan ke harga jual (`sale_price`) sehingga modal produk selalu
    kosong di web — itu bug yang diperbaiki bersama perubahan satuan ini.
    """
    out: dict = {}
    for raw in block.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "sku":
            out["sku"] = val[:40]
        elif key in ("nama", "name"):
            out["name"] = val[:200]
        elif key in ("isi per dus", "isi", "isi dus", "pack", "pack size"):
            out["pack_raw"] = val
        elif key in ("harga", "modal", "modal per dus", "harga modal",
                     "harga per dus", "price"):
            out["price_raw"] = val
    return out


# ===================== DRAFT SESI -> INPUT SERVICE =====================
class DraftUnitMissing(ValueError):
    """Baris draft tidak menyimpan satuan — biasanya sesi lama dari versi
    sebelum satuan diwajibkan. Harus ditolak, TIDAK boleh dianggap botol."""


def draft_to_lines_in(lines: list[dict], *, price_field: str) -> list[dict]:
    """Ubah baris draft (tersimpan di sesi bot) menjadi `lines_in` untuk service.

    `price_field` = "unit_cost" untuk pengadaan, "unit_price" untuk penjualan.

    Fungsi ini ada karena pemetaannya pernah ditulis dua kali secara manual dan
    salah satunya LUPA menyertakan `unit`. Akibatnya "10 dus" dikirim tanpa
    satuan, service memakai default "botol", dan stok tercatat 12-48x lebih
    kecil — langsung masuk jurnal. Satu fungsi murni membuat kesalahan itu
    tertangkap tes.
    """
    out: list[dict] = []
    for ln in lines:
        if not ln.get("unit"):
            raise DraftUnitMissing(str(ln.get("product_id")))
        out.append({
            "product_id": ln["product_id"],
            "quantity": Decimal(str(ln["quantity"])),
            "unit": ln["unit"],
            price_field: Decimal(str(ln[price_field])),
            "note": ln.get("note"),
        })
    return out
