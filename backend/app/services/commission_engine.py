"""Mesin hitung komisi & alokasi prorata pembayaran.

Modul MURNI: tidak menyentuh database, tidak membuat jurnal, tidak tahu
apa-apa soal FastAPI. Semua masukan berupa angka, semua keluaran berupa
angka. Itu disengaja — logika bisnis yang berubah-ubah lebih aman diuji dan
dipakai ulang kalau ia tidak terikat ke I/O.

Yang memakai modul ini bertanggung jawab menjurnalkan hasilnya lewat pintu
tetap (lihat services/profit_sheet_service.py): Beban/Utang Komisi dan
Beban/Utang Bagi Hasil. Pendapatan, HPP, dan Persediaan tidak pernah
tersentuh oleh angka dari sini.

Uang selalu Decimal, tidak pernah float. `0.1 + 0.2 != 0.3` pada float, dan
kesalahan sepersekian sen akan menumpuk lintas cicilan sampai total komisi
tidak sama dengan jumlah yang tercairkan.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def _d(v) -> Decimal:
    """Apa pun jadi Decimal. float sengaja lewat str supaya tidak bawa galat biner."""
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v if v is not None else 0))


def _q(v) -> Decimal:
    return _d(v).quantize(CENT, rounding=ROUND_HALF_UP)


class SkemaKomisi(str, Enum):
    """Daftar TERTUTUP. Menambah skema = menambah satu anggota + satu cabang
    di `calculate_invoice_commission`. JANGAN diganti rumus yang bisa diketik
    user: angka yang tidak bisa dijelaskan tidak bisa dipertanggungjawabkan."""
    RUSDI_MARGIN = "RUSDI_MARGIN"
    FIXED_AMOUNT = "FIXED_AMOUNT"
    ANDRE_SPLIT = "ANDRE_SPLIT"
    KIMOB_KIRONG_SPLIT = "KIMOB_KIRONG_SPLIT"
    NO_COMMISSION = "NO_COMMISSION"


# --- Tarif baku. Diletakkan sebagai konstanta bernama, bukan angka telanjang
# --- di tengah rumus, supaya ketahuan kalau suatu saat berubah.
RUSDI_PERSEN = Decimal("4")
RUSDI_PENGURANG_PER_DUS = Decimal("50000")
ANDRE_PORSI_ASF = Decimal("50")      # % dari margin perjanjian
ANDRE_KOMISI_SILO = Decimal("4")     # % dari bagian ASF
ANDRE_KOMISI_ELIAS = Decimal("6")    # % dari bagian ASF
KIMOB_PORSI = Decimal("50")          # % dari margin perjanjian
BONUS_SALES_PERSEN = Decimal("4.3")  # % dari dasar bonus masuk


@dataclass
class InvoiceData:
    """Angka faktur yang dibutuhkan mesin hitung.

    `total_invoice` adalah nilai yang ditagih ke customer — dasar prorata
    pembayaran, karena itu yang benar-benar dibayar customer.
    """
    skema: SkemaKomisi
    total_invoice: Decimal = Decimal("0")
    total_hpp: Decimal = Decimal("0")          # HPP riil (yang masuk jurnal)
    total_dus: Decimal = Decimal("0")
    modal_perjanjian: Decimal = Decimal("0")   # ANDRE_SPLIT saja
    komisi_manual: Decimal = Decimal("0")      # FIXED_AMOUNT saja
    # Penimpa opsional — kalau kesepakatannya menyimpang dari tarif baku.
    persen: Decimal | None = None
    pengurang_per_dus: Decimal | None = None


@dataclass
class CommissionResult:
    # Komisi PIHAK KETIGA saja (Bokap Adin / Silo+Elias / Kimob-Kirong / flat).
    total_komisi: Decimal
    skema: SkemaKomisi
    dasar_komisi: Decimal = Decimal("0")
    # Hak mitra yang BUKAN komisi pihak ketiga (Andre 50%).
    bagi_hasil_mitra: Decimal = Decimal("0")
    margin_perjanjian: Decimal = Decimal("0")
    asf_share: Decimal = Decimal("0")
    hidden_margin: Decimal = Decimal("0")
    rincian: list[dict] = field(default_factory=list)

    @property
    def total_pengurang(self) -> Decimal:
        """Seluruh uang yang keluar dari ASF atas invoice ini.

        Inilah yang dipakai menghitung Rasio Bersih — bukan `total_komisi`.
        Untuk ANDRE_SPLIT, hak mitra 50% juga uang yang keluar; kalau ia tidak
        ikut dipotong, dasar bonus internal jadi terlalu besar dan bonus
        dibayarkan atas uang yang sebenarnya bukan milik ASF.
        """
        return _q(self.total_komisi + self.bagi_hasil_mitra)


@dataclass
class PaymentResult:
    amount_paid: Decimal
    net_ratio: Decimal
    net_bonus_basis: Decimal
    bonus_amount: Decimal
    commission_released: Decimal
    total_dibayar: Decimal
    sisa_piutang: Decimal
    lunas: bool


# ============================================================ KOMISI
def calculate_invoice_commission(invoice: InvoiceData) -> CommissionResult:
    """Total komisi awal sebuah faktur menurut skemanya.

    `total_komisi` HANYA komisi pihak ketiga. Untuk ANDRE_SPLIT, hak mitra
    50% dikembalikan terpisah di `bagi_hasil_mitra`; yang dipakai menghitung
    Rasio Bersih adalah `total_pengurang` (jumlah keduanya).
    """
    total = _q(invoice.total_invoice)
    hpp = _q(invoice.total_hpp)

    if invoice.skema is SkemaKomisi.NO_COMMISSION:
        return CommissionResult(total_komisi=Decimal("0.00"),
                                skema=invoice.skema)

    if invoice.skema is SkemaKomisi.FIXED_AMOUNT:
        nilai = _q(invoice.komisi_manual)
        if nilai < 0:
            raise ValueError("Komisi tetap tidak boleh negatif.")
        if nilai > total:
            raise ValueError(
                f"Komisi tetap {nilai} melebihi nilai faktur {total}."
            )
        return CommissionResult(
            total_komisi=nilai, skema=invoice.skema, dasar_komisi=total,
            rincian=[{"label": "Nominal disepakati", "nilai": str(nilai)}],
        )

    if invoice.skema is SkemaKomisi.RUSDI_MARGIN:
        persen = _d(invoice.persen) if invoice.persen is not None else RUSDI_PERSEN
        tarif = (_d(invoice.pengurang_per_dus)
                 if invoice.pengurang_per_dus is not None
                 else RUSDI_PENGURANG_PER_DUS)
        potongan = _q(tarif * _d(invoice.total_dus))
        dasar = total - hpp - potongan
        # Pengurang yang melahap seluruh margin tidak boleh jadi komisi
        # negatif — itu berarti menagih uang ke sales, bukan membayarnya.
        if dasar < 0:
            dasar = Decimal("0.00")
        komisi = _q(dasar * persen / HUNDRED)
        return CommissionResult(
            total_komisi=komisi, skema=invoice.skema, dasar_komisi=_q(dasar),
            rincian=[
                {"label": "Total invoice", "nilai": str(total)},
                {"label": "HPP", "nilai": f"-{hpp}"},
                {"label": f"Pengurang {tarif}/dus x {_d(invoice.total_dus)}",
                 "nilai": f"-{potongan}"},
                {"label": "Dasar komisi", "nilai": str(_q(dasar))},
                {"label": "Persen", "nilai": f"{persen}%"},
            ],
        )

    if invoice.skema is SkemaKomisi.KIMOB_KIRONG_SPLIT:
        modal = _q(invoice.modal_perjanjian)
        if modal <= 0:
            raise ValueError("KIMOB_KIRONG_SPLIT butuh Modal Perjanjian.")
        margin_perjanjian = total - modal
        if margin_perjanjian < 0:
            raise ValueError(
                f"Modal perjanjian {modal} melebihi nilai faktur {total}."
            )
        porsi = _q(margin_perjanjian * KIMOB_PORSI / HUNDRED)
        asf_share = _q(margin_perjanjian - porsi)
        hidden = _q(modal - hpp)
        # Kimob/Kirong adalah pihak ketiga (bukan mitra bagi hasil), jadi
        # seluruh 50%-nya masuk `total_komisi` dan `bagi_hasil_mitra` nol.
        return CommissionResult(
            total_komisi=porsi, skema=invoice.skema,
            dasar_komisi=_q(margin_perjanjian),
            margin_perjanjian=_q(margin_perjanjian), asf_share=asf_share,
            hidden_margin=hidden,
            rincian=[
                {"label": "Margin perjanjian", "nilai": str(_q(margin_perjanjian))},
                {"label": "Kimob/Kirong 50%", "nilai": str(porsi)},
                {"label": "Bagian ASF 50%", "nilai": str(asf_share)},
                {"label": "Hidden margin ASF", "nilai": str(hidden)},
            ],
        )

    if invoice.skema is SkemaKomisi.ANDRE_SPLIT:
        modal = _q(invoice.modal_perjanjian)
        if modal <= 0:
            raise ValueError("ANDRE_SPLIT butuh Modal Perjanjian.")
        margin_perjanjian = total - modal
        if margin_perjanjian < 0:
            raise ValueError(
                f"Modal perjanjian {modal} melebihi nilai faktur {total}."
            )
        asf_share = _q(margin_perjanjian * ANDRE_PORSI_ASF / HUNDRED)
        mitra = _q(margin_perjanjian - asf_share)
        silo = _q(asf_share * ANDRE_KOMISI_SILO / HUNDRED)
        elias = _q(asf_share * ANDRE_KOMISI_ELIAS / HUNDRED)
        # Hidden margin = selisih modal perjanjian dengan HPP riil. 100% hak
        # ASF, tidak dibagi. TIDAK PERNAH dijurnal: ia turunan, bukan
        # transaksi. Menjurnalnya sebagai pendapatan bikin laba dobel dan
        # nilai persediaan melenceng.
        hidden = _q(modal - hpp)
        return CommissionResult(
            total_komisi=_q(silo + elias), skema=invoice.skema,
            dasar_komisi=asf_share, margin_perjanjian=_q(margin_perjanjian),
            asf_share=asf_share, hidden_margin=hidden, bagi_hasil_mitra=mitra,
            rincian=[
                {"label": "Margin perjanjian", "nilai": str(_q(margin_perjanjian))},
                {"label": "Bagian mitra (50%)", "nilai": str(mitra)},
                {"label": "Bagian ASF (50%)", "nilai": str(asf_share)},
                {"label": "Bokap Silo 4%", "nilai": str(silo)},
                {"label": "Elias 6%", "nilai": str(elias)},
                {"label": "Hidden margin ASF", "nilai": str(hidden)},
            ],
        )

    raise ValueError(f"Skema '{invoice.skema}' tidak dikenal.")


# ============================================================ PEMBAYARAN
def process_payment(
    invoice: InvoiceData,
    amount_paid,
    *,
    total_komisi: Decimal | None = None,
    sudah_dibayar: Decimal = Decimal("0"),
    sudah_dicairkan: Decimal = Decimal("0"),
    sudah_basis: Decimal = Decimal("0"),
    bonus_persen: Decimal | None = None,
) -> PaymentResult:
    """Pecah satu uang masuk secara prorata.

        Rasio Bersih        = (Total Invoice - Total Komisi) / Total Invoice
        Dasar Bonus Masuk   = amount_paid x Rasio Bersih
        Bonus Sales (4,3%)  = Dasar Bonus Masuk x 4,3%
        Komisi Siap Cair    = amount_paid x (Total Komisi / Total Invoice)

    `sudah_dibayar`, `sudah_dicairkan`, dan `sudah_basis` dipakai untuk
    PEMBULATAN CICILAN TERAKHIR. Prorata per cicilan hampir selalu menyisakan
    pecahan sen; kalau tiap cicilan dibulatkan sendiri-sendiri, jumlah seluruh
    `commission_released` tidak akan sama persis dengan `total_komisi` — akan
    ada sisa utang komisi beberapa rupiah yang menggantung selamanya di
    neraca — dan jumlah `net_bonus_basis` tidak akan sama dengan
    (Invoice - Komisi). Karena itu cicilan yang MELUNASI faktur menyerap
    seluruh sisanya, untuk kedua angka.

    Pemanggil wajib mengakumulasi ketiganya dari hasil sebelumnya. Kalau
    `sudah_basis` tidak diisi padahal ada cicilan sebelumnya, cicilan pelunas
    akan menyerap terlalu banyak.

    Bawaannya memakai `total_pengurang` — komisi pihak ketiga DITAMBAH hak
    mitra — sesuai spesifikasi client: "Total Pengurang Invoice (yang keluar
    dari ASF) = Hak Mitra Andre + Komisi Pihak Ketiga". Kirim `total_komisi`
    sendiri hanya kalau ada kesepakatan yang menyimpang dari itu.
    """
    total = _q(invoice.total_invoice)
    if total <= 0:
        raise ValueError("Total invoice harus lebih dari 0.")

    bayar = _q(amount_paid)
    if bayar <= 0:
        raise ValueError("Jumlah pembayaran harus lebih dari 0.")

    sudah = _q(sudah_dibayar)
    if sudah + bayar > total:
        raise ValueError(
            f"Pembayaran {bayar} melebihi sisa piutang ({total - sudah})."
        )

    komisi = (_q(total_komisi) if total_komisi is not None
              else calculate_invoice_commission(invoice).total_pengurang)
    if komisi > total:
        raise ValueError(f"Total komisi {komisi} melebihi nilai faktur {total}.")

    persen_bonus = (_d(bonus_persen) if bonus_persen is not None
                    else BONUS_SALES_PERSEN)

    # Rasio disimpan penuh (tidak dibulatkan ke sen) supaya galat tidak
    # menumpuk; pembulatan hanya di angka rupiah akhir.
    net_ratio = (total - komisi) / total
    rasio_komisi = komisi / total

    total_dibayar = _q(sudah + bayar)
    lunas = total_dibayar >= total

    if lunas:
        # Cicilan pelunas menyerap sisa pembulatan: dasar bonus & komisi cair
        # dihitung dari SELISIH total, bukan dari cicilan ini sendiri.
        net_bonus_basis = _q(total - komisi) - _q(sudah_basis)
        commission_released = komisi - _q(sudah_dicairkan)
    else:
        net_bonus_basis = _q(bayar * net_ratio)
        commission_released = _q(bayar * rasio_komisi)

    return PaymentResult(
        amount_paid=bayar,
        net_ratio=net_ratio,
        net_bonus_basis=net_bonus_basis,
        bonus_amount=_q(net_bonus_basis * persen_bonus / HUNDRED),
        commission_released=commission_released,
        total_dibayar=total_dibayar,
        sisa_piutang=_q(total - total_dibayar),
        lunas=lunas,
    )
