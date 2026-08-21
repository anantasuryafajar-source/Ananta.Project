"""Bonus internal berjenjang, dividen bulanan, dan tutup buku.

Modul MURNI seperti `commission_engine`: tanpa DB, tanpa jurnal, tanpa
FastAPI. Semua masukan angka, semua keluaran angka.

Tiga aturan yang membentuk modul ini (spesifikasi client 2026-08-21):

1. Bonus internal dihitung dari **Dasar Uang Masuk Bersih**, bukan omzet
   kotor. Dasar itu datang dari `commission_engine.process_payment`, yang
   sudah memotong komisi pihak ketiga dan hak mitra.
2. Term 1 (tgl 1–15) **pasti cair** tgl 16 pada 4,3%. Term 2 (tgl 16–akhir
   bulan) **all-or-nothing**: hanya cair kalau target bulanan tercapai,
   berikut rapelan 1% untuk Term 1.
3. Dividen dihitung dari **omzet kotor** dan tunduk gerbang yang sama.

Gerbang target butuh DUA syarat sekaligus (omzet ≥ 500jt DAN uang masuk
bersih ≥ 500jt). Memakai `or` di situ akan mencairkan ratusan juta atas
penjualan yang uangnya belum masuk — dikunci dengan tes tersendiri.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .commission_engine import _d, _q, HUNDRED  # noqa: F401

# --- Tarif & ambang. Konstanta bernama, bukan angka telanjang di rumus.
BONUS_TERM1_PERSEN = Decimal("4.3")     # pasti cair tgl 16
BONUS_TERM2_PERSEN = Decimal("5.3")     # bersyarat, cair tgl 1
BOOSTER_TERM1_PERSEN = Decimal("1.0")   # rapelan Term 1: 4,3% -> 5,3%
DIVIDEN_NYOKAP_SAM = Decimal("18")      # % dari omzet bulanan
DIVIDEN_DELVINA = Decimal("14")         # % dari omzet bulanan
TARGET_OMZET = Decimal("500000000")
TARGET_UANG_MASUK = Decimal("500000000")

TERM1_HARI_TERAKHIR = 15


def term_of(d: date) -> int:
    """1 untuk tanggal 1–15, 2 untuk 16–akhir bulan."""
    return 1 if d.day <= TERM1_HARI_TERAKHIR else 2


@dataclass
class PaymentRecord:
    """Satu uang masuk yang sudah dipecah oleh `process_payment`."""
    tanggal: date
    net_basis: Decimal              # Dasar Hitung Bonus Masuk
    commission_released: Decimal    # komisi pihak luar siap cair
    invoice_lunas: bool = False     # transfer fisik hanya setelah lunas
    invoice_number: str = ""


@dataclass
class MonthData:
    tahun: int
    bulan: int
    omzet_penjualan: Decimal = Decimal("0")   # omzet KOTOR bulan berjalan
    # Laba kotor bulan berjalan (omzet - HPP). OPSIONAL, tapi sangat
    # disarankan diisi: tanpa angka ini modul tidak bisa memperingatkan kalau
    # dividen yang dihitung dari omzet KOTOR ternyata melampaui laba yang
    # benar-benar dihasilkan.
    laba_kotor: Decimal | None = None
    pembayaran: list[PaymentRecord] = field(default_factory=list)
    # Bonus Term 1 yang sudah benar-benar dibayar tgl 16. Dipakai supaya
    # rekap tgl 1 tidak menghitungnya dua kali.
    bonus_term1_sudah_dibayar: Decimal = Decimal("0")


@dataclass
class TargetStatus:
    tercapai: bool
    omzet: Decimal
    uang_masuk_bersih: Decimal
    kurang_omzet: Decimal
    kurang_uang_masuk: Decimal


@dataclass
class BonusStatus:
    basis_term1: Decimal
    basis_term2: Decimal
    bonus_tgl16: Decimal            # 4,3% x basis Term 1 (pasti)
    bonus_term2: Decimal            # 5,3% x basis Term 2 (bersyarat)
    booster_term1: Decimal          # 1,0% x basis Term 1 (bersyarat)
    total_cair_tgl1: Decimal
    hangus: Decimal                 # yang batal cair karena target meleset


@dataclass
class DividenStatus:
    nyokap_sam: Decimal
    delvina: Decimal
    total: Decimal
    hangus: Decimal


# ============================================================ TARGET
def evaluate_target(data: MonthData) -> TargetStatus:
    """Gerbang all-or-nothing. WAJIB dua syarat, bukan salah satu."""
    omzet = _q(data.omzet_penjualan)
    masuk = _q(sum((_d(p.net_basis) for p in data.pembayaran), Decimal("0")))
    tercapai = omzet >= TARGET_OMZET and masuk >= TARGET_UANG_MASUK
    return TargetStatus(
        tercapai=tercapai, omzet=omzet, uang_masuk_bersih=masuk,
        kurang_omzet=_q(max(TARGET_OMZET - omzet, Decimal("0"))),
        kurang_uang_masuk=_q(max(TARGET_UANG_MASUK - masuk, Decimal("0"))),
    )


def basis_per_term(data: MonthData) -> tuple[Decimal, Decimal]:
    t1 = sum((_d(p.net_basis) for p in data.pembayaran
              if term_of(p.tanggal) == 1), Decimal("0"))
    t2 = sum((_d(p.net_basis) for p in data.pembayaran
              if term_of(p.tanggal) == 2), Decimal("0"))
    return _q(t1), _q(t2)


# ============================================================ BONUS
def calculate_bonus(data: MonthData,
                    target: TargetStatus | None = None) -> BonusStatus:
    """Bonus internal Term 1 (pasti) & Term 2 + booster (bersyarat)."""
    target = target or evaluate_target(data)
    b1, b2 = basis_per_term(data)

    tgl16 = _q(b1 * BONUS_TERM1_PERSEN / HUNDRED)

    if target.tercapai:
        bonus2 = _q(b2 * BONUS_TERM2_PERSEN / HUNDRED)
        booster = _q(b1 * BOOSTER_TERM1_PERSEN / HUNDRED)
        hangus = Decimal("0.00")
    else:
        # All-or-nothing: Term 2 hangus TOTAL, bukan turun rate. Booster juga
        # batal, jadi Term 1 tetap di 4,3% yang sudah dibayar tgl 16 — bonus
        # yang sudah cair tidak pernah ditarik kembali.
        bonus2 = Decimal("0.00")
        booster = Decimal("0.00")
        hangus = _q(b2 * BONUS_TERM2_PERSEN / HUNDRED
                    + b1 * BOOSTER_TERM1_PERSEN / HUNDRED)

    return BonusStatus(
        basis_term1=b1, basis_term2=b2, bonus_tgl16=tgl16,
        bonus_term2=bonus2, booster_term1=booster,
        total_cair_tgl1=_q(bonus2 + booster), hangus=hangus,
    )


# ============================================================ DIVIDEN
def calculate_dividen(data: MonthData,
                      target: TargetStatus | None = None) -> DividenStatus:
    """Dividen dari OMZET KOTOR bulanan, tunduk gerbang yang sama."""
    target = target or evaluate_target(data)
    omzet = _q(data.omzet_penjualan)
    penuh_sam = _q(omzet * DIVIDEN_NYOKAP_SAM / HUNDRED)
    penuh_del = _q(omzet * DIVIDEN_DELVINA / HUNDRED)

    if target.tercapai:
        return DividenStatus(nyokap_sam=penuh_sam, delvina=penuh_del,
                             total=_q(penuh_sam + penuh_del),
                             hangus=Decimal("0.00"))
    return DividenStatus(nyokap_sam=Decimal("0.00"), delvina=Decimal("0.00"),
                         total=Decimal("0.00"),
                         hangus=_q(penuh_sam + penuh_del))


# ============================================================ TUTUP BUKU
def generate_monthly_closing_report(data: MonthData) -> dict:
    """Rekap tutup buku & daftar transfer yang jatuh tempo tanggal 1.

    Komisi pihak luar dipisah dua: yang fakturnya sudah LUNAS (boleh
    ditransfer fisik) dan yang belum (tertahan). Keduanya sengaja tidak
    dijumlah jadi satu angka — menjumlahkannya lalu membandingkannya dengan
    saldo kas akan selalu tampak kurang, dan orang akan mengira ada uang
    hilang.
    """
    target = evaluate_target(data)
    bonus = calculate_bonus(data, target)
    dividen = calculate_dividen(data, target)

    cair = _q(sum((_d(p.commission_released) for p in data.pembayaran
                   if p.invoice_lunas), Decimal("0")))
    tertahan = _q(sum((_d(p.commission_released) for p in data.pembayaran
                       if not p.invoice_lunas), Decimal("0")))

    disbursement = _q(bonus.total_cair_tgl1 + dividen.total + cair)

    laporan = {
        "periode": f"{data.tahun}-{data.bulan:02d}",
        "target": {
            "tercapai": target.tercapai,
            "omzet": str(target.omzet),
            "uang_masuk_bersih": str(target.uang_masuk_bersih),
            "ambang": str(TARGET_OMZET),
            "kurang_omzet": str(target.kurang_omzet),
            "kurang_uang_masuk": str(target.kurang_uang_masuk),
        },
        "komisi_pihak_luar": {
            "siap_transfer": str(cair),
            "tertahan_belum_lunas": str(tertahan),
        },
        "bonus_internal": {
            "basis_term1": str(bonus.basis_term1),
            "basis_term2": str(bonus.basis_term2),
            "sudah_cair_tgl16": str(bonus.bonus_tgl16),
            "bonus_term2": str(bonus.bonus_term2),
            "booster_term1": str(bonus.booster_term1),
            "cair_tgl1": str(bonus.total_cair_tgl1),
            "hangus": str(bonus.hangus),
        },
        "laba_kotor": (str(_q(data.laba_kotor))
                       if data.laba_kotor is not None else None),
        "dividen": {
            "nyokap_sam": str(dividen.nyokap_sam),
            "delvina": str(dividen.delvina),
            "total": str(dividen.total),
            "hangus": str(dividen.hangus),
        },
        "disbursement_tgl1": {
            "bonus_internal": str(bonus.total_cair_tgl1),
            "dividen": str(dividen.total),
            "komisi_pihak_luar": str(cair),
            "total": str(disbursement),
        },
        "peringatan": [],
    }

    # Peringatan, bukan penghalang: modul melapor, finance yang memutuskan.
    #
    # Dividen 18% + 14% dihitung dari OMZET KOTOR, sementara laba yang
    # dihasilkan jauh lebih kecil. Pada faktur bertipe Rusdi (Inv 16jt, HPP
    # 14jt) marginnya cuma 12,5%; 32% dari omzet berarti membagikan sekitar
    # dua setengah kali lipat laba kotornya. Itu tidak akan terlihat di angka
    # mana pun sampai kas kering, karena tidak ada satu pun rumus di atas
    # yang membandingkan pembagian dengan laba.
    if data.laba_kotor is not None and disbursement > _q(data.laba_kotor):
        laporan["peringatan"].append(
            f"Total transfer {disbursement} MELEBIHI laba kotor bulan ini "
            f"({_q(data.laba_kotor)}). Dividen dihitung dari omzet kotor "
            f"({DIVIDEN_NYOKAP_SAM + DIVIDEN_DELVINA}% x {target.omzet}), "
            f"bukan dari laba — selisihnya diambil dari modal kerja."
        )
    if disbursement > target.uang_masuk_bersih:
        laporan["peringatan"].append(
            f"Total transfer {disbursement} melebihi uang masuk bersih "
            f"{target.uang_masuk_bersih} bulan ini. Periksa saldo kas "
            f"sebelum mengeksekusi."
        )
    if tertahan > 0:
        laporan["peringatan"].append(
            f"Komisi {tertahan} tertahan karena fakturnya belum lunas."
        )
    return laporan
