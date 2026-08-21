"""Kasus uji mesin komisi & prorata — angka nyata dari client (2026-08-21).

Modul yang diuji murni (tanpa DB), jadi tes ini tidak butuh fixture `db`.
"""
from decimal import Decimal
import pytest
from app.services.commission_engine import (
    InvoiceData, SkemaKomisi, calculate_invoice_commission, process_payment,
)

D = Decimal


# ============================================================ RUSDI
def test_rusdi_2_dus_hennessy():
    """Inv 16jt, HPP 14jt, 2 dus.

    4% x (16.000.000 - 14.000.000 - 100.000) = 4% x 1.900.000 = 76.000
    """
    inv = InvoiceData(skema=SkemaKomisi.RUSDI_MARGIN,
                      total_invoice=D("16000000"), total_hpp=D("14000000"),
                      total_dus=D("2"))
    r = calculate_invoice_commission(inv)
    assert r.dasar_komisi == D("1900000.00")
    assert r.total_komisi == D("76000.00")


def test_rusdi_cicilan_10_juta():
    """Rasio bersih 15.924.000/16.000.000; cicilan 10jt."""
    inv = InvoiceData(skema=SkemaKomisi.RUSDI_MARGIN,
                      total_invoice=D("16000000"), total_hpp=D("14000000"),
                      total_dus=D("2"))
    p = process_payment(inv, D("10000000"))
    assert p.net_bonus_basis == D("9952500.00")
    assert p.bonus_amount == D("427957.50")      # 4,3%
    assert p.commission_released == D("47500.00")
    assert p.sisa_piutang == D("6000000.00")
    assert p.lunas is False


def test_rusdi_pengurang_melahap_margin_tidak_negatif():
    """Komisi negatif berarti menagih uang ke sales — tidak boleh terjadi."""
    inv = InvoiceData(skema=SkemaKomisi.RUSDI_MARGIN,
                      total_invoice=D("1000000"), total_hpp=D("990000"),
                      total_dus=D("5"))   # potongan 250.000 > margin 10.000
    r = calculate_invoice_commission(inv)
    assert r.total_komisi == D("0.00")


# ============================================================ EXA
def test_exa_komisi_tetap_41_juta():
    inv = InvoiceData(skema=SkemaKomisi.FIXED_AMOUNT,
                      total_invoice=D("208000000"),
                      komisi_manual=D("41000000"))
    assert calculate_invoice_commission(inv).total_komisi == D("41000000.00")


def test_exa_cicilan_10_juta():
    """Rasio bersih 167/208. 10jt x 167/208 = 8.028.846,15."""
    inv = InvoiceData(skema=SkemaKomisi.FIXED_AMOUNT,
                      total_invoice=D("208000000"),
                      komisi_manual=D("41000000"))
    p = process_payment(inv, D("10000000"))
    assert p.net_bonus_basis == D("8028846.15")
    assert p.bonus_amount == D("345240.38")
    assert p.commission_released == D("1971153.85")
    assert p.sisa_piutang == D("198000000.00")
    assert p.lunas is False


# ============================================================ TONY
def test_tony_lunas_22_juta():
    """Lunas sekali bayar: dasar bonus = Invoice - Komisi, komisi cair penuh."""
    inv = InvoiceData(skema=SkemaKomisi.FIXED_AMOUNT,
                      total_invoice=D("22000000"), komisi_manual=D("500000"))
    p = process_payment(inv, D("22000000"))
    assert p.net_bonus_basis == D("21500000.00")
    assert p.bonus_amount == D("924500.00")
    assert p.commission_released == D("500000.00")
    assert p.sisa_piutang == D("0.00")
    assert p.lunas is True


# ============================================================ BPN
def test_bpn_tanpa_komisi():
    """Komisi 0 -> rasio bersih 1, seluruh uang masuk jadi dasar bonus."""
    inv = InvoiceData(skema=SkemaKomisi.NO_COMMISSION,
                      total_invoice=D("8700000"))
    assert calculate_invoice_commission(inv).total_komisi == D("0.00")
    p = process_payment(inv, D("8700000"))
    assert p.net_ratio == 1
    assert p.net_bonus_basis == D("8700000.00")
    assert p.bonus_amount == D("374100.00")
    assert p.commission_released == D("0.00")
    assert p.lunas is True


# ============================================================ ANDRE
def test_andre_split():
    """Inv 1.000, HPP riil 600, modal perjanjian 700.

    Margin perjanjian 300 -> mitra 150, ASF 150.
    Silo 4% x 150 = 6, Elias 6% x 150 = 9 -> total komisi 15.
    Hidden margin = 700 - 600 = 100.
    """
    inv = InvoiceData(skema=SkemaKomisi.ANDRE_SPLIT,
                      total_invoice=D("1000"), total_hpp=D("600"),
                      modal_perjanjian=D("700"))
    r = calculate_invoice_commission(inv)
    assert r.margin_perjanjian == D("300.00")
    assert r.asf_share == D("150.00")
    assert r.bagi_hasil_mitra == D("150.00")
    assert r.total_komisi == D("15.00")     # 6 + 9
    assert r.hidden_margin == D("100.00")


def test_andre_prorata_memotong_hak_mitra_juga():
    """Spesifikasi client: Total Pengurang = Hak Mitra + Komisi Pihak Ketiga.

    Rasio Bersih memakai `total_pengurang` (165), BUKAN `total_komisi` (15).
    Kalau hanya komisi yang dipotong, dasar bonus internal jadi 985 dan bonus
    dibayarkan atas 150 yang sebenarnya milik Andre.
    """
    inv = InvoiceData(skema=SkemaKomisi.ANDRE_SPLIT,
                      total_invoice=D("1000"), total_hpp=D("600"),
                      modal_perjanjian=D("700"))
    r = calculate_invoice_commission(inv)
    assert r.total_komisi == D("15.00")
    assert r.bagi_hasil_mitra == D("150.00")
    assert r.total_pengurang == D("165.00")

    p = process_payment(inv, D("1000"))
    assert p.net_bonus_basis == D("835.00")          # 1000 - 165
    assert p.commission_released == D("165.00")


def test_kimob_kirong_split():
    """Inv 1.000, HPP riil 600, modal perjanjian 700.

    Margin perjanjian 300 -> Kimob/Kirong 150, ASF 150.
    Kimob pihak ketiga (bukan mitra bagi hasil), jadi seluruh 150 masuk
    total_komisi dan total_pengurang tetap 150.
    """
    inv = InvoiceData(skema=SkemaKomisi.KIMOB_KIRONG_SPLIT,
                      total_invoice=D("1000"), total_hpp=D("600"),
                      modal_perjanjian=D("700"))
    r = calculate_invoice_commission(inv)
    assert r.total_komisi == D("150.00")
    assert r.asf_share == D("150.00")
    assert r.hidden_margin == D("100.00")
    assert r.bagi_hasil_mitra == D("0")
    assert r.total_pengurang == D("150.00")


# ============================================================ PEMBULATAN
def test_cicilan_terakhir_menyerap_sisa_pembulatan():
    """Jumlah komisi cair lintas cicilan HARUS sama persis dengan total komisi.

    Tanpa penyerapan di cicilan pelunas, sisa beberapa rupiah akan menggantung
    sebagai utang komisi yang tidak akan pernah lunas di neraca.
    """
    inv = InvoiceData(skema=SkemaKomisi.FIXED_AMOUNT,
                      total_invoice=D("208000000"),
                      komisi_manual=D("41000000"))
    total_komisi = calculate_invoice_commission(inv).total_komisi

    dibayar = D("0")
    dicairkan = D("0")
    basis = D("0")
    for cicilan in (D("10000000"), D("99000000"), D("99000000")):
        p = process_payment(inv, cicilan, sudah_dibayar=dibayar,
                            sudah_dicairkan=dicairkan, sudah_basis=basis)
        dibayar = p.total_dibayar
        dicairkan += p.commission_released
        basis += p.net_bonus_basis

    assert dibayar == D("208000000.00")
    assert dicairkan == total_komisi == D("41000000.00")
    assert basis == D("167000000.00")     # Invoice - Komisi, tanpa sisa


# ============================================================ PENJAGA
def test_pembayaran_melebihi_sisa_ditolak():
    inv = InvoiceData(skema=SkemaKomisi.NO_COMMISSION,
                      total_invoice=D("1000000"))
    with pytest.raises(ValueError, match="melebihi sisa piutang"):
        process_payment(inv, D("600000"), sudah_dibayar=D("500000"))


def test_komisi_tetap_melebihi_faktur_ditolak():
    inv = InvoiceData(skema=SkemaKomisi.FIXED_AMOUNT,
                      total_invoice=D("1000000"),
                      komisi_manual=D("1500000"))
    with pytest.raises(ValueError, match="melebihi nilai faktur"):
        calculate_invoice_commission(inv)


def test_andre_tanpa_modal_perjanjian_ditolak():
    inv = InvoiceData(skema=SkemaKomisi.ANDRE_SPLIT,
                      total_invoice=D("1000"), total_hpp=D("600"))
    with pytest.raises(ValueError, match="Modal Perjanjian"):
        calculate_invoice_commission(inv)
