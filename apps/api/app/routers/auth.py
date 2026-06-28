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
