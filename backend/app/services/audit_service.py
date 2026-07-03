"""Pencatatan jejak audit ringan.

write_audit() dipanggil di titik-titik aksi sensitif (void, hapus permanen,
tutup buku, reset). Sengaja tidak mengubah setiap endpoint agar minim risiko;
fokus pada aksi owner yang wajib terlacak. Kegagalan menulis audit TIDAK boleh
menggagalkan transaksi utama — jadi selalu dibungkus best-effort oleh pemanggil
(commit audit terpisah / toleran error).
"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import AuditLog


async def write_audit(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    action: str, entity: str, entity_id: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(AuditLog(
        company_id=company_id, user_id=user_id, action=action,
        entity=entity, entity_id=entity_id, detail=detail,
    ))
    await db.flush()
