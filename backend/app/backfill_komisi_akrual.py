"""Backfill jurnal pengakuan untuk komisi yang dicatat SEBELUM pindah akrual.

Latar: sampai 2026-08-20 komisi hanya berjurnal saat dibayar. Setelah pindah ke
basis akrual, komisi berstatus "terutang" dari periode lama tidak punya jurnal
pengakuan sama sekali — bebannya tidak ada di Laba Rugi dan kewajibannya tidak
ada di Neraca. Skrip ini yang menambalnya.

Sengaja BUKAN migrasi Alembic. Migrasi berjalan otomatis saat deploy, dan skrip
ini menambah BEBAN ke laporan periode yang mungkin sudah dilaporkan ke orang
lain — itu harus dilihat dan disetujui manusia lebih dulu, bukan terjadi
diam-diam.

Pakai:
    python -m app.backfill_komisi_akrual              # HANYA melihat (dry run)
    python -m app.backfill_komisi_akrual --terapkan   # benar-benar menjurnal

Aman diulang: komisi yang sudah punya `journal_id` dilewati.

Catatan periode tutup buku: kalau `Company.period_lock_date` menutup tanggal
komisi lama, `post_journal` akan menolak dan komisi itu dilaporkan sebagai
GAGAL, bukan dipaksa lewat. Buka periodenya dulu atau jurnal manual dengan
tanggal berjalan — jangan longgarkan penguncian periode demi skrip ini.
"""
from __future__ import annotations
import asyncio
import sys
from decimal import Decimal
from sqlalchemy import select
from .core.database import SessionLocal
from .models import SalesCommission, Company
from .services.journal import Line, post_journal
from .services.accounts_map import ensure_account

PAYABLE_KEY = "commission_payable"


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


async def jalankan(terapkan: bool) -> None:
    async with SessionLocal() as db:
        companies = (await db.execute(select(Company))).scalars().all()

        total_semua = Decimal("0")
        for co in companies:
            rows = (await db.execute(
                select(SalesCommission).where(
                    SalesCommission.company_id == co.id,
                    SalesCommission.status != "void",
                    SalesCommission.journal_id.is_(None),
                ).order_by(SalesCommission.date)
            )).scalars().all()

            if not rows:
                continue

            print(f"\n=== {co.name} — {len(rows)} komisi tanpa jurnal pengakuan ===")
            per_bulan: dict[str, Decimal] = {}
            for k in rows:
                bulan = k.date.strftime("%Y-%m")
                per_bulan[bulan] = per_bulan.get(bulan, Decimal("0")) + _q(k.amount)
                print(f"  {k.number}  {k.date}  {k.payee_name:<20} {_q(k.amount):>14}"
                      f"  [{k.status}]")

            print("  --- beban yang akan DITAMBAHKAN per bulan ---")
            for bulan, jml in sorted(per_bulan.items()):
                print(f"  {bulan}: {jml:>14}")
            subtotal = sum(per_bulan.values(), Decimal("0"))
            total_semua += subtotal
            print(f"  TOTAL: {subtotal}")

            if not terapkan:
                continue

            payable_id = await ensure_account(db, co.id, PAYABLE_KEY)
            berhasil, gagal = 0, []
            for k in rows:
                amount = _q(k.amount)
                if amount <= 0:
                    continue
                try:
                    journal = await post_journal(
                        db, company_id=co.id,
                        number=k.number.replace("KOM", "JVA"),
                        on_date=k.date,
                        lines=[
                            Line(k.expense_account_id, debit=amount,
                                 description=f"Komisi {k.payee_name}"),
                            Line(payable_id, credit=amount,
                                 description=f"Utang komisi {k.number}"),
                        ],
                        memo=f"Backfill pengakuan komisi {k.number}",
                        source_type="commission", source_id=k.id,
                    )
                    k.journal_id = journal.id
                    if not k.payable_account_id:
                        k.payable_account_id = payable_id
                    await db.commit()
                    berhasil += 1
                except Exception as e:  # noqa: BLE001 — dilaporkan, tidak ditelan
                    await db.rollback()
                    gagal.append((k.number, str(e)))

            print(f"  Dijurnal: {berhasil}. Gagal: {len(gagal)}.")
            for nomor, alasan in gagal:
                print(f"    ! {nomor}: {alasan}")

        if total_semua == 0:
            print("\nTidak ada komisi yang perlu ditambal. Aman.")
        elif not terapkan:
            print(f"\n>>> DRY RUN. Total beban yang AKAN ditambahkan: {total_semua}")
            print(">>> Periksa daftar & rekap bulanan di atas. Kalau sudah cocok,")
            print(">>> jalankan ulang dengan --terapkan.")


if __name__ == "__main__":
    asyncio.run(jalankan("--terapkan" in sys.argv))
