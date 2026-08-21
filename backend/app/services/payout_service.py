"""Penyambung mesin hitung ke buku besar.

PEMBAGIAN TITIK PENGAKUAN — ini bagian yang paling mudah salah, jadi ditulis
eksplisit:

| Jenis                    | Diakui kapan            | Jurnal                       |
|--------------------------|-------------------------|------------------------------|
| Komisi pihak ketiga      | lembar hitung disetujui | 6-1100 / 2-1600  (sudah ada) |
| Hak mitra (Andre)        | lembar hitung disetujui | 6-1300 / 2-1700  (sudah ada) |
| Insentif penjualan       | tiap cicilan masuk      | 6-1400 / 2-1800              |
| Bagi hasil omzet         | tutup buku bulanan      | 6-1500 / 2-1900              |

Kenapa komisi TIDAK diakrual ulang per cicilan: `profit_sheet_service.
approve_sheet` sudah mengakui seluruhnya saat lembar disetujui. Menambah
akrual prorata di atasnya membuat komisi yang sama terjurnal dua kali dan
laba anjlok dua kali lipat. Prorata untuk komisi karena itu hanya menentukan
BERAPA YANG BOLEH DITRANSFER (`porsi_komisi_cair`), bukan membuat jurnal
baru.

Kenapa insentif JUSTRU diakrual per cicilan: dasarnya adalah uang masuk
bersih. Mengakuinya saat faktur terbit berarti mengakui beban atas uang yang
belum tentu masuk.

Transfer fisik komisi tetap dikunci pada faktur berstatus PAID — pengakuan
hak (akrual) dan pencairan (kas) memang dua hal berbeda.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Payout, Invoice, Account
from .journal import Line, post_journal
from .numbering import next_number
from .accounts_map import ensure_account
from .commission_engine import _q, HUNDRED
from .incentive_engine import (
    MonthData, PaymentRecord, evaluate_target, calculate_bonus,
    calculate_dividen, generate_monthly_closing_report,
    BONUS_TERM1_PERSEN, BONUS_TERM2_PERSEN, BOOSTER_TERM1_PERSEN,
    DIVIDEN_NYOKAP_SAM, DIVIDEN_DELVINA, term_of,
)

AKUN = {
    "insentif": ("incentive_expense", "incentive_payable"),
    "omzet": ("revenue_share_expense", "revenue_share_payable"),
}


async def _akun_id(db, company_id: str, jenis: str) -> tuple[str, str]:
    exp, pay = AKUN[jenis]
    return (await ensure_account(db, company_id, exp),
            await ensure_account(db, company_id, pay))


async def _kas_id(db, company_id: str, code: str) -> str:
    aid = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if not aid:
        raise ValueError(f"Akun {code} tidak ada di CoA.")
    return aid


# ==================================================== PELEPASAN KOMISI
def porsi_komisi_cair(total_invoice, total_pengurang, amount_paid,
                      *, sudah_dicairkan=Decimal("0"), lunas: bool = False
                      ) -> Decimal:
    """Berapa komisi yang BOLEH dicairkan atas satu cicilan.

    Murni angka — TIDAK membuat jurnal. Bebannya sudah diakui saat lembar
    hitung disetujui; ini cuma membuka kunci sebagian utangnya.

    Cicilan pelunas menyerap sisa pembulatan, supaya jumlah seluruh
    pelepasan sama persis dengan total pengurang dan tidak ada sisa beberapa
    rupiah yang menggantung selamanya.
    """
    total = _q(total_invoice)
    if total <= 0:
        raise ValueError("Total invoice harus lebih dari 0.")
    pengurang = _q(total_pengurang)
    if lunas:
        return _q(pengurang - _q(sudah_dicairkan))
    return _q(_q(amount_paid) * (pengurang / total))


# ==================================================== AKRUAL INSENTIF
async def accrue_insentif(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    on_date: date, payee_name: str, net_basis: Decimal,
    invoice_id: str | None = None, persen: Decimal | None = None,
    note: str | None = None,
) -> Payout:
    """Akui hak insentif atas satu cicilan: Dr 6-1400 / Cr 2-1800.

    `persen` bawaan 4,3% (Term 1 / tarif dasar). Kenaikan ke 5,3% dan booster
    1% baru diakui saat tutup buku, karena keduanya bersyarat target bulanan
    yang belum diketahui saat cicilan masuk.
    """
    dasar = _q(net_basis)
    if dasar <= 0:
        raise ValueError("Dasar insentif harus lebih dari 0.")
    rate = persen if persen is not None else BONUS_TERM1_PERSEN
    amount = _q(dasar * rate / HUNDRED)

    exp, pay = await _akun_id(db, company_id, "insentif")
    number = await next_number(db, company_id=company_id, doc_type="payout",
                               on_date=on_date, prefix="PAY", reset="monthly")
    p = Payout(
        company_id=company_id, number=number, date=on_date, jenis="insentif",
        payee_name=payee_name.strip(), periode_tahun=on_date.year,
        periode_bulan=on_date.month, term=term_of(on_date), dasar=dasar,
        persen=rate, amount=amount, invoice_id=invoice_id, status="terutang",
        expense_account_id=exp, payable_account_id=pay, note=note,
        created_by=user_id,
    )
    db.add(p)
    await db.flush()

    journal = await post_journal(
        db, company_id=company_id, number=number.replace("PAY", "JVI"),
        on_date=on_date,
        lines=[Line(exp, debit=amount, description=f"Insentif {payee_name}"),
               Line(pay, credit=amount, description=f"Utang insentif {number}")],
        memo=f"Insentif {number} · {payee_name} · {rate}% x {dasar}",
        source_type="payout", source_id=p.id, created_by=user_id,
    )
    p.journal_id = journal.id
    await db.flush()
    return p


# ==================================================== TUTUP BUKU
async def _sudah_ada(db, company_id, jenis, tahun, bulan, payee=None,
                     term=None) -> bool:
    stmt = select(Payout.id).where(
        Payout.company_id == company_id, Payout.jenis == jenis,
        Payout.periode_tahun == tahun, Payout.periode_bulan == bulan,
        Payout.status != "batal")
    if payee:
        stmt = stmt.where(Payout.payee_name == payee)
    if term is not None:
        stmt = stmt.where(Payout.term == term)
    return (await db.execute(stmt)).first() is not None


async def close_month(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    data: MonthData, on_date: date, payee_sales: str = "Sales",
    terapkan: bool = False,
) -> dict:
    """Evaluasi tutup buku, dan (opsional) jurnalkan hak yang lolos gerbang.

    `terapkan=False` (bawaan) hanya melaporkan — tidak ada jurnal. Ini
    disengaja: tutup buku memindahkan ratusan juta, jadi harus dilihat orang
    dulu, bukan terjadi otomatis.

    Aman diulang: hak yang sudah diakrual untuk periode & penerima yang sama
    dilewati, bukan ditumpuk.
    """
    laporan = generate_monthly_closing_report(data)
    target = evaluate_target(data)
    bonus = calculate_bonus(data, target)
    dividen = calculate_dividen(data, target)
    dibuat: list[str] = []

    if not terapkan:
        laporan["dijurnalkan"] = []
        laporan["mode"] = "pratinjau"
        return laporan

    t, b = data.tahun, data.bulan

    # --- Insentif Term 2 + booster Term 1 (hanya kalau target tercapai) ---
    if target.tercapai:
        exp, pay = await _akun_id(db, company_id, "insentif")
        for label, dasar, rate, amount, term in (
            ("Bonus Term 2", bonus.basis_term2, BONUS_TERM2_PERSEN,
             bonus.bonus_term2, 2),
            ("Booster Term 1", bonus.basis_term1, BOOSTER_TERM1_PERSEN,
             bonus.booster_term1, 1),
        ):
            if amount <= 0:
                continue
            nama = f"{payee_sales} ({label})"
            if await _sudah_ada(db, company_id, "insentif", t, b, nama, term):
                continue
            p = await _payout(db, company_id, user_id, on_date, "insentif",
                              nama, t, b, term, dasar, rate, amount, exp, pay)
            dibuat.append(p.number)

    # --- Bagi hasil omzet (gerbang yang sama) ---
    if target.tercapai:
        exp, pay = await _akun_id(db, company_id, "omzet")
        for nama, rate, amount in (
            ("Nyokap Sam", DIVIDEN_NYOKAP_SAM, dividen.nyokap_sam),
            ("Delvina", DIVIDEN_DELVINA, dividen.delvina),
        ):
            if amount <= 0:
                continue
            if await _sudah_ada(db, company_id, "omzet", t, b, nama, 0):
                continue
            p = await _payout(db, company_id, user_id, on_date, "omzet", nama,
                              t, b, 0, data.omzet_penjualan, rate, amount,
                              exp, pay)
            dibuat.append(p.number)

    laporan["dijurnalkan"] = dibuat
    laporan["mode"] = "terapkan"
    return laporan


async def _payout(db, company_id, user_id, on_date, jenis, nama, tahun, bulan,
                  term, dasar, rate, amount, exp, pay) -> Payout:
    number = await next_number(db, company_id=company_id, doc_type="payout",
                               on_date=on_date, prefix="PAY", reset="monthly")
    p = Payout(company_id=company_id, number=number, date=on_date, jenis=jenis,
               payee_name=nama, periode_tahun=tahun, periode_bulan=bulan,
               term=term, dasar=_q(dasar), persen=rate, amount=_q(amount),
               status="terutang", expense_account_id=exp,
               payable_account_id=pay, created_by=user_id)
    db.add(p)
    await db.flush()
    journal = await post_journal(
        db, company_id=company_id, number=number.replace("PAY", "JVI"),
        on_date=on_date,
        lines=[Line(exp, debit=_q(amount), description=f"{jenis} {nama}"),
               Line(pay, credit=_q(amount), description=f"Utang {number}")],
        memo=f"{jenis.title()} {tahun}-{bulan:02d} · {nama} · {rate}%",
        source_type="payout", source_id=p.id, created_by=user_id,
    )
    p.journal_id = journal.id
    await db.flush()
    return p


# ==================================================== BAYAR
async def pay_payout(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    payout_id: str, on_date: date, paid_account_code: str = "1-1000",
) -> Payout:
    """Transfer hak: Dr Utang / Cr Kas. Bebannya sudah diakui saat akrual."""
    p = (await db.execute(
        select(Payout).where(Payout.company_id == company_id,
                             Payout.id == payout_id)
    )).scalar_one_or_none()
    if p is None:
        raise ValueError("Hak tidak ditemukan.")
    if p.status == "dibayar":
        raise ValueError(f"{p.number} sudah dibayar.")
    if p.status == "batal":
        raise ValueError(f"{p.number} sudah dibatalkan.")

    kas = await _kas_id(db, company_id, paid_account_code)
    amount = _q(p.amount)
    journal = await post_journal(
        db, company_id=company_id, number=p.number.replace("PAY", "JVP"),
        on_date=on_date,
        lines=[Line(p.payable_account_id, debit=amount,
                    description=f"Lunasi {p.number}"),
               Line(kas, credit=amount, description=f"Transfer {p.payee_name}")],
        memo=f"Pembayaran {p.number} · {p.payee_name}",
        source_type="payout_payment", source_id=p.id, created_by=user_id,
    )
    p.status = "dibayar"
    p.paid_date = on_date
    p.paid_account_id = kas
    p.settlement_journal_id = journal.id
    await db.flush()
    return p


async def void_payout(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    payout_id: str, on_date: date, reason: str | None = None,
) -> Payout:
    """Batalkan hak yang belum dibayar — jurnal balik, utang kembali nol."""
    p = (await db.execute(
        select(Payout).where(Payout.company_id == company_id,
                             Payout.id == payout_id)
    )).scalar_one_or_none()
    if p is None:
        raise ValueError("Hak tidak ditemukan.")
    if p.status == "batal":
        raise ValueError(f"{p.number} sudah dibatalkan.")
    if p.status == "dibayar":
        raise ValueError(
            f"{p.number} sudah dibayar — tarik kembali dananya dulu."
        )
    amount = _q(p.amount)
    await post_journal(
        db, company_id=company_id, number=p.number.replace("PAY", "JVPR"),
        on_date=on_date,
        lines=[Line(p.payable_account_id, debit=amount,
                    description=f"Batalkan {p.number}"),
               Line(p.expense_account_id, credit=amount,
                    description=f"Batalkan beban {p.payee_name}")],
        memo=f"Pembatalan {p.number}" + (f" · {reason}" if reason else ""),
        source_type="payout_void", source_id=p.id, created_by=user_id,
    )
    p.status = "batal"
    if reason:
        p.note = f"{p.note}\n[BATAL] {reason}" if p.note else f"[BATAL] {reason}"
    await db.flush()
    return p


# ==================================================== AKRUAL OTOMATIS
# Penerima bawaan bonus penjualan. Dijadikan konstanta bernama supaya
# ketahuan kalau suatu saat perlu jadi master data per-orang.
PENERIMA_INSENTIF = "Sales"


async def _pengurang_faktur(db: AsyncSession, invoice_id: str) -> Decimal:
    """Total uang keluar atas faktur ini (komisi pihak ketiga + hak mitra).

    Dibaca dari lembar hitung yang tidak dibatalkan. Faktur tanpa lembar
    berarti tidak ada pengurang — seluruh uang masuk jadi dasar bonus.
    """
    from ..models import ProfitSheet, ProfitSheetLine
    rows = (await db.execute(
        select(ProfitSheetLine.amount)
        .join(ProfitSheet, ProfitSheet.id == ProfitSheetLine.sheet_id)
        .where(ProfitSheet.invoice_id == invoice_id,
               ProfitSheet.status != "batal")
    )).scalars().all()
    return _q(sum((Decimal(str(r or 0)) for r in rows), Decimal("0")))


async def _basis_terakrual(db: AsyncSession, company_id: str,
                           invoice_id: str) -> Decimal:
    """Dasar insentif yang sudah diakui atas faktur ini, untuk pembulatan."""
    rows = (await db.execute(
        select(Payout.dasar).where(Payout.company_id == company_id,
                                   Payout.invoice_id == invoice_id,
                                   Payout.jenis == "insentif",
                                   Payout.status != "batal")
    )).scalars().all()
    return _q(sum((Decimal(str(r or 0)) for r in rows), Decimal("0")))


async def accrue_insentif_untuk_pembayaran(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    invoice, amount_paid: Decimal, on_date: date,
    payee_name: str = PENERIMA_INSENTIF,
) -> Payout | None:
    """Akui insentif atas satu penerimaan kas. Dipanggil `receive_payment`.

        Dasar Bonus Masuk = amount_paid x (Total Invoice - Total Pengurang)
                                          / Total Invoice

    Cicilan PELUNAS menyerap sisa pembulatan, supaya jumlah seluruh dasar
    persis sama dengan (Total Invoice - Total Pengurang). Tanpa itu akan ada
    selisih beberapa rupiah yang tidak pernah bisa direkonsiliasi dengan
    laporan tutup buku.

    Mengembalikan None kalau tidak ada yang perlu diakui (mis. seluruh nilai
    faktur habis jadi pengurang) — pemanggil tidak perlu memperlakukan itu
    sebagai kegagalan.
    """
    total = _q(invoice.total)
    if total <= 0:
        return None
    pengurang = await _pengurang_faktur(db, invoice.id)
    bersih_total = total - pengurang
    if bersih_total <= 0:
        return None

    sudah = await _basis_terakrual(db, company_id, invoice.id)
    lunas = _q(invoice.paid_total) >= total
    dasar = (bersih_total - sudah if lunas
             else _q(_q(amount_paid) * (bersih_total / total)))
    if dasar <= 0:
        return None

    return await accrue_insentif(
        db, company_id=company_id, user_id=user_id, on_date=on_date,
        payee_name=payee_name, net_basis=dasar, invoice_id=invoice.id,
        note=f"Otomatis dari penerimaan {invoice.number}",
    )


# ==================================================== DATA TUTUP BUKU
async def build_month_data(db: AsyncSession, company_id: str,
                           tahun: int, bulan: int) -> MonthData:
    """Susun MonthData dari transaksi nyata, bukan angka yang diketik ulang.

    Sengaja dihitung di server: kalau UI yang menjumlahkan omzet & uang masuk,
    dua tempat bisa berbeda dan tidak ada yang tahu mana yang benar.

    Omzet memakai `Invoice.subtotal` (sebelum pajak) agar sepadan dengan dasar
    komisi & laba kotor; PPN bukan penghasilan ASF.
    """
    from calendar import monthrange
    from ..models import Invoice, PaymentReceived, Journal, JournalEntry
    from .accounts_map import code_to_id

    awal = date(tahun, bulan, 1)
    akhir = date(tahun, bulan, monthrange(tahun, bulan)[1])

    faktur = (await db.execute(
        select(Invoice).where(Invoice.company_id == company_id,
                              Invoice.status.in_(["posted", "paid", "overdue"]),
                              Invoice.date >= awal, Invoice.date <= akhir)
    )).scalars().all()
    omzet = _q(sum((Decimal(str(f.subtotal or 0)) for f in faktur), Decimal("0")))

    acc = await code_to_id(db, company_id)
    hpp = (await db.execute(
        select(JournalEntry.debit)
        .join(Journal, Journal.id == JournalEntry.journal_id)
        .where(Journal.company_id == company_id,
               Journal.source_type == "invoice",
               Journal.date >= awal, Journal.date <= akhir,
               JournalEntry.account_id == acc["cogs"])
    )).scalars().all()
    laba_kotor = _q(omzet - sum((Decimal(str(h or 0)) for h in hpp), Decimal("0")))

    bayar = (await db.execute(
        select(PaymentReceived, Invoice)
        .join(Invoice, Invoice.id == PaymentReceived.invoice_id)
        .where(PaymentReceived.company_id == company_id,
               PaymentReceived.date >= awal, PaymentReceived.date <= akhir)
        .order_by(PaymentReceived.date)
    )).all()

    catatan: list[PaymentRecord] = []
    for pay, inv in bayar:
        total = _q(inv.total)
        pengurang = await _pengurang_faktur(db, inv.id)
        rasio_bersih = ((total - pengurang) / total) if total > 0 else Decimal("1")
        rasio_komisi = (pengurang / total) if total > 0 else Decimal("0")
        jml = _q(pay.amount)
        catatan.append(PaymentRecord(
            tanggal=pay.date, net_basis=_q(jml * rasio_bersih),
            commission_released=_q(jml * rasio_komisi),
            invoice_lunas=(inv.status == "paid"), invoice_number=inv.number,
        ))

    return MonthData(tahun=tahun, bulan=bulan, omzet_penjualan=omzet,
                     laba_kotor=laba_kotor, pembayaran=catatan)


async def daftar_disbursement(db: AsyncSession, company_id: str) -> dict:
    """Apa saja yang siap ditransfer sekarang.

    Komisi pihak luar dipisah "siap" vs "tertahan": transfer fisik hanya untuk
    faktur berstatus PAID. Keduanya sengaja tidak dijumlah — angka gabungan
    akan selalu tampak lebih besar dari kas yang boleh keluar.
    """
    from ..models import ProfitSheet, ProfitSheetLine, Invoice

    rows = (await db.execute(
        select(ProfitSheetLine, ProfitSheet, Invoice)
        .join(ProfitSheet, ProfitSheet.id == ProfitSheetLine.sheet_id)
        .join(Invoice, Invoice.id == ProfitSheet.invoice_id)
        .where(ProfitSheet.company_id == company_id,
               ProfitSheet.status.in_(["disetujui", "ditransfer"]),
               ProfitSheetLine.settlement_journal_id.is_(None))
        .order_by(ProfitSheet.date)
    )).all()

    siap, tertahan = [], []
    for baris, sheet, inv in rows:
        item = {
            "line_id": baris.id, "sheet_number": sheet.number,
            "invoice_number": inv.number, "invoice_status": inv.status,
            "payee_name": baris.payee_name, "jenis": baris.jenis,
            "amount": str(_q(baris.amount)),
            "sisa_piutang": str(_q(Decimal(str(inv.total))
                                   - Decimal(str(inv.paid_total)))),
        }
        (siap if inv.status == "paid" else tertahan).append(item)

    hak = (await db.execute(
        select(Payout).where(Payout.company_id == company_id,
                             Payout.status == "terutang")
        .order_by(Payout.date)
    )).scalars().all()

    return {
        "komisi_siap_transfer": siap,
        "komisi_tertahan": tertahan,
        "total_siap": str(_q(sum((Decimal(x["amount"]) for x in siap),
                                 Decimal("0")))),
        "total_tertahan": str(_q(sum((Decimal(x["amount"]) for x in tertahan),
                                     Decimal("0")))),
        "hak_internal": [{
            "id": h.id, "number": h.number, "date": str(h.date),
            "jenis": h.jenis, "payee_name": h.payee_name,
            "periode": f"{h.periode_tahun}-{h.periode_bulan:02d}",
            "amount": str(_q(h.amount)),
        } for h in hak],
        "total_hak_internal": str(_q(sum((Decimal(str(h.amount)) for h in hak),
                                         Decimal("0")))),
    }
