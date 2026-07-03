from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jwt import InvalidTokenError
from ..core.database import get_db
from ..core.security import (
    verify_password, create_access_token, create_refresh_token, decode_token,
)
from ..models import User
from ..deps import current_user, user_roles
from ..schemas.auth import TokenOut, RefreshIn, MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(
    form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    # OAuth2PasswordRequestForm pakai 'username' — kita isi dengan email.
    user = (await db.execute(
        select(User).where(User.email == form.username)
    )).scalar_one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah.",
        )
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        sub = payload["sub"]
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Token refresh tidak valid.")
    return TokenOut(
        access_token=create_access_token(sub),
        refresh_token=create_refresh_token(sub),
    )


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return MeOut(
        id=user.id, email=user.email, full_name=user.full_name,
        roles=sorted(await user_roles(db, user.id)),
    )


# ============================= LUPA & RESET KATA SANDI =============================
import secrets
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
from ..core.security import hash_password
from ..core.config import settings
from ..services.email_service import send_email, reset_email_html


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(body: ForgotIn, db: AsyncSession = Depends(get_db)):
    """Kirim tautan reset ke email bila terdaftar. Selalu balas sukses
    (tidak membocorkan apakah email ada) demi keamanan."""
    user = (await db.execute(
        select(User).where(User.email == body.email.lower())
    )).scalar_one_or_none()

    generic = {"ok": True, "message":
               "Jika email terdaftar, tautan reset telah dikirim."}

    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()
        reset_url = f"{settings.APP_URL.rstrip('/')}/reset-password?token={token}"
        await send_email(
            to=user.email,
            subject="Atur Ulang Kata Sandi — Ananta",
            html=reset_email_html(user.full_name, reset_url),
        )
    return generic


@router.post("/reset-password")
async def reset_password(body: ResetIn, db: AsyncSession = Depends(get_db)):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422,
                            detail="Kata sandi baru minimal 8 karakter.")
    user = (await db.execute(
        select(User).where(User.reset_token == body.token)
    )).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Tautan tidak valid.")
    exp = user.reset_expires
    if exp is None or (exp.tzinfo and exp < datetime.now(timezone.utc)) or \
       (exp.tzinfo is None and exp < datetime.utcnow()):
        raise HTTPException(status_code=400,
                            detail="Tautan sudah kedaluwarsa. Minta tautan baru.")
    user.password_hash = hash_password(body.new_password)
    user.reset_token = None
    user.reset_expires = None
    await db.commit()
    return {"ok": True, "message": "Kata sandi berhasil diperbarui. Silakan masuk."}
