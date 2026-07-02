"""Endpoint akun: ganti kata sandi sendiri.

Dipisah dari auth.py (login/refresh/me) agar file auth inti tidak tersentuh.
Prefix sama-sama /auth — FastAPI mengizinkan dua router berbagi prefix.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..core.security import hash_password, verify_password
from ..models import User
from ..deps import current_user

router = APIRouter(prefix="/auth", tags=["account"])


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # ambil ulang dari DB (state segar) lalu verifikasi sandi lama
    me = (await db.execute(select(User).where(User.id == user.id))).scalar_one()
    if not verify_password(body.current_password, me.password_hash):
        raise HTTPException(status_code=422, detail="Kata sandi saat ini salah.")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=422, detail="Kata sandi baru tidak boleh sama dengan yang lama.")
    me.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
