"""Pembacaan angka dari sel Excel — gaya Indonesia maupun Inggris.

Sel bertipe TEKS sering memuat pemisah ribuan. `Decimal("600.000")` sah dibaca
Python sebagai 600, jadi tanpa penanganan khusus modal enam ratus ribu tersimpan
enam ratus rupiah dan HPP ikut salah 1.000x.
"""
from decimal import Decimal

import pytest

from app.routers.bulk_import import _num


def test_gaya_indonesia():
    assert _num("1.800.000") == Decimal("1800000")
    assert _num("600.000") == Decimal("600000")      # inilah kasus yang dulu salah
    assert _num("Rp 1.300.000") == Decimal("1300000")
    assert _num("1.800.000,50") == Decimal("1800000.50")
    assert _num("1500,75") == Decimal("1500.75")


def test_gaya_inggris():
    assert _num("1,800,000") == Decimal("1800000")
    assert _num("1,800,000.50") == Decimal("1800000.50")
    assert _num("600000.5") == Decimal("600000.5")


def test_angka_polos_dan_kosong():
    assert _num(1800000) == Decimal("1800000")
    assert _num(Decimal("12.5")) == Decimal("12.5")
    assert _num("") == Decimal("0")
    assert _num(None) == Decimal("0")
    assert _num("", default="12") == Decimal("12")
    assert _num("-5.000") == Decimal("-5000")


def test_desimal_asli_tidak_dianggap_ribuan():
    # dua angka di belakang titik -> desimal, bukan pemisah ribuan
    assert _num("12.50") == Decimal("12.50")
    assert _num("0.75") == Decimal("0.75")


def test_teks_ngawur_ditolak():
    with pytest.raises(ValueError):
        _num("seratus ribu")
