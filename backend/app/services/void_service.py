"""Pembatalan (VOID) transaksi terposting — hak absolut owner.

Prinsip akuntansi: transaksi terposting TIDAK dihapus fisik. Void membuat
JURNAL BALIK (debit<->kredit dari jurnal asli) dan MENGEMBALIKAN STOK persis
dari catatan StockMovement aslinya, lalu menandai status 'void'. Jejak audit
tetap utuh: dokumen asli, jurnal asli, jurnal pembalik, dan mutasi stok
pembalik semuanya tersimpan.

Aturan pengaman:
- Faktur/Bill yang sudah menerima pembayaran tidak bisa di-void
  (batalkan/void pembayarannya dulu — fase berikutnya; untuk kini ditolak).
- Void Bill ditolak bila stok tersisa tidak cukup untuk ditarik kembali
  (barangnya sudah terlanjur terjual).
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    Invoice, Bill, Expense, Journal, JournalEntry, StockLevel, StockMovement,
)
from .journal import Line, post_journal
from .numbering import next_number

CENT = Decimal("0.01")
QTYQ = Decimal("0.0001")


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


class VoidError(ValueError):
    pass


async def _reversal_lines(db, journal_id: str) -> list[Line]:
    entries = (await db.execute(
        select(JournalEntry).where(JournalEntry.journal_id == journal_id)
    )).scalars().all()
    if not entries:
        raise VoidError("Jurnal asal tidak ditemukan — tidak bisa dibalik.")
    return [
        Line(e.account_id,
             debit=_q(e.credit), credit=_q(e.debit),
             description=f"Balik: {e.description or ''}".strip())
        for e in entries
    ]


async def _post_reversal(db, *, company_id, user_id, journal_id,
                         on_date, memo, source_type, source_id) -> Journal:
    number = await next_number(db, company_id=company_id, doc_type="void",
                               on_date=on_date, prefix="VD", reset="monthly")
    lines = await _reversal_lines(db, journal_id)
    return await post_journal(
        db, company_id=company_id, number=number, on_date=on_date,
        lines=lines, memo=memo, source_type=source_type,
        source_id=source_id, created_by=user_id,
    )


async def _movements(db, ref_type: str, ref_id: str) -> list[StockMovement]:
    return (await db.execute(
        select(StockMovement).where(StockMovement.ref_type == ref_type,
                                    StockMovement.ref_id == ref_id)
    )).scalars().all()


async def _level(db, product_id, warehouse_id) -> StockLevel | None:
    return (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product_id,
                                 StockLevel.warehouse_id == warehouse_id)
    )).scalar_one_or_none()


# ============================================================ VOID INVOICE
async def void_invoice(db: AsyncSession, *, company_id: str,
                       user_id: str | None, invoice_id: str) -> Invoice:
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id,
                              Invoice.company_id == company_id)
    )).scalar_one_or_none()
    if inv is None:
        raise VoidError("Faktur tidak ditemukan.")
    if inv.status == "void":
        raise VoidError("Faktur sudah dibatalkan.")
    if _q(inv.paid_total) > 0:
        raise VoidError("Faktur sudah menerima pembayaran — tidak bisa dibatalkan. "
                        "Batalkan pembayarannya dulu.")

    today = date.today()

    # 1) kembalikan stok persis dari movement asli (qty & unit_cost sama)
    for m in await _movements(db, "invoice", inv.id):
        qty = Decimal(str(m.quantity))
        unit_cost = Decimal(str(m.unit_cost or 0))
        level = await _level(db, m.product_id, m.warehouse_id)
        if level is None:
            level = StockLevel(product_id=m.product_id, warehouse_id=m.warehouse_id,
                               quantity=Decimal("0"), avg_cost=unit_cost)
            db.add(level)
            await db.flush()
        old_q = Decimal(str(level.quantity))
        old_avg = Decimal(str(level.avg_cost))
        new_q = old_q + qty
        new_avg = ((old_q * old_avg + qty * unit_cost) / new_q) if new_q > 0 else unit_cost
        level.quantity = new_q.quantize(QTYQ)
        level.avg_cost = _q(new_avg)
        db.add(StockMovement(
            company_id=company_id, product_id=m.product_id,
            warehouse_id=m.warehouse_id, direction="in", quantity=qty,
            unit_cost=unit_cost, ref_type="void_invoice", ref_id=inv.id,
        ))

    # 2) jurnal balik
    if inv.journal_id:
        await _post_reversal(
            db, company_id=company_id, user_id=user_id,
            journal_id=inv.journal_id, on_date=today,
            memo=f"Pembatalan faktur {inv.number}",
            source_type="void_invoice", source_id=inv.id,
        )

    inv.status = "void"
    await db.flush()
    return inv


# ============================================================ VOID BILL
async def void_bill(db: AsyncSession, *, company_id: str,
                    user_id: str | None, bill_id: str) -> Bill:
    bill = (await db.execute(
        select(Bill).where(Bill.id == bill_id, Bill.company_id == company_id)
    )).scalar_one_or_none()
    if bill is None:
        raise VoidError("Tagihan tidak ditemukan.")
    if bill.status == "void":
        raise VoidError("Tagihan sudah dibatalkan.")
    if _q(bill.paid_total) > 0:
        raise VoidError("Tagihan sudah dibayar sebagian/lunas — tidak bisa dibatalkan. "
                        "Batalkan pembayarannya dulu.")

    today = date.today()
    moves = await _movements(db, "bill", bill.id)

    # pra-cek: semua stok masih cukup untuk ditarik kembali
    for m in moves:
        qty = Decimal(str(m.quantity))
        level = await _level(db, m.product_id, m.warehouse_id)
        if level is None or Decimal(str(level.quantity)) < qty:
            raise VoidError("Stok dari tagihan ini sudah terpakai/terjual — "
                            "tidak bisa ditarik kembali.")

    # 1) tarik kembali stok
    for m in moves:
        qty = Decimal(str(m.quantity))
        unit_cost = Decimal(str(m.unit_cost or 0))
        level = await _level(db, m.product_id, m.warehouse_id)
        level.quantity = (Decimal(str(level.quantity)) - qty).quantize(QTYQ)
        db.add(StockMovement(
            company_id=company_id, product_id=m.product_id,
            warehouse_id=m.warehouse_id, direction="out", quantity=qty,
            unit_cost=unit_cost, ref_type="void_bill", ref_id=bill.id,
        ))

    # 2) jurnal balik
    if bill.journal_id:
        await _post_reversal(
            db, company_id=company_id, user_id=user_id,
            journal_id=bill.journal_id, on_date=today,
            memo=f"Pembatalan tagihan {bill.number}",
            source_type="void_bill", source_id=bill.id,
        )

    bill.status = "void"
    await db.flush()
    return bill


# ============================================================ VOID EXPENSE
async def void_expense(db: AsyncSession, *, company_id: str,
                       user_id: str | None, expense_id: str) -> Expense:
    exp = (await db.execute(
        select(Expense).where(Expense.id == expense_id,
                              Expense.company_id == company_id)
    )).scalar_one_or_none()
    if exp is None:
        raise VoidError("Beban tidak ditemukan.")
    if exp.category == "void":
        raise VoidError("Beban sudah dibatalkan.")

    if exp.journal_id:
        await _post_reversal(
            db, company_id=company_id, user_id=user_id,
            journal_id=exp.journal_id, on_date=date.today(),
            memo=f"Pembatalan beban {exp.number}",
            source_type="void_expense", source_id=exp.id,
        )
    # tandai batal lewat kategori (model beban tidak punya kolom status)
    exp.category = "void"
    await db.flush()
    return exp


# ════════════════════════════════════════════════════════════════════
# HAPUS PERMANEN (khusus data uji/percobaan) — hak absolut owner.
# Berbeda dengan VOID: dokumen, jurnal, dan mutasi stoknya DIHAPUS TOTAL
# tanpa jejak, termasuk pembayarannya. Stok dikembalikan ke kondisi
# sebelum transaksi. Gunakan hanya untuk membersihkan transaksi percobaan.
# ════════════════════════════════════════════════════════════════════
from ..models import (
    PaymentReceived, PaymentMade, SalesOrder, PurchaseOrder, CourierExpense,
)


async def _delete_journal(db, journal_id: str | None):
    if not journal_id:
        return
    j = (await db.execute(
        select(Journal).where(Journal.id == journal_id)
    )).scalar_one_or_none()
    if j:
        await db.delete(j)  # entries ikut terhapus (cascade delete-orphan)


async def hard_delete_invoice(db: AsyncSession, *, company_id: str,
                              invoice_id: str) -> str:
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id,
                              Invoice.company_id == company_id)
    )).scalar_one_or_none()
    if inv is None:
        raise VoidError("Faktur tidak ditemukan.")
    number = inv.number

    # 1) hapus pembayaran terkait + jurnalnya
    pays = (await db.execute(
        select(PaymentReceived).where(PaymentReceived.invoice_id == inv.id)
    )).scalars().all()
    for p in pays:
        jid = p.journal_id
        await db.delete(p)
        await db.flush()
        await _delete_journal(db, jid)

    # 2) lepaskan referensi dari SO & ongkir kurir
    for so in (await db.execute(
        select(SalesOrder).where(SalesOrder.invoice_id == inv.id)
    )).scalars().all():
        so.invoice_id = None
        so.status = "confirmed"
    for ce in (await db.execute(
        select(CourierExpense).where(CourierExpense.invoice_id == inv.id)
    )).scalars().all():
        ce.invoice_id = None

    # 3) kembalikan stok dari movement asli, lalu hapus movement-nya
    for m in await _movements(db, "invoice", inv.id):
        qty = Decimal(str(m.quantity))
        unit_cost = Decimal(str(m.unit_cost or 0))
        level = await _level(db, m.product_id, m.warehouse_id)
        if level is None:
            level = StockLevel(product_id=m.product_id, warehouse_id=m.warehouse_id,
                               quantity=Decimal("0"), avg_cost=unit_cost)
            db.add(level)
            await db.flush()
        old_q = Decimal(str(level.quantity))
        old_avg = Decimal(str(level.avg_cost))
        new_q = old_q + qty
        new_avg = ((old_q * old_avg + qty * unit_cost) / new_q) if new_q > 0 else unit_cost
        level.quantity = new_q.quantize(QTYQ)
        level.avg_cost = _q(new_avg)
        await db.delete(m)

    # 4) hapus dokumen + jurnalnya
    jid = inv.journal_id
    await db.delete(inv)  # lines ikut (cascade)
    await db.flush()
    await _delete_journal(db, jid)
    return number


async def hard_delete_bill(db: AsyncSession, *, company_id: str,
                           bill_id: str) -> str:
    bill = (await db.execute(
        select(Bill).where(Bill.id == bill_id, Bill.company_id == company_id)
    )).scalar_one_or_none()
    if bill is None:
        raise VoidError("Tagihan tidak ditemukan.")
    number = bill.number

    moves = await _movements(db, "bill", bill.id)
    # pra-cek stok cukup untuk ditarik
    for m in moves:
        level = await _level(db, m.product_id, m.warehouse_id)
        if level is None or Decimal(str(level.quantity)) < Decimal(str(m.quantity)):
            raise VoidError("Stok dari tagihan ini sudah terpakai — hapus/void dulu "
                            "transaksi penjualannya, atau gunakan reset massal.")

    # 1) pembayaran + jurnalnya
    pays = (await db.execute(
        select(PaymentMade).where(PaymentMade.bill_id == bill.id)
    )).scalars().all()
    for p in pays:
        jid = p.journal_id
        await db.delete(p)
        await db.flush()
        await _delete_journal(db, jid)

    # 2) lepaskan referensi PO
    for po in (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.bill_id == bill.id)
    )).scalars().all():
        po.bill_id = None
        po.status = "confirmed"

    # 3) tarik stok & hapus movement
    for m in moves:
        level = await _level(db, m.product_id, m.warehouse_id)
        level.quantity = (Decimal(str(level.quantity)) - Decimal(str(m.quantity))).quantize(QTYQ)
        await db.delete(m)

    # 4) dokumen + jurnal
    jid = bill.journal_id
    await db.delete(bill)
    await db.flush()
    await _delete_journal(db, jid)
    return number


async def hard_delete_expense(db: AsyncSession, *, company_id: str,
                              expense_id: str) -> str:
    exp = (await db.execute(
        select(Expense).where(Expense.id == expense_id,
                              Expense.company_id == company_id)
    )).scalar_one_or_none()
    if exp is None:
        raise VoidError("Beban tidak ditemukan.")
    number = exp.number
    jid = exp.journal_id
    await db.delete(exp)
    await db.flush()
    await _delete_journal(db, jid)
    return number
