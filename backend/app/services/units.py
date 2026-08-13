"""Konversi satuan dus <-> botol. Satu-satunya tempat aturan satuan hidup.

ATURAN INTI — jangan dilanggar:

1. **Stok, HPP, dan valuasi HANYA disimpan dalam BOTOL** (satuan dasar).
   "Dus" bukan satuan penyimpanan; dus adalah pengali saat input dan cara
   menampilkan. Menyimpan dua penghitung (qty_dus + qty_botol) berarti dua
   sumber kebenaran untuk satu kenyataan fisik — persis yang dihindari.

2. **Isi per dus disimpan per produk** (`Product.pack_size`), bukan konstanta
   global. PT ASF: Chivas 200ml = 24 botol/dus, Robinson Vodka = 48, sisanya 12.
   Kalau angka ini jadi fallback global, SKU baru berkemasan lain akan
   menghasilkan stok salah TANPA error apa pun.

3. **Harga modal diinput per DUS** (cara client berpikir), disimpan dua bentuk:
   `Product.pack_purchase_price` (per dus, apa yang diketik = sumber kebenaran)
   dan `Product.purchase_price` (per botol, turunan untuk hitung margin/HPP).

4. **Faktor konversi di-snapshot per baris transaksi** (`*.unit_factor`), tidak
   dibaca ulang dari master. Kalau kemasan berubah (12 -> 6 per dus), riwayat
   transaksi lama harus tetap berarti sama seperti saat dicatat.
"""
from __future__ import annotations

from decimal import Decimal

BASE_UNIT = "botol"
PACK_UNIT = "dus"
# Default isi per dus untuk PT ASF; wajib di-override untuk produk berkemasan lain.
DEFAULT_PACK_SIZE = 12

# Satuan yang boleh dipakai di baris transaksi.
ALLOWED_UNITS = (PACK_UNIT, BASE_UNIT)

_PACK_ALIASES = {
    "dus", "dos", "dz", "karton", "kardus", "carton", "ctn", "box", "kotak",
    "pack", "pak", "krat",
}
_BASE_ALIASES = {
    "botol", "botols", "btl", "bt", "bottle", "pcs", "pc", "pieces", "buah",
    "bh", "unit", "biji",
}


class UnitError(ValueError):
    """Satuan tidak dikenal / tidak valid — pesannya aman ditampilkan ke user."""


def try_normalize_unit(raw: str | None) -> str | None:
    """'DUS'/'ctn' -> 'dus', 'btl'/'pcs' -> 'botol'. None bila tidak dikenal."""
    if raw is None:
        return None
    key = str(raw).strip().lower().rstrip(".")
    if not key:
        return None
    if key in _PACK_ALIASES:
        return PACK_UNIT
    if key in _BASE_ALIASES:
        return BASE_UNIT
    return None


def normalize_unit(raw: str | None) -> str:
    """Seperti try_normalize_unit, tetapi menolak yang tidak dikenal.

    Dipakai di jalur yang TIDAK BOLEH menebak (mis. bot Telegram): salah tebak
    'botol' padahal maksudnya 'dus' membuat stok salah sampai 48x dan langsung
    masuk jurnal.
    """
    unit = try_normalize_unit(raw)
    if unit is None:
        raise UnitError(
            f"Satuan '{raw or ''}' tidak dikenal. Tulis '{PACK_UNIT}' atau "
            f"'{BASE_UNIT}'."
        )
    return unit


def clean_pack_size(value) -> int:
    """Isi per dus yang valid (bulat >= 1). Kosong/tidak valid -> default."""
    try:
        size = int(Decimal(str(value)))
    except (ArithmeticError, TypeError, ValueError):
        return DEFAULT_PACK_SIZE
    return size if size >= 1 else DEFAULT_PACK_SIZE


def factor_for(unit: str | None, pack_size) -> int:
    """Berapa botol per satu satuan yang dipilih. 'botol' -> 1, 'dus' -> isi dus."""
    return clean_pack_size(pack_size) if try_normalize_unit(unit) == PACK_UNIT else 1


def to_base(qty_input, factor: int) -> Decimal:
    """Jumlah dalam BOTOL dari jumlah yang diketik user + faktor."""
    return Decimal(str(qty_input)) * Decimal(int(factor))


def base_price_from_pack(pack_price, pack_size) -> Decimal:
    """Harga per BOTOL dari harga per DUS. Dibulatkan ke rupiah-sen.

    Pembulatan di sini hanya memengaruhi harga ACUAN (modal referensi); HPP
    sesungguhnya memakai `StockLevel.avg_cost` yang dihitung dari nilai bill
    nyata, jadi selisih sen tidak merembet ke jurnal.
    """
    size = clean_pack_size(pack_size)
    return (Decimal(str(pack_price or 0)) / Decimal(size)).quantize(Decimal("0.01"))


def pack_price_from_base(base_price, pack_size) -> Decimal:
    """Harga per DUS dari harga per botol (kebalikan base_price_from_pack)."""
    size = clean_pack_size(pack_size)
    return (Decimal(str(base_price or 0)) * Decimal(size)).quantize(Decimal("0.01"))


def _trim(value: Decimal) -> str:
    """'5.0000' -> '5', '2.5000' -> '2.5' (biar enak dibaca di UI & bot)."""
    text = format(value.normalize(), "f")
    return text


def format_qty(base_qty, pack_size, *, pack_unit: str = PACK_UNIT,
               base_unit: str = BASE_UNIT) -> str:
    """Tampilkan stok botol sebagai 'dus + botol'. 29 botol @24 -> '1 dus 5 botol'.

    Hanya untuk TAMPILAN. Angka yang disimpan tetap dalam botol.
    """
    qty = Decimal(str(base_qty or 0))
    size = clean_pack_size(pack_size) if pack_size else 1
    sign = "-" if qty < 0 else ""
    qty = abs(qty)

    if size <= 1:
        return f"{sign}{_trim(qty)} {base_unit}"

    packs = int(qty // size)
    rest = qty - (Decimal(packs) * Decimal(size))
    parts: list[str] = []
    if packs:
        parts.append(f"{packs} {pack_unit}")
    if rest or not parts:
        parts.append(f"{_trim(rest)} {base_unit}")
    return sign + " ".join(parts)
