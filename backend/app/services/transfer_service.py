"""Transfer stok antar-gudang. Pergerakan internal (tidak mengubah nilai
persediaan total), jadi TIDAK membuat jurnal — hanya memindah kuantitas &
membawa harga rata-rata ke gudang tujuan. Atomik: caller yang commit/rollback.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Product, StockLevel, StockMovement, Warehouse

CENT = Decimal("0.01")
QTYQ = Decimal("0.0001")


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


class TransferError(ValueError):
    pass


async def _level(db, product_id, warehouse_id) -> StockLevel | None:
    return (await db.execute(
        select(StockLevel).where(
            StockLevel.product_id == product_id,
            StockLevel.warehouse_id == warehouse_id,
        )
    )).scalar_one_or_none()


async def transfer_stock(
    db: AsyncSession, *, company_id: str, from_wh: str, to_wh: str,
    on_date: date, lines: list[dict],
) -> int:
    if from_wh == to_wh:
        raise TransferError("Gudang asal dan tujuan tidak boleh sama.")
    for wh in (from_wh, to_wh):
        ok = (await db.execute(
            select(Warehouse.id).where(Warehouse.id == wh,
                                       Warehouse.company_id == company_id)
        )).scalar_one_or_none()
        if not ok:
            raise TransferError("Gudang tidak ditemukan.")

    moved = 0
    for raw in lines:
        pid = raw["product_id"]
        qty = Decimal(str(raw["quantity"]))
        if qty <= 0:
            continue

        src = await _level(db, pid, from_wh)
        if src is None or Decimal(str(src.quantity)) < qty:
            prod = (await db.execute(
                select(Product.name).where(Product.id == pid)
            )).scalar_one_or_none()
            raise TransferError(
                f"Stok tidak cukup di gudang asal untuk {prod or pid}."
            )

        unit_cost = Decimal(str(src.avg_cost))

        # kurangi sumber
        src.quantity = (Decimal(str(src.quantity)) - qty).quantize(QTYQ)

        # tambah tujuan (average tertimbang)
        dst = await _level(db, pid, to_wh)
        if dst is None:
            dst = StockLevel(product_id=pid, warehouse_id=to_wh,
                             quantity=Decimal("0"), avg_cost=unit_cost)
            db.add(dst)
            await db.flush()
        old_q = Decimal(str(dst.quantity))
        old_avg = Decimal(str(dst.avg_cost))
        new_q = old_q + qty
        new_avg = (old_q * old_avg + qty * unit_cost) / new_q if new_q > 0 else unit_cost
        dst.quantity = new_q.quantize(QTYQ)
        dst.avg_cost = _q(new_avg)

        # dua mutasi: keluar dari asal, masuk ke tujuan
        db.add(StockMovement(
            company_id=company_id, product_id=pid, warehouse_id=from_wh,
            direction="transfer", quantity=-qty, unit_cost=unit_cost,
            ref_type="transfer", ref_id=to_wh,
        ))
        db.add(StockMovement(
            company_id=company_id, product_id=pid, warehouse_id=to_wh,
            direction="transfer", quantity=qty, unit_cost=unit_cost,
            ref_type="transfer", ref_id=from_wh,
        ))
        moved += 1

    await db.flush()
    return moved
