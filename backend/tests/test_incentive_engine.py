"""Kasus uji bonus berjenjang, dividen, dan tutup buku bulanan.

Modul yang diuji murni (tanpa DB), jadi tidak butuh fixture `db`.
"""
from datetime import date
from decimal import Decimal
from app.services.incentive_engine import (
    MonthData, PaymentRecord, term_of, evaluate_target, calculate_bonus,
    calculate_dividen, generate_monthly_closing_report,
)

D = Decimal


def _bayar(hari, basis, komisi="0", lunas=False):
    return PaymentRecord(tanggal=date(2026, 3, hari), net_basis=D(basis),
                         commission_released=D(komisi), invoice_lunas=lunas)


# ============================================================ TERM
def test_pembagian_term_di_tanggal_15_dan_16():
    """Batasnya tanggal 15 — tanggal 16 sudah masuk Term 2."""
    assert term_of(date(2026, 3, 1)) == 1
    assert term_of(date(2026, 3, 15)) == 1
    assert term_of(date(2026, 3, 16)) == 2
    assert term_of(date(2026, 3, 31)) == 2


# ============================================================ TARGET
def test_target_butuh_dua_syarat_sekaligus():
    """Omzet tembus tapi uang masuk belum -> TIDAK tercapai.

    Kalau gerbangnya dibuat `or`, ratusan juta cair atas penjualan yang
    uangnya belum masuk. Ini tes yang menangkapnya.
    """
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
                     pembayaran=[_bayar(10, "300000000")])
    t = evaluate_target(data)
    assert t.tercapai is False
    assert t.kurang_uang_masuk == D("200000000.00")
    assert t.kurang_omzet == D("0.00")


def test_target_tercapai_saat_keduanya_tembus():
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("520000000"),
                     pembayaran=[_bayar(10, "300000000"),
                                 _bayar(20, "250000000")])
    assert evaluate_target(data).tercapai is True


# ============================================================ BONUS
def test_bonus_term1_pasti_cair_walau_target_meleset():
    """Term 1 guaranteed: sudah dibayar tgl 16, tidak ditarik kembali."""
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("100000000"),
                     pembayaran=[_bayar(10, "100000000"),
                                 _bayar(20, "50000000")])
    b = calculate_bonus(data)
    assert b.bonus_tgl16 == D("4300000.00")      # 4,3% x 100jt
    assert b.bonus_term2 == D("0.00")            # hangus
    assert b.booster_term1 == D("0.00")
    assert b.total_cair_tgl1 == D("0.00")
    # 5,3% x 50jt + 1% x 100jt = 2.650.000 + 1.000.000
    assert b.hangus == D("3650000.00")


def test_bonus_target_tercapai_term2_plus_booster():
    """Target tembus: Term 2 di 5,3% + rapelan 1% untuk Term 1."""
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
                     pembayaran=[_bayar(10, "300000000"),
                                 _bayar(20, "250000000")])
    b = calculate_bonus(data)
    assert b.bonus_tgl16 == D("12900000.00")     # 4,3% x 300jt
    assert b.bonus_term2 == D("13250000.00")     # 5,3% x 250jt
    assert b.booster_term1 == D("3000000.00")    # 1,0% x 300jt
    assert b.total_cair_tgl1 == D("16250000.00")
    assert b.hangus == D("0.00")


def test_booster_menyamakan_term1_jadi_53_persen():
    """4,3% + 1,0% = 5,3% — rapelan, bukan bonus tambahan di luar rate."""
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
                     pembayaran=[_bayar(10, "300000000"),
                                 _bayar(20, "250000000")])
    b = calculate_bonus(data)
    total_term1 = b.bonus_tgl16 + b.booster_term1
    assert total_term1 == D("300000000") * D("5.3") / D("100")


# ============================================================ DIVIDEN
def test_dividen_hangus_kalau_target_meleset():
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("400000000"),
                     pembayaran=[_bayar(10, "400000000")])
    d = calculate_dividen(data)
    assert d.nyokap_sam == D("0.00")
    assert d.delvina == D("0.00")
    # 18% + 14% = 32% x 400jt = 128jt
    assert d.hangus == D("128000000.00")


def test_dividen_cair_penuh_saat_target_tercapai():
    data = MonthData(tahun=2026, bulan=3, omzet_penjualan=D("500000000"),
                     pembayaran=[_bayar(10, "500000000")])
    d = calculate_dividen(data)
    assert d.nyokap_sam == D("90000000.00")   # 18%
    assert d.delvina == D("70000000.00")      # 14%
    assert d.total == D("160000000.00")


# ============================================================ TUTUP BUKU
def test_tutup_buku_target_tercapai():
    data = MonthData(
        tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
        pembayaran=[_bayar(10, "300000000", "5000000", lunas=True),
                    _bayar(20, "250000000", "3000000", lunas=False)],
    )
    r = generate_monthly_closing_report(data)
    assert r["target"]["tercapai"] is True
    assert r["komisi_pihak_luar"]["siap_transfer"] == "5000000.00"
    assert r["komisi_pihak_luar"]["tertahan_belum_lunas"] == "3000000.00"
    assert r["bonus_internal"]["cair_tgl1"] == "16250000.00"
    assert r["dividen"]["total"] == "192000000.00"   # 32% x 600jt
    # 16.250.000 + 192.000.000 + 5.000.000
    assert r["disbursement_tgl1"]["total"] == "213250000.00"


def test_tutup_buku_target_meleset_hanya_komisi_yang_keluar():
    data = MonthData(
        tahun=2026, bulan=3, omzet_penjualan=D("100000000"),
        pembayaran=[_bayar(10, "80000000", "2000000", lunas=True)],
    )
    r = generate_monthly_closing_report(data)
    assert r["target"]["tercapai"] is False
    assert r["bonus_internal"]["sudah_cair_tgl16"] == "3440000.00"  # tetap
    assert r["bonus_internal"]["cair_tgl1"] == "0.00"
    assert r["dividen"]["total"] == "0.00"
    assert r["disbursement_tgl1"]["total"] == "2000000.00"


def test_peringatan_dividen_melebihi_laba_kotor():
    """32% dari omzet KOTOR bisa jauh melampaui laba yang dihasilkan.

    Margin tipe Rusdi cuma 12,5% (Inv 16jt, HPP 14jt). Pada omzet 600jt,
    laba kotornya sekitar 75jt sementara dividen saja 192jt. Tidak ada satu
    pun rumus di spesifikasi yang membandingkan pembagian dengan laba, jadi
    ini tidak akan terlihat sampai kas kering.
    """
    data = MonthData(
        tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
        laba_kotor=D("75000000"),
        pembayaran=[_bayar(10, "300000000"), _bayar(20, "250000000")],
    )
    r = generate_monthly_closing_report(data)
    assert r["target"]["tercapai"] is True
    assert r["disbursement_tgl1"]["total"] == "208250000.00"
    assert any("MELEBIHI laba kotor" in p for p in r["peringatan"])


def test_tanpa_laba_kotor_peringatan_itu_tidak_muncul():
    """Opsional — kalau tidak diisi, modul tidak menebak-nebak."""
    data = MonthData(
        tahun=2026, bulan=3, omzet_penjualan=D("600000000"),
        pembayaran=[_bayar(10, "300000000"), _bayar(20, "250000000")],
    )
    r = generate_monthly_closing_report(data)
    assert r["laba_kotor"] is None
    assert not any("laba kotor" in p for p in r["peringatan"])


def test_bulan_kosong_tidak_error():
    r = generate_monthly_closing_report(MonthData(tahun=2026, bulan=3))
    assert r["disbursement_tgl1"]["total"] == "0.00"
    assert r["target"]["tercapai"] is False


# ===================================================================
# AKRUAL BONUS ATAS FAKTUR RUSDI — presisi penuh
# (spesifikasi client 2026-08-31)
#
# Faktur 350.000.000, komisi Bokap Adin 1.800.000, dasar bonus 348.200.000.
# Dua cicilan: 200.000.000 lalu 150.000.000 (pelunas).
#
# Dasar yang masuk ke mesin ini datang dari commission_engine.process_payment
# TANPA dibulatkan; pembulatan ke rupiah-sen hanya saat angkanya menyentuh
# jurnal. Tes di sini memastikan angka bonusnya benar dan akumulasinya pas.
# ===================================================================
from decimal import ROUND_HALF_UP

from app.services.commission_engine import (
    InvoiceData, SkemaKomisi, process_payment,
)

_FAKTUR = InvoiceData(
    skema=SkemaKomisi.RUSDI_MARGIN,
    total_invoice=D("350000000"),
    total_hpp=D("300000000"),
    total_dus=D("100"),
)


def _sen(v: D) -> D:
    """Bulatkan ke rupiah-sen, seperti saat menjurnal."""
    return v.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _dua_cicilan():
    """200jt lalu 150jt pelunas, akumulasi disimpan dalam rupiah-sen."""
    c1 = process_payment(_FAKTUR, D("200000000"))
    c2 = process_payment(
        _FAKTUR, D("150000000"), sudah_dibayar=D("200000000"),
        sudah_dicairkan=_sen(c1.commission_released),
        sudah_basis=_sen(c1.net_bonus_basis),
    )
    return c1, c2


def test_akrual_term1_dari_dasar_presisi_penuh():
    """4,3% x 198.971.428,571428... = 8.555.771,428571...

    Yang diakui di jurnal 8.555.771,43 — pembulatan terjadi SEKALI, di ujung.
    """
    c1, _ = _dua_cicilan()
    assert c1.net_bonus_basis == D("200000000") * D("3482") / D("3500")

    bonus_nyata = c1.net_bonus_basis * D("4.3") / D("100")
    # Dibandingkan dengan pecahan EKSAK, bukan angka desimal yang diketik
    # tangan: 198.971.428,571428... tidak pernah habis, jadi menuliskannya
    # sebagai literal selalu berarti memotongnya di suatu digit.
    assert bonus_nyata == D("200000000") * D("3482") / D("3500") * D("43") / D("1000")
    # Pecahannya memang tidak bulat — inilah yang tidak boleh hilang di tengah.
    assert bonus_nyata != _sen(bonus_nyata)
    # Yang diakui di jurnal, setelah dibulatkan SEKALI di ujung.
    assert _sen(bonus_nyata) == D("8555771.43")


def test_dua_cicilan_masuk_term_yang_sama_berjumlah_pas():
    """Keduanya di tgl 1-15: dasar Term 1 harus pas 348.200.000."""
    c1, c2 = _dua_cicilan()
    data = MonthData(
        tahun=2026, bulan=3, omzet_penjualan=D("350000000"),
        pembayaran=[
            _bayar(5, str(_sen(c1.net_bonus_basis)),
                   str(_sen(c1.commission_released))),
            _bayar(12, str(_sen(c2.net_bonus_basis)),
                   str(_sen(c2.commission_released)), lunas=True),
        ],
    )
    b = calculate_bonus(data)
    assert b.basis_term1 == D("348200000.00")
    assert b.basis_term2 == D("0.00")
    # 4,3% x 348.200.000 = 14.972.600 tepat.
    assert b.bonus_tgl16 == D("14972600.00")


def test_jumlah_bonus_per_cicilan_sama_dengan_bonus_sekaligus():
    """Memecah pembayaran tidak boleh mengubah total bonusnya.

    Inilah bukti tidak ada pecahan yang hilang: 4,3% dihitung dua kali atas
    dua cicilan harus sama dengan 4,3% atas keseluruhan.
    """
    c1, c2 = _dua_cicilan()
    per_cicilan = (_sen(c1.net_bonus_basis * D("4.3") / D("100"))
                   + _sen(c2.net_bonus_basis * D("4.3") / D("100")))
    sekaligus = _sen(D("348200000") * D("4.3") / D("100"))
    assert per_cicilan == sekaligus == D("14972600.00")


def test_komisi_dan_dasar_bonus_menutup_nilai_faktur():
    """Komisi + dasar bonus harus persis senilai faktur — tidak ada yang
    tercecer di antara keduanya."""
    c1, c2 = _dua_cicilan()
    komisi = _sen(c1.commission_released) + _sen(c2.commission_released)
    dasar = _sen(c1.net_bonus_basis) + _sen(c2.net_bonus_basis)
    assert komisi == D("1800000.00")
    assert dasar == D("348200000.00")
    assert komisi + dasar == D("350000000.00")
