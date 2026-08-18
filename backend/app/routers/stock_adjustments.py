"""Endpoint penyesuaian stok (opname & stok awal).

Dua endpoint POST yang berpasangan:

    POST /stock-adjustments/preview   hitung selisih, TIDAK menyimpan apa pun
    POST /stock-adjustments           simpan: dokumen + jurnal + mutasi stok

Pratinjau bukan kemewahan. Hitungan fisik menulis ulang saldo stok sekaligus
memposting jurnal, dan kesalahan ketik satu angka bisa menghapus stok satu
produk tanpa siapa pun sadar. Keduanya memanggil fungsi hitung yang SAMA, jadi
angka yang disetujui user persis angka yang diposting.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..deps import current_user, require_roles
from ..models import StockAdjustment, User
from ..schemas.stock_adjustment import (
    AdjustmentDetailOut,
    AdjustmentIn,
    AdjustmentOut,
    PreviewIn,
    PreviewOut,
)
from ..services.audit_service import write_audit
from ..services.journal import JournalNotBalanced
from ..services.stock_adjustment_service import (
    PenyesuaianError,
    create_and_post_adjustment,
    hitung_penyesuaian,
)
from ..services.units import NoWarehouse, resolve_warehouse

router = APIRouter(prefix="/stock-adjustments", tags=["stock-adjustments"])


@router.get("", response_model=list[AdjustmentOut])
async def list_adjustments(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(StockAdjustment)
        .where(StockAdjustment.company_id == user.company_id)
        .order_by(StockAdjustment.date.desc(), StockAdjustment.number.desc())
        .limit(100)
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/{adjustment_id}", response_model=AdjustmentDetailOut)
async def get_adjustment(
    adjustment_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    adj = (await db.execute(
        select(StockAdjustment).where(
            StockAdjustment.id == adjustment_id,
            StockAdjustment.company_id == user.company_id,
        )
    )).scalar_one_or_none()
    if adj is None:
        raise HTTPException(status_code=404, detail="Penyesuaian tidak ditemukan.")
    return adj


@router.post("/preview", response_model=PreviewOut)
async def preview_adjustment(
    body: PreviewIn,
    user: User = Depends(require_roles("warehouse", "finance")),
    db: AsyncSession = Depends(get_db),
):
    """Hitung selisih terhadap stok tercatat tanpa menyimpan apa pun.

    Rollback di akhir bukan sekadar kehati-hatian: `hitung_penyesuaian` membaca
    lewat sesi yang sama, dan tanpa rollback objek yang sempat termuat bisa
    ikut ter-flush oleh permintaan berikutnya di sesi itu.
    """
    try:
        warehouse_id = await resolve_warehouse(
            db, user.company_id, body.warehouse_id
        )
        hasil = await hitung_penyesuaian(
            db, company_id=user.company_id, warehouse_id=warehouse_id,
            lines_in=[l.model_dump() for l in body.lines],
            hitungan_lengkap=body.hitungan_lengkap,
        )
    except (PenyesuaianError, NoWarehouse) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.rollback()
    return hasil


@router.post("", response_model=AdjustmentOut, status_code=201)
async def create_adjustment(
    body: AdjustmentIn,
    user: User = Depends(require_roles("warehouse", "finance")),
    db: AsyncSession = Depends(get_db),
):
    """Simpan hasil hitung fisik: stok disetel + jurnal terposting - atomik."""
    try:
        adj = await create_and_post_adjustment(
            db, company_id=user.company_id, user_id=user.id,
            on_date=body.date, warehouse_id=body.warehouse_id, mode=body.mode,
            lines_in=[l.model_dump() for l in body.lines],
            hitungan_lengkap=body.hitungan_lengkap, notes=body.notes,
        )
        await write_audit(
            db, company_id=user.company_id, user_id=user.id,
            action="create_stock_adjustment", entity="stock_adjustment",
            entity_id=adj.id,
        )
        await db.commit()
    except (PenyesuaianError, NoWarehouse, JournalNotBalanced) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(adj)
    return adj
