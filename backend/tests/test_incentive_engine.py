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
