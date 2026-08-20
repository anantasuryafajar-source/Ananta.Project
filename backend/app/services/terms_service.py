"""Jadwal termin pembayaran faktur.

Menggantikan `Invoice.due_date` tunggal. Satu faktur bisa punya beberapa termin
("DP 30% lalu sisanya tempo 30 hari" = dua baris).

Tidak ada satu pun fungsi di sini yang membuat jurnal — jadwal termin murni
informasi penagihan. Uang baru bergerak lewat `payment_service` (kas masuk)
atau `advance_service` (pakai DP). Itu yang menjaga agar menambah mode
pembayaran tidak pernah bisa merusak Laba Rugi.
"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Invoice, InvoiceTerm

CENT = Decimal("0.01")

KINDS = ("tunai", "dp", "tempo", "po_berikutnya", "custom")


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


async def set_terms(
    db: AsyncSession, *, invoice_id: str, terms: list[dict],
) -> list[InvoiceTerm]:
    """Pasang/ganti jadwal termin sebuah faktur.

    `terms` = [{"kind": ..., "due_date": date|None, "amount": Decimal,
                "note": str|None}, ...]

    INVARIAN: total termin harus PERSIS sama dengan total faktur. Ditegakkan
    di sini, bukan di UI — sekeras debit==kredit di post_journal. Kalau jadwal
    boleh berbeda dari faktur, AR Aging akan melaporkan angka yang tidak pernah
    cocok dengan Neraca dan tidak ada error yang memberitahu.
    """
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )).scalar_one_or_none()
    if inv is None:
        raise ValueError("Faktur tidak ditemukan.")
    if not terms:
        raise ValueError("Jadwal termin tidak boleh kosong.")

    total = Decimal("0")
    for t in terms:
        kind = t.get("kind", "tempo")
        if kind not in KINDS:
            raise ValueError(f"Jenis termin '{kind}' tidak dikenal.")
        amt = _q(t.get("amount"))
        if amt <= 0:
            raise ValueError("Nominal tiap termin harus lebih dari 0.")
        total += amt

    if total != _q(inv.total):
        raise ValueError(
            f"Total termin {total} tidak sama dengan total faktur "
            f"{_q(inv.total)}. Selisih {total - _q(inv.total)}."
        )

    lama = (await db.execute(
        select(InvoiceTerm).where(InvoiceTerm.invoice_id == invoice_id)
    )).scalars().all()
    if any(_q(t.settled_amount) > 0 for t in lama):
        raise ValueError(
            "Jadwal tidak bisa diubah: sudah ada termin yang terbayar."
        )
    for t in lama:
        await db.delete(t)
    await db.flush()

    dibuat = []
    for i, t in enumerate(terms, start=1):
        row = InvoiceTerm(
            invoice_id=invoice_id, sequence=i,
            kind=t.get("kind", "tempo"), due_date=t.get("due_date"),
            amount=_q(t.get("amount")), settled_amount=Decimal("0"),
            note=t.get("note"),
        )
        db.add(row)
        dibuat.append(row)
    await db.flush()

    # `Invoice.due_date` dipertahankan = tanggal jatuh tempo TERAKHIR yang
    # punya tanggal, supaya kode & laporan lama yang masih membacanya tidak
    # tiba-tiba kehilangan nilai.
    bertanggal = [t.due_date for t in dibuat if t.due_date]
    inv.due_date = max(bertanggal) if bertanggal else None
    await db.flush()
    return dibuat


def default_terms(inv_total: Decimal, on_date: date,
                  term_days: int = 0) -> list[dict]:
    """Jadwal bawaan untuk faktur tanpa kesepakatan khusus: satu termin."""
    return [{
        "kind": "tunai" if not term_days else "tempo",
        "due_date": on_date + timedelta(days=term_days or 0),
        "amount": _q(inv_total),
    }]


async def settle_terms(
    db: AsyncSession, *, invoice_id: str, amount: Decimal,
    prefer_kind: str | None = None,
) -> None:
    """Tandai termin tertutup sebanyak `amount`.

    Urutan: termin dengan `prefer_kind` lebih dulu (alokasi DP menutup termin
    DP), sisanya berurutan menurut `sequence`. Kalau faktur belum punya jadwal,
    fungsi ini tidak melakukan apa-apa — faktur lama tetap jalan seperti biasa.
    """
    sisa = _q(amount)
    if sisa <= 0:
        return

    rows = (await db.execute(
        select(InvoiceTerm).where(InvoiceTerm.invoice_id == invoice_id)
        .order_by(InvoiceTerm.sequence)
    )).scalars().all()
    if not rows:
        return

    urut = rows
    if prefer_kind:
        urut = ([r for r in rows if r.kind == prefer_kind]
                + [r for r in rows if r.kind != prefer_kind])

    for r in urut:
        if sisa <= 0:
            break
        ruang = _q(r.amount) - _q(r.settled_amount)
        if ruang <= 0:
            continue
        pakai = min(ruang, sisa)
        r.settled_amount = _q(_q(r.settled_amount) + pakai)
        sisa -= pakai
    await db.flush()
