"""Lembar Hitung: kesepakatan bagi hasil & komisi per faktur.

DIREKONSTRUKSI dari `tests/test_profit_sheet.py`, pemakaian di
`payout_service`/`void_service`, kode akun di `accounts_map`, dan aturan 1-8
"Lembar Hitung" di CLAUDE.md — berkas aslinya tidak pernah ikut ter-commit.

APA YANG DIKERJAKAN MODUL INI, DAN APA YANG TIDAK

Ia MENGHITUNG dari angka faktur yang sudah terposting, lalu menjurnal
HASILNYA saja:

    disetujui   Dr Beban Bagi Hasil (6-1300) / Cr Utang Bagi Hasil (2-1700)
                Dr Beban Komisi     (6-1100) / Cr Utang Komisi     (2-1600)
    ditransfer  Dr Utang .../ Cr Kas
    dibatalkan  kebalikan dari jurnal persetujuan

Ia TIDAK PERNAH menyentuh Pendapatan, HPP, atau Persediaan. Kalau suatu saat
ada yang menambahkan `Line()` ke akun-akun itu di sini, laba kotor jadi bisa
terkontaminasi kesepakatan dan aturan anti-double-counting client batal.

URUTAN EVALUASI ADALAH ATURAN BISNIS, BUKAN DETAIL TEKNIS
Baris berdasar `bagian_asf` WAJIB dihitung setelah seluruh baris bagi hasil,
karena bagian ASF adalah SISA setelah mitra mengambil haknya. Kalau dibalik,
komisi pihak ketiga terhitung dari profit bersama dan nilainya dua kali lipat
(4% x 300 = 12, benarnya 4% x 150 = 6). Angkanya tetap terlihat masuk akal,
jadi tidak akan ketahuan sampai ada yang protes soal bayarannya. Dikunci di
`test_komisi_pihak_ketiga_dari_bagian_asf_bukan_profit_bersama`.

HIDDEN MARGIN TIDAK DIJURNAL. Selisih modal perjanjian terhadap HPP riil
adalah hak internal penuh dan sifatnya turunan; menjurnalnya sebagai
pendapatan terpisah membuat laba dobel dan persediaan melenceng.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Account, Invoice, InvoiceLine, Journal, JournalEntry, Product,
    ProfitSheet, ProfitSheetLine,
)
from ..models.profit_sheet import DASAR, JENIS
from .accounts_map import code_to_id, ensure_account
from .journal import Line, post_journal
from .numbering import next_number
from .units import clean_pack_size

CENT = Decimal("0.01")
QTYQ = Decimal("0.0001")
Z = Decimal("0")

# Pasangan akun per jenis baris: (beban, utang).
AKUN = {
    "komisi": ("commission_expense", "commission_payable"),
    "bagi_hasil": ("profit_share_expense", "profit_share_payable"),
}


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _qn(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(QTYQ)


def _d(v) -> Decimal | None:
    return None if v in (None, "") else Decimal(str(v))


# --------------------------------------------------------------- pembacaan

async def _hpp_riil(db: AsyncSession, company_id: str, invoice_id: str) -> Decimal:
    """HPP faktur ini APA ADANYA dari jurnal, bukan dihitung ulang dari stok.

    `avg_cost` sudah bergerak sejak faktur diposting, jadi menghitung ulang
    memberi angka berbeda tiap hari dan lembar berhenti bisa dipakai memeriksa
    pembukuan.
    """
    acc = await code_to_id(db, company_id)
    cogs = acc.get("cogs")
    if cogs is None:
        return Z
    rows = (await db.execute(
        select(JournalEntry.debit, JournalEntry.credit)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(Journal.source_id == invoice_id,
               Journal.source_type == "invoice",
               JournalEntry.account_id == cogs)
    )).all()
    return _q(sum((Decimal(str(d)) - Decimal(str(k)) for d, k in rows), Z))


async def _jumlah_dus(db: AsyncSession, invoice_id: str) -> Decimal:
    """Jumlah dus PECAHAN. 18 botol dari dus isi 12 = 1,5 dus.

    Sengaja tidak dibulatkan ke atas: itu keputusan bisnis, dan membulatkan
    membuat orang dibayar lebih dari kesepakatan.
    """
    rows = (await db.execute(
        select(InvoiceLine.quantity, Product.pack_size)
        .join(Product, Product.id == InvoiceLine.product_id)
        .where(InvoiceLine.invoice_id == invoice_id)
    )).all()
    total = Z
    for qty, pack in rows:
        total += Decimal(str(qty or 0)) / Decimal(clean_pack_size(pack))
    return _qn(total)


# ------------------------------------------------------------- perhitungan

def _dasar_nilai(
    dasar: str, *, penjualan: Decimal, hpp_riil: Decimal,
    hpp_dasar_komisi: Decimal | None, modal_perjanjian: Decimal | None,
    pengurang_per_dus: Decimal, jumlah_dus: Decimal, bagian_asf: Decimal | None,
) -> Decimal:
    """Nilai dasar hitung untuk satu baris. Daftar TERTUTUP — lihat models."""
    if dasar == "omzet":
        return penjualan
    if dasar == "margin_riil":
        return penjualan - hpp_riil
    if dasar == "margin_komisi":
        if hpp_dasar_komisi is None:
            raise ValueError(
                "Dasar 'margin_komisi' butuh HPP Dasar Komisi diisi."
            )
        return penjualan - hpp_dasar_komisi
    if dasar == "margin_min_pengurang":
        return penjualan - hpp_riil - (pengurang_per_dus * jumlah_dus)
    if dasar == "profit_bersama":
        if modal_perjanjian is None:
            raise ValueError(
                "Bagi hasil butuh Modal Perjanjian diisi — tanpa itu tidak ada "
                "profit bersama yang bisa dibagi."
            )
        return penjualan - modal_perjanjian
    if dasar == "bagian_asf":
        if modal_perjanjian is None:
            raise ValueError(
                "Dasar 'bagian_asf' butuh Modal Perjanjian diisi."
            )
        return bagian_asf if bagian_asf is not None else Z
    if dasar == "nominal":
        return Z          # nominal tidak menghitung; angkanya diketik langsung
    raise ValueError(
        f"Dasar hitung '{dasar}' tidak dikenal. Pilihan: {', '.join(DASAR)}."
    )


def hitung_baris(
    baris: list[dict], *, penjualan: Decimal, hpp_riil: Decimal,
    hpp_dasar_komisi: Decimal | None, modal_perjanjian: Decimal | None,
    pengurang_per_dus: Decimal, jumlah_dus: Decimal,
) -> list[dict]:
    """Hitung seluruh baris. Fungsi MURNI — tidak menyentuh database.

    Dua lintasan, dan urutannya adalah aturan bisnis: `bagian_asf` adalah SISA
    setelah mitra bagi hasil mengambil bagiannya, jadi ia hanya bisa dihitung
    setelah seluruh baris lain selesai.
    """
    if not baris:
        raise ValueError("Lembar hitung harus punya minimal satu baris.")

    def satu(raw: dict, bagian_asf: Decimal | None) -> dict:
        jenis = (raw.get("jenis") or "").strip()
        if jenis not in JENIS:
            raise ValueError(
                f"Jenis '{jenis}' tidak dikenal. Pilihan: {', '.join(JENIS)}."
            )
        dasar = (raw.get("dasar") or "").strip()
        nilai_dasar = _q(_dasar_nilai(
            dasar, penjualan=penjualan, hpp_riil=hpp_riil,
            hpp_dasar_komisi=hpp_dasar_komisi,
            modal_perjanjian=modal_perjanjian,
            pengurang_per_dus=pengurang_per_dus, jumlah_dus=jumlah_dus,
            bagian_asf=bagian_asf,
        ))
        if dasar == "nominal":
            jumlah = _q(raw.get("nominal"))
        else:
            persen = Decimal(str(raw.get("persen") or 0))
            jumlah = _q(nilai_dasar * persen / Decimal("100"))
        return {
            "payee_name": (raw.get("payee_name") or "").strip(),
            "jenis": jenis,
            "dasar": dasar,
            "persen": _q(raw.get("persen")),
            "nominal": _q(raw.get("nominal")),
            "basis_amount": nilai_dasar,
            "amount": jumlah,
            "note": (raw.get("note") or "").strip() or None,
        }

    # Lintasan 1: semua kecuali bagian_asf.
    hasil: list[dict | None] = [None] * len(baris)
    for i, raw in enumerate(baris):
        if (raw.get("dasar") or "").strip() != "bagian_asf":
            hasil[i] = satu(raw, None)

    # Bagian ASF = profit bersama dikurangi seluruh hak mitra bagi hasil.
    bagian_asf = None
    if any((r.get("dasar") or "").strip() == "bagian_asf" for r in baris):
        profit_bersama = _q(_dasar_nilai(
            "profit_bersama", penjualan=penjualan, hpp_riil=hpp_riil,
            hpp_dasar_komisi=hpp_dasar_komisi,
            modal_perjanjian=modal_perjanjian,
            pengurang_per_dus=pengurang_per_dus, jumlah_dus=jumlah_dus,
            bagian_asf=None,
        ))
        hak_mitra = sum(
            (b["amount"] for b in hasil if b and b["jenis"] == "bagi_hasil"), Z
        )
        bagian_asf = _q(profit_bersama - hak_mitra)

    # Lintasan 2: baris bagian_asf, kini dasarnya sudah diketahui.
    for i, raw in enumerate(baris):
        if hasil[i] is None:
            hasil[i] = satu(raw, bagian_asf)

    return [b for b in hasil if b is not None]


# ----------------------------------------------------------------- perintah

async def create_sheet(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    invoice_id: str, on_date: date, baris: list[dict],
    modal_perjanjian=None, hpp_dasar_komisi=None, pengurang_per_dus=None,
    notes: str | None = None,
) -> ProfitSheet:
    """Buat lembar (status draft). Belum ada jurnal apa pun sampai disetujui."""
    invoice = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id,
                              Invoice.company_id == company_id)
    )).scalar_one_or_none()
    if invoice is None:
        raise ValueError("Faktur tidak ditemukan.")

    ada = (await db.execute(
        select(ProfitSheet).where(ProfitSheet.invoice_id == invoice_id,
                                  ProfitSheet.status != "batal")
    )).scalar_one_or_none()
    if ada is not None:
        raise ValueError(
            f"Faktur {invoice.number} sudah punya lembar hitung {ada.number}. "
            f"Batalkan lembar itu dulu bila ingin menghitung ulang."
        )

    # Dasar komisi memakai nilai SEBELUM PPN: pajak bukan hasil usaha yang
    # boleh dibagi, ia titipan negara.
    penjualan = _q(invoice.subtotal)
    hpp_riil = await _hpp_riil(db, company_id, invoice_id)
    jumlah_dus = await _jumlah_dus(db, invoice_id)
    pengurang = _q(pengurang_per_dus)

    dihitung = hitung_baris(
        baris, penjualan=penjualan, hpp_riil=hpp_riil,
        hpp_dasar_komisi=_d(hpp_dasar_komisi),
        modal_perjanjian=_d(modal_perjanjian),
        pengurang_per_dus=pengurang, jumlah_dus=jumlah_dus,
    )

    # Jaring pengaman salah ketik persen. Margin RIIL yang jadi batas, bukan
    # margin perjanjian: yang benar-benar dimiliki ASF cuma sebesar itu, dan
    # membagi lebih dari itu berarti membayar dari modal kerja.
    total_hak = _q(sum((b["amount"] for b in dihitung), Z))
    margin_riil = _q(penjualan - hpp_riil)
    if total_hak > margin_riil:
        raise ValueError(
            f"Total hak {total_hak:,.2f} melebihi margin riil faktur "
            f"{margin_riil:,.2f}. Periksa persentasenya."
        )

    number = await next_number(
        db, company_id=company_id, doc_type="profit_sheet", on_date=on_date,
        prefix="LH", reset="monthly",
    )
    sheet = ProfitSheet(
        company_id=company_id, number=number, date=on_date,
        invoice_id=invoice_id, status="draft",
        penjualan=penjualan, hpp_riil=hpp_riil, jumlah_dus=jumlah_dus,
        modal_perjanjian=_d(modal_perjanjian),
        hpp_dasar_komisi=_d(hpp_dasar_komisi),
        pengurang_per_dus=pengurang, notes=notes, created_by=user_id,
        lines=[
            ProfitSheetLine(urutan=i, **b) for i, b in enumerate(dihitung)
        ],
    )
    db.add(sheet)
    await db.flush()
    return sheet


async def approve_sheet(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    sheet_id: str, on_date: date,
) -> ProfitSheet:
    """Akui bebannya. Inilah titik pengakuan komisi & hak mitra.

    Diakui PENUH di sini, bukan dicicil per pembayaran: bebannya menempel ke
    penjualannya (matching principle). Prorata hanya menentukan berapa yang
    boleh DITRANSFER — lihat payout_service.porsi_komisi_cair.
    """
    sheet = await _ambil(db, company_id, sheet_id)
    if sheet.status != "draft":
        raise ValueError(
            f"Lembar {sheet.number} berstatus {sheet.status}, hanya lembar "
            f"draft yang bisa disetujui."
        )

    per_jenis: dict[str, Decimal] = {}
    for b in sheet.lines:
        per_jenis[b.jenis] = per_jenis.get(b.jenis, Z) + _q(b.amount)

    lines: list[Line] = []
    for jenis, total in per_jenis.items():
        if total == 0:
            continue
        beban, utang = AKUN[jenis]
        lines.append(Line(await ensure_account(db, company_id, beban),
                          debit=total, description=f"Beban {jenis}"))
        lines.append(Line(await ensure_account(db, company_id, utang),
                          credit=total, description=f"Utang {jenis}"))

    if lines:
        journal = await post_journal(
            db, company_id=company_id,
            number=sheet.number.replace("LH", "JV"), on_date=on_date,
            lines=lines, memo=f"Lembar hitung {sheet.number}",
            source_type="profit_sheet", source_id=sheet.id, created_by=user_id,
        )
        sheet.journal_id = journal.id

    sheet.status = "disetujui"
    await db.flush()
    return sheet


async def transfer_line(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    line_id: str, on_date: date, paid_account_code: str = "1-1000",
) -> ProfitSheetLine:
    """Bayarkan satu hak. Menutup utang — TIDAK menggerakkan laba.

    Terkunci sampai fakturnya lunas. Yang dijaga di sini adalah KAS: bebannya
    sudah diakui saat lembar disetujui, jadi menahan transfer tidak menunda
    pengakuan apa pun, ia cuma mencegah uang keluar sebelum uang masuk.
    """
    baris = (await db.execute(
        select(ProfitSheetLine).where(ProfitSheetLine.id == line_id)
    )).scalar_one_or_none()
    if baris is None:
        raise ValueError("Baris lembar hitung tidak ditemukan.")
    sheet = await _ambil(db, company_id, baris.sheet_id)
    if sheet.status not in ("disetujui", "ditransfer"):
        raise ValueError(
            f"Lembar {sheet.number} belum disetujui, jadi haknya belum bisa "
            f"ditransfer."
        )
    if baris.settlement_journal_id:
        raise ValueError(
            f"Hak {baris.payee_name} pada lembar {sheet.number} sudah pernah "
            f"ditransfer."
        )

    invoice = (await db.execute(
        select(Invoice).where(Invoice.id == sheet.invoice_id)
    )).scalar_one()
    if invoice.status != "paid":
        raise ValueError(
            f"Faktur {invoice.number} belum lunas, jadi hak {baris.payee_name} "
            f"belum boleh ditransfer."
        )

    kas = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == paid_account_code)
    )).scalar_one_or_none()
    if not kas:
        raise ValueError(f"Akun {paid_account_code} tidak ada di bagan akun.")
    _, utang = AKUN[baris.jenis]
    nilai = _q(baris.amount)

    journal = await post_journal(
        db, company_id=company_id,
        number=f"{sheet.number}/T{baris.urutan + 1}".replace("LH", "JV"),
        on_date=on_date,
        lines=[
            Line(await ensure_account(db, company_id, utang), debit=nilai,
                 description=f"Transfer {baris.payee_name}"),
            Line(kas, credit=nilai, description=f"Kas keluar {baris.payee_name}"),
        ],
        memo=f"Transfer {baris.payee_name} — {sheet.number}",
        source_type="profit_sheet_line", source_id=baris.id, created_by=user_id,
    )
    baris.settlement_journal_id = journal.id

    if all(b.settlement_journal_id for b in sheet.lines):
        sheet.status = "ditransfer"
    await db.flush()
    return baris


async def void_sheet(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    sheet_id: str, on_date: date, reason: str | None = None,
) -> ProfitSheet:
    """Batalkan lembar & balik jurnalnya.

    Wajib dipakai untuk faktur yang tak akan pernah lunas — tanpa ini Utang
    Bagi Hasil & Utang Komisi menumpuk selamanya dengan angka yang tidak akan
    pernah dibayar.
    """
    sheet = await _ambil(db, company_id, sheet_id)
    if sheet.status == "batal":
        raise ValueError(f"Lembar {sheet.number} sudah dibatalkan.")

    # Hak yang sudah ditransfer berarti uangnya sudah keluar. Membalik bebannya
    # akan membuat kas berkurang tanpa beban yang menjelaskannya.
    sudah = [b.payee_name for b in sheet.lines if b.settlement_journal_id]
    if sudah:
        raise ValueError(
            f"Lembar {sheet.number} tidak bisa dibatalkan karena hak "
            f"{', '.join(sudah)} sudah ditransfer. Uangnya sudah keluar."
        )

    if sheet.status != "draft" and sheet.journal_id:
        per_jenis: dict[str, Decimal] = {}
        for b in sheet.lines:
            per_jenis[b.jenis] = per_jenis.get(b.jenis, Z) + _q(b.amount)

        lines: list[Line] = []
        for jenis, total in per_jenis.items():
            if total == 0:
                continue
            beban, utang = AKUN[jenis]
            # Kebalikan persis dari jurnal persetujuan.
            lines.append(Line(await ensure_account(db, company_id, utang),
                              debit=total, description=f"Batal utang {jenis}"))
            lines.append(Line(await ensure_account(db, company_id, beban),
                              credit=total, description=f"Batal beban {jenis}"))
        if lines:
            journal = await post_journal(
                db, company_id=company_id,
                number=f"{sheet.number}/BATAL".replace("LH", "JV"),
                on_date=on_date, lines=lines,
                memo=f"Pembatalan lembar hitung {sheet.number}"
                     + (f" — {reason}" if reason else ""),
                source_type="profit_sheet_void", source_id=sheet.id,
                created_by=user_id,
            )
            sheet.void_journal_id = journal.id

    sheet.status = "batal"
    sheet.void_reason = (reason or "").strip()[:255] or None
    await db.flush()
    return sheet


async def _ambil(db: AsyncSession, company_id: str, sheet_id: str) -> ProfitSheet:
    sheet = (await db.execute(
        select(ProfitSheet).where(ProfitSheet.id == sheet_id,
                                  ProfitSheet.company_id == company_id)
    )).scalar_one_or_none()
    if sheet is None:
        raise ValueError("Lembar hitung tidak ditemukan.")
    return sheet
