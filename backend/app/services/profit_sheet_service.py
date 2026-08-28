"""Lembar Hitung: bagi hasil & komisi bertingkat atas satu faktur.

Rancangan di RANCANGAN-LEMBAR-HITUNG.md, penjaganya tests/test_profit_sheet.py.

Alur & jurnal
-------------
    create_sheet   -> status "draft"        (tidak menjurnal apa pun)
    approve_sheet  -> status "disetujui"    Dr 6-1300 Beban Bagi Hasil
                                                Cr 2-1700 Utang Bagi Hasil
                                            Dr 6-1100 Beban Komisi
                                                Cr 2-1600 Utang Komisi
    transfer_line  -> per baris             Dr Utang / Cr Kas-Bank (neraca saja)
    void_sheet     -> status "batal"        jurnal balik atas yang belum cair

Yang TIDAK pernah disentuh modul ini: Pendapatan, HPP, dan Persediaan. Yang
dijurnal hanya HASIL kesepakatan. Kalau suatu saat ada yang menambahkan
`Line()` ke akun pendapatan/HPP/persediaan di sini, laba kotor jadi bisa
terkontaminasi kesepakatan internal dan aturan anti-double-counting client
batal - kerusakan yang tidak akan pernah muncul sebagai error.

Kenapa beban diakui saat DISETUJUI dan bukan saat ditransfer: nilainya sudah
disepakati dan sudah jadi kewajiban. Menunggu transfer berarti utang ke mitra
tidak muncul di neraca sama sekali. Transfer setelah itu murni neraca dan
tidak boleh menggerakkan Laba Rugi sedikit pun.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ProfitSheet, ProfitSheetLine, Invoice, InvoiceLine, Product, Account,
    JournalEntry,
)
from .accounts_map import DEFAULT_CODES, ensure_account
from .journal import Line, post_journal
from .numbering import next_number

CENT = Decimal("0.01")
DUS = Decimal("0.0001")
HUNDRED = Decimal("100")

# Faktur yang barangnya sudah keluar. Lembar tidak boleh dibuat atas draft
# (HPP-nya belum ada di jurnal) maupun void (transaksinya dibatalkan).
FAKTUR_SAH = ("posted", "paid", "overdue")

# Status lembar yang jurnalnya sudah ada.
SUDAH_BERJURNAL = ("disetujui", "ditransfer")


# ------------------------------------------------------------ DAFTAR TERTUTUP
# Daftar dasar perhitungan SENGAJA tertutup. "nominal" adalah pintu darurat
# yang menyimpan ANGKA, bukan aturan - custom berarti user mengetik angka,
# BUKAN user mendefinisikan rumus. Begitu rumus bisa diketik user, angkanya
# berhenti bisa dijelaskan dan tidak bisa dites. Menambah dasar baru =
# menambah entri bernama jelas di sini, bukan membuka evaluator.
DASAR: dict[str, str] = {
    "omzet": "Penjualan (sebelum PPN)",
    "margin_riil": "Penjualan - HPP riil",
    "margin_komisi": "Penjualan - HPP dasar komisi",
    "margin_min_pengurang": "Penjualan - HPP riil - (pengurang per dus x dus)",
    "profit_bersama": "Penjualan - Modal Perjanjian",
    "bagian_asf": "Profit bersama - seluruh bagian mitra",
    "nominal": "Angka yang diketik langsung",
}

# Dasar yang WAJIB dievaluasi paling akhir. Lihat _evaluasi() - urutan ini
# menentukan benar/salahnya angka, bukan sekadar kerapian.
FASE_AKHIR = ("bagian_asf",)

# Jenis hak -> pasangan akun (kunci accounts_map.AUTO_CREATE).
JENIS_AKUN: dict[str, tuple[str, str]] = {
    "komisi": ("commission_expense", "commission_payable"),          # 6-1100 / 2-1600
    "bagi_hasil": ("profit_share_expense", "profit_share_payable"),  # 6-1300 / 2-1700
}


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _opsional(v) -> Decimal | None:
    return None if v is None or v == "" else _q(v)


# ------------------------------------------------------------ PENGAMBIL ANGKA
async def _faktur_sah(db: AsyncSession, company_id: str, invoice_id: str) -> Invoice:
    inv = (await db.execute(
        select(Invoice).where(Invoice.company_id == company_id,
                              Invoice.id == invoice_id)
    )).scalar_one_or_none()
    if inv is None:
        raise ValueError("Faktur tidak ditemukan.")
    if inv.status not in FAKTUR_SAH:
        raise ValueError(
            f"Faktur {inv.number} berstatus '{inv.status}' - lembar hitung baru "
            f"bisa dibuat setelah faktur diposting (barang keluar)."
        )
    return inv


async def _hpp_riil(db: AsyncSession, company_id: str, inv: Invoice) -> Decimal:
    """HPP faktur ini APA ADANYA dari `journal_entries`.

    Sengaja TIDAK dihitung ulang dari stok: `avg_cost` sudah bergerak sejak
    faktur diposting, jadi menghitung ulang akan memberi angka berbeda tiap
    kali lembar dibuka - dan lembar berhenti bisa dipakai memeriksa pembukuan.
    Sengaja pula tidak bisa ditimpa user; yang boleh ditimpa `hpp_dasar_komisi`.
    """
    if not inv.journal_id:
        return Decimal("0.00")
    rows = (await db.execute(
        select(JournalEntry.debit, JournalEntry.credit)
        .join(Account, Account.id == JournalEntry.account_id)
        .where(JournalEntry.journal_id == inv.journal_id,
               Account.company_id == company_id,
               Account.code == DEFAULT_CODES["cogs"])
    )).all()
    return _q(sum((_q(d) - _q(k) for d, k in rows), Decimal("0")))


async def _jumlah_dus(db: AsyncSession, invoice_id: str) -> Decimal:
    """Jumlah dus faktur, PECAHAN - 18 botol dari dus isi 12 = 1,5 dus.

    Bukan dibulatkan ke atas: itu keputusan bisnis yang sama dengan
    `commission_service.persen_margin_min_ongkir`, dan dua tempat tidak boleh
    menjawab berbeda untuk faktur yang sama. `quantity` SELALU botol.
    """
    rows = (await db.execute(
        select(InvoiceLine.quantity, Product.pack_size)
        .join(Product, Product.id == InvoiceLine.product_id, isouter=True)
        .where(InvoiceLine.invoice_id == invoice_id)
    )).all()
    dus = Decimal("0")
    for botol, pack in rows:
        isi = Decimal(str(pack or 1))
        if isi <= 0:
            isi = Decimal("1")
        dus += _q(botol) / isi
    return dus.quantize(DUS)


# ------------------------------------------------------------ PERHITUNGAN
class Konteks:
    """Angka dasar satu lembar. Murni data - tidak menyentuh DB."""

    def __init__(self, *, penjualan: Decimal, hpp_riil: Decimal,
                 hpp_dasar_komisi: Decimal, modal_perjanjian: Decimal | None,
                 pengurang_per_dus: Decimal | None, jumlah_dus: Decimal):
        self.penjualan = penjualan
        self.hpp_riil = hpp_riil
        self.hpp_dasar_komisi = hpp_dasar_komisi
        self.modal_perjanjian = modal_perjanjian
        self.pengurang_per_dus = pengurang_per_dus
        self.jumlah_dus = jumlah_dus
        # Diisi _evaluasi() setelah seluruh baris bagi hasil selesai.
        self.bagian_asf = Decimal("0.00")

    @property
    def margin_riil(self) -> Decimal:
        return _q(self.penjualan - self.hpp_riil)

    @property
    def margin_komisi(self) -> Decimal:
        return _q(self.penjualan - self.hpp_dasar_komisi)

    @property
    def potongan(self) -> Decimal:
        return _q(_q(self.pengurang_per_dus) * self.jumlah_dus)

    @property
    def profit_bersama(self) -> Decimal:
        if self.modal_perjanjian is None:
            return Decimal("0.00")
        return _q(self.penjualan - self.modal_perjanjian)

    @property
    def hidden_margin(self) -> Decimal:
        """Selisih modal perjanjian dengan HPP sebenarnya.

        TIDAK pernah dijurnal - ia turunan. Menjurnalnya sebagai pendapatan
        terpisah membuat laba dobel dan persediaan melenceng.
        """
        if self.modal_perjanjian is None:
            return Decimal("0.00")
        return _q(self.modal_perjanjian - self.hpp_riil)


def _nilai_dasar(kode: str, ctx: Konteks) -> Decimal:
    if kode == "omzet":
        return ctx.penjualan
    if kode == "margin_riil":
        return ctx.margin_riil
    if kode == "margin_komisi":
        return ctx.margin_komisi
    if kode == "margin_min_pengurang":
        # Pengurang yang melahap seluruh margin tidak boleh jadi komisi
        # negatif - itu berarti menagih uang ke orang, bukan membayarnya.
        sisa = _q(ctx.margin_riil - ctx.potongan)
        return sisa if sisa > 0 else Decimal("0.00")
    if kode == "profit_bersama":
        return ctx.profit_bersama
    if kode == "bagian_asf":
        return ctx.bagian_asf
    raise ValueError(f"Dasar '{kode}' tidak dikenal.")


def _periksa_baris(baris: list[dict], ctx: Konteks) -> None:
    butuh_modal = {"profit_bersama", "bagian_asf"}
    for b in baris:
        jenis = str(b.get("jenis") or "")
        dasar = str(b.get("dasar") or "")
        if jenis not in JENIS_AKUN:
            raise ValueError(
                f"Jenis '{jenis}' tidak dikenal. Pilihan: "
                f"{', '.join(sorted(JENIS_AKUN))}."
            )
        if dasar not in DASAR:
            raise ValueError(
                f"Dasar '{dasar}' tidak dikenal. Pilihan: "
                f"{', '.join(sorted(DASAR))}."
            )
        if not str(b.get("payee_name") or "").strip():
            raise ValueError("Setiap baris harus punya nama penerima.")
        if dasar == "nominal":
            if b.get("nominal") is None:
                raise ValueError("Dasar 'nominal' butuh angka yang diketik.")
        elif b.get("persen") is None:
            raise ValueError(f"Dasar '{dasar}' butuh persen.")
        if dasar in butuh_modal and ctx.modal_perjanjian is None:
            raise ValueError(
                f"Dasar '{dasar}' butuh Modal Perjanjian diisi lebih dulu."
            )


def _evaluasi(baris: list[dict], ctx: Konteks) -> list[Decimal]:
    """Nilai tiap baris, hasilnya mengikuti urutan input.

    URUTAN EVALUASINYA yang penting, bukan urutan tampilnya. `bagian_asf`
    WAJIB dihitung setelah SELURUH baris bagi hasil selesai: kalau dibalik,
    komisi pihak ketiga terhitung dari profit bersama dan nilainya dua kali
    lipat (4% x 300 = 12, benarnya 4% x 150 = 6). Angkanya tetap masuk akal,
    jadi tidak akan ketahuan sampai ada yang protes bayarannya.
    """
    hasil: list[Decimal | None] = [None] * len(baris)

    def hitung(b: dict) -> Decimal:
        dasar = str(b["dasar"])
        if dasar == "nominal":
            return _q(b.get("nominal"))
        return _q(_nilai_dasar(dasar, ctx) * _q(b.get("persen")) / HUNDRED)

    # Fase 1 - semua yang tidak bergantung pada bagian ASF.
    for i, b in enumerate(baris):
        if str(b["dasar"]) not in FASE_AKHIR:
            hasil[i] = hitung(b)

    # Bagian ASF = sisa profit bersama setelah seluruh mitra mengambil
    # bagiannya. Baris bagi hasil yang justru BERDASAR `bagian_asf` tidak ikut
    # mengurangi di sini - kalau ikut, definisinya jadi melingkar.
    bagian_mitra = sum(
        (hasil[i] or Decimal("0")
         for i, b in enumerate(baris)
         if b["jenis"] == "bagi_hasil" and str(b["dasar"]) not in FASE_AKHIR),
        Decimal("0"),
    )
    ctx.bagian_asf = _q(ctx.profit_bersama - bagian_mitra)

    # Fase 2 - baru sekarang bagian ASF punya nilai.
    for i, b in enumerate(baris):
        if hasil[i] is None:
            hasil[i] = hitung(b)

    return [x if x is not None else Decimal("0.00") for x in hasil]


# ------------------------------------------------------------ BUAT LEMBAR
async def create_sheet(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    invoice_id: str, on_date: date, baris: list[dict],
    modal_perjanjian=None, hpp_dasar_komisi=None, pengurang_per_dus=None,
    note: str | None = None,
) -> ProfitSheet:
    """Susun lembar dan simpan sebagai draft. TIDAK menjurnal apa pun."""
    inv = await _faktur_sah(db, company_id, invoice_id)

    lama = (await db.execute(
        select(ProfitSheet).where(ProfitSheet.invoice_id == invoice_id,
                                  ProfitSheet.status != "batal")
    )).scalar_one_or_none()
    if lama is not None:
        raise ValueError(
            f"Faktur {inv.number} sudah punya lembar hitung {lama.number}. "
            f"Batalkan lembar itu dulu kalau kesepakatannya berubah."
        )

    if not baris:
        raise ValueError("Lembar hitung butuh minimal satu baris penerima.")

    hpp = await _hpp_riil(db, company_id, inv)
    ctx = Konteks(
        penjualan=_q(inv.subtotal),
        hpp_riil=hpp,
        # Default mengikuti HPP sebenarnya; diisi berbeda hanya kalau
        # kesepakatannya memakai modal lain sebagai dasar komisi.
        hpp_dasar_komisi=_opsional(hpp_dasar_komisi) or hpp,
        modal_perjanjian=_opsional(modal_perjanjian),
        pengurang_per_dus=_opsional(pengurang_per_dus),
        jumlah_dus=await _jumlah_dus(db, invoice_id),
    )

    _periksa_baris(baris, ctx)
    nilai = _evaluasi(baris, ctx)

    # Jaring pengaman salah ketik persen: seluruh hak yang dijanjikan tidak
    # boleh melebihi margin yang benar-benar ada. Tanpa ini satu digit
    # kelebihan langsung jadi beban besar yang terlihat wajar di jurnal.
    total = _q(sum(nilai, Decimal("0")))
    if total > ctx.margin_riil:
        raise ValueError(
            f"Total hak {total} melebihi margin riil faktur "
            f"{ctx.margin_riil} - periksa lagi persen yang diketik."
        )

    sheet = ProfitSheet(
        company_id=company_id,
        number=await next_number(db, company_id=company_id,
                                 doc_type="profit_sheet", on_date=on_date,
                                 prefix="LH", reset="monthly"),
        date=on_date,
        invoice_id=invoice_id,
        status="draft",
        penjualan=ctx.penjualan,
        hpp_riil=ctx.hpp_riil,
        hpp_dasar_komisi=ctx.hpp_dasar_komisi,
        modal_perjanjian=ctx.modal_perjanjian,
        pengurang_per_dus=ctx.pengurang_per_dus,
        jumlah_dus=ctx.jumlah_dus,
        profit_bersama=ctx.profit_bersama,
        bagian_asf=ctx.bagian_asf,
        hidden_margin=ctx.hidden_margin,
        note=note,
        created_by=user_id,
        lines=[
            ProfitSheetLine(
                sequence=i,
                payee_name=str(b["payee_name"]).strip(),
                jenis=str(b["jenis"]),
                dasar=str(b["dasar"]),
                persen=_opsional(b.get("persen")),
                nominal=_opsional(b.get("nominal")),
                amount=nilai[i],
                note=b.get("note"),
            )
            for i, b in enumerate(baris)
        ],
    )
    db.add(sheet)
    await db.flush()
    return sheet


# ------------------------------------------------------------ SETUJUI
async def approve_sheet(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    sheet_id: str, on_date: date,
) -> ProfitSheet:
    """Akui seluruh hak di lembar ini sebagai beban + utang.

    Hanya dua pasang akun yang tersentuh. Pendapatan, HPP, dan Persediaan
    TIDAK boleh muncul di sini - lihat docstring modul.
    """
    sheet = await _ambil(db, company_id, sheet_id)
    if sheet.status != "draft":
        raise ValueError(
            f"Lembar {sheet.number} berstatus '{sheet.status}' - hanya draft "
            f"yang bisa disetujui."
        )

    lines: list[Line] = []
    for baris in sheet.lines:
        beban_key, utang_key = JENIS_AKUN[baris.jenis]
        beban_id = await ensure_account(db, company_id, beban_key)
        utang_id = await ensure_account(db, company_id, utang_key)
        baris.expense_account_id = beban_id
        baris.payable_account_id = utang_id
        nilai = _q(baris.amount)
        if nilai <= 0:
            continue
        keterangan = f"{baris.payee_name} - {DASAR[baris.dasar]}"
        lines.append(Line(account_id=beban_id, debit=nilai,
                          description=keterangan))
        lines.append(Line(account_id=utang_id, credit=nilai,
                          description=keterangan))

    if not lines:
        raise ValueError(
            f"Lembar {sheet.number} tidak punya nilai yang bisa dijurnal."
        )

    # Nomor jurnal diturunkan dari nomor dokumennya, mengikuti konvensi
    # commission_service & payout_service (KOM->JV, PAY->JVI): satu lembar
    # selalu bisa ditelusuri ke jurnalnya lewat nomor, tanpa membuka tabel.
    jurnal = await post_journal(
        db, company_id=company_id, number=sheet.number.replace("LH", "JVL"),
        on_date=on_date, lines=lines,
        memo=f"Lembar hitung {sheet.number}",
        source_type="profit_sheet", source_id=sheet.id, created_by=user_id,
    )
    sheet.journal_id = jurnal.id
    sheet.status = "disetujui"
    await db.flush()
    return sheet


# ------------------------------------------------------------ TRANSFER
async def transfer_line(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    line_id: str, on_date: date, paid_account_code: str = "1-1000",
) -> ProfitSheetLine:
    """Bayar satu baris: Dr Utang / Cr Kas-Bank. Neraca saja.

    Gerbangnya `invoice.status == "paid"` - STATUS faktur, bukan jurnal.
    Bebannya sudah diakui saat lembar disetujui; yang ditahan di sini cuma
    uang keluarnya, sampai uang customer benar-benar masuk.
    """
    baris = (await db.execute(
        select(ProfitSheetLine).where(ProfitSheetLine.id == line_id)
    )).scalar_one_or_none()
    if baris is None:
        raise ValueError("Baris lembar hitung tidak ditemukan.")

    sheet = await _ambil(db, company_id, baris.sheet_id)
    if sheet.status not in SUDAH_BERJURNAL:
        raise ValueError(
            f"Lembar {sheet.number} berstatus '{sheet.status}' - setujui dulu "
            f"sebelum mentransfer."
        )
    if baris.settlement_journal_id:
        raise ValueError(f"Hak {baris.payee_name} sudah ditransfer.")

    inv = (await db.execute(
        select(Invoice).where(Invoice.id == sheet.invoice_id)
    )).scalar_one()
    if inv.status != "paid":
        sisa = _q(Decimal(str(inv.total)) - Decimal(str(inv.paid_total)))
        raise ValueError(
            f"Faktur {inv.number} belum lunas (sisa {sisa}) - transfer komisi "
            f"& bagi hasil baru dibuka setelah uangnya masuk."
        )

    kas_id = await _akun_kode(db, company_id, paid_account_code)
    utang_id = baris.payable_account_id or await ensure_account(
        db, company_id, JENIS_AKUN[baris.jenis][1]
    )
    nilai = _q(baris.amount)
    keterangan = f"Transfer {baris.payee_name} - lembar {sheet.number}"

    # Satu lembar bisa punya beberapa transfer, jadi nomor jurnalnya diberi
    # akhiran urutan baris — tanpa itu dua transfer dari lembar yang sama
    # akan memakai nomor jurnal yang identik.
    jurnal = await post_journal(
        db, company_id=company_id,
        number=f"{sheet.number.replace('LH', 'JVLT')}-{baris.sequence + 1}",
        on_date=on_date,
        lines=[Line(account_id=utang_id, debit=nilai, description=keterangan),
               Line(account_id=kas_id, credit=nilai, description=keterangan)],
        memo=keterangan, source_type="profit_sheet_transfer",
        source_id=baris.id, created_by=user_id,
    )
    baris.settlement_journal_id = jurnal.id
    baris.paid_account_id = kas_id
    baris.paid_date = on_date

    if all(b.settlement_journal_id for b in sheet.lines):
        sheet.status = "ditransfer"
    await db.flush()
    return baris


# ------------------------------------------------------------ BATALKAN
async def void_sheet(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    sheet_id: str, on_date: date, reason: str | None = None,
) -> ProfitSheet:
    """Balik pengakuan hak yang belum cair, untuk faktur yang tak akan lunas.

    WAJIB dipakai kalau fakturnya batal / tak tertagih: tanpa ini Utang Bagi
    Hasil & Utang Komisi menumpuk selamanya dengan angka yang tidak akan
    pernah dibayar, dan laba terlihat lebih kecil dari kenyataan.

    Baris yang uangnya SUDAH ditransfer tidak dibalik - uangnya memang sudah
    keluar, jadi bebannya memang sudah terjadi. Membalik itu justru membuat
    kas dan beban tidak lagi bertemu.
    """
    sheet = await _ambil(db, company_id, sheet_id)
    if sheet.status == "batal":
        raise ValueError(f"Lembar {sheet.number} sudah dibatalkan.")
    if sheet.status == "draft":
        # Belum ada jurnal - cukup ditandai, tidak ada yang perlu dibalik.
        sheet.status = "batal"
        _catat_alasan(sheet, reason)
        await db.flush()
        return sheet

    lines: list[Line] = []
    for baris in sheet.lines:
        if baris.settlement_journal_id:
            continue
        nilai = _q(baris.amount)
        if nilai <= 0:
            continue
        beban_key, utang_key = JENIS_AKUN[baris.jenis]
        beban_id = baris.expense_account_id or await ensure_account(
            db, company_id, beban_key)
        utang_id = baris.payable_account_id or await ensure_account(
            db, company_id, utang_key)
        keterangan = f"Batal {baris.payee_name} - lembar {sheet.number}"
        lines.append(Line(account_id=utang_id, debit=nilai,
                          description=keterangan))
        lines.append(Line(account_id=beban_id, credit=nilai,
                          description=keterangan))

    if lines:
        jurnal = await post_journal(
            db, company_id=company_id,
            number=sheet.number.replace("LH", "JVLR"),
            on_date=on_date, lines=lines,
            memo=f"Pembatalan lembar hitung {sheet.number}",
            source_type="profit_sheet_void", source_id=sheet.id,
            created_by=user_id,
        )
        sheet.void_journal_id = jurnal.id

    sheet.status = "batal"
    _catat_alasan(sheet, reason)
    await db.flush()
    return sheet


# ------------------------------------------------------------ BACA
async def get_sheet(db: AsyncSession, company_id: str,
                    sheet_id: str) -> ProfitSheet:
    return await _ambil(db, company_id, sheet_id)


async def sheet_by_invoice(db: AsyncSession, company_id: str,
                           invoice_id: str) -> ProfitSheet | None:
    return (await db.execute(
        select(ProfitSheet).where(ProfitSheet.company_id == company_id,
                                  ProfitSheet.invoice_id == invoice_id,
                                  ProfitSheet.status != "batal")
    )).scalar_one_or_none()


async def list_sheets(db: AsyncSession, company_id: str, *,
                      status: str | None = None,
                      limit: int = 200) -> list[ProfitSheet]:
    stmt = (select(ProfitSheet).where(ProfitSheet.company_id == company_id)
            .order_by(ProfitSheet.date.desc(), ProfitSheet.number.desc())
            .limit(limit))
    if status:
        stmt = stmt.where(ProfitSheet.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def pratinjau(
    db: AsyncSession, *, company_id: str, invoice_id: str, baris: list[dict],
    modal_perjanjian=None, hpp_dasar_komisi=None, pengurang_per_dus=None,
) -> dict:
    """Hitung tanpa menyimpan - supaya user bisa melihat angkanya dulu.

    Sengaja memakai jalur yang sama persis dengan `create_sheet`; kalau
    pratinjau punya rumusnya sendiri, dua tempat akan berbeda diam-diam.
    """
    inv = await _faktur_sah(db, company_id, invoice_id)
    hpp = await _hpp_riil(db, company_id, inv)
    ctx = Konteks(
        penjualan=_q(inv.subtotal), hpp_riil=hpp,
        hpp_dasar_komisi=_opsional(hpp_dasar_komisi) or hpp,
        modal_perjanjian=_opsional(modal_perjanjian),
        pengurang_per_dus=_opsional(pengurang_per_dus),
        jumlah_dus=await _jumlah_dus(db, invoice_id),
    )
    _periksa_baris(baris, ctx)
    nilai = _evaluasi(baris, ctx)
    total = _q(sum(nilai, Decimal("0")))
    return {
        "invoice_number": inv.number,
        "penjualan": str(ctx.penjualan),
        "hpp_riil": str(ctx.hpp_riil),
        "hpp_dasar_komisi": str(ctx.hpp_dasar_komisi),
        "margin_riil": str(ctx.margin_riil),
        "jumlah_dus": str(ctx.jumlah_dus),
        "profit_bersama": str(ctx.profit_bersama),
        "bagian_asf": str(ctx.bagian_asf),
        "hidden_margin": str(ctx.hidden_margin),
        "total_hak": str(total),
        "melebihi_margin": total > ctx.margin_riil,
        "baris": [
            {"payee_name": b["payee_name"], "jenis": b["jenis"],
             "dasar": b["dasar"], "keterangan_dasar": DASAR[str(b["dasar"])],
             "amount": str(nilai[i])}
            for i, b in enumerate(baris)
        ],
    }


# ------------------------------------------------------------ INTERNAL
async def _ambil(db: AsyncSession, company_id: str, sheet_id: str) -> ProfitSheet:
    sheet = (await db.execute(
        select(ProfitSheet).where(ProfitSheet.id == sheet_id,
                                  ProfitSheet.company_id == company_id)
    )).scalar_one_or_none()
    if sheet is None:
        raise ValueError("Lembar hitung tidak ditemukan.")
    return sheet


async def _akun_kode(db: AsyncSession, company_id: str, code: str) -> str:
    aid = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if not aid:
        raise ValueError(f"Akun {code} tidak ada di CoA.")
    return aid


def _catat_alasan(sheet: ProfitSheet, reason: str | None) -> None:
    if not reason:
        return
    sheet.note = (f"{sheet.note}\n[BATAL] {reason}" if sheet.note
                  else f"[BATAL] {reason}")
