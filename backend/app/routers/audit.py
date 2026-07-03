"""Tampilan jejak audit: siapa melakukan aksi apa, kapan."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import AuditLog, User
from ..deps import current_user

router = APIRouter(prefix="/audit", tags=["audit"])

ACTION_LABEL = {
    "void_invoice": "Batal faktur", "void_bill": "Batal tagihan",
    "void_expense": "Batal beban", "void_payment": "Batal pembayaran",
    "hard_delete_invoice": "Hapus faktur", "hard_delete_bill": "Hapus tagihan",
    "hard_delete_expense": "Hapus beban",
    "delete_product": "Hapus produk", "delete_contact": "Hapus kontak",
    "period_lock": "Tutup buku", "period_unlock": "Buka buku",
    "reconcile": "Rekonsiliasi bank",
}


@router.get("")
async def list_audit(
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(AuditLog, User.full_name)
        .join(User, User.id == AuditLog.user_id, isouter=True)
        .where(AuditLog.company_id == user.company_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset).limit(limit)
    )).all()
    return [{
        "id": a.id,
        "at": a.created_at.isoformat() if a.created_at else None,
        "user": name or "(sistem)",
        "action": a.action,
        "action_label": ACTION_LABEL.get(a.action, a.action),
        "entity": a.entity,
        "entity_id": a.entity_id,
        "detail": a.detail,
    } for a, name in rows]
