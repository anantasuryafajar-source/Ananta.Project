"""Dependency FastAPI: autentikasi & RBAC. RBAC dicek di BACKEND, bukan hanya UI."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jwt import InvalidTokenError
from .core.database import get_db
from .core.security import decode_token
from .models import User, Role, UserRole

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def current_user(
    token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)
) -> User:
    cred_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesi tidak valid. Silakan masuk lagi.",
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise cred_err
        user_id = payload["sub"]
    except (InvalidTokenError, KeyError):
        raise cred_err

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise cred_err
    return user


async def user_roles(db: AsyncSession, user_id: str) -> set[str]:
    rows = (await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )).scalars().all()
    return set(rows)


def require_roles(*allowed: str):
    """Pembatas akses per peran. 'owner' selalu lolos."""
    async def _checker(
        user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
    ) -> User:
        roles = await user_roles(db, user.id)
        if "owner" in roles or roles.intersection(allowed):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kamu tidak punya akses ke modul ini.",
        )
    return _checker
