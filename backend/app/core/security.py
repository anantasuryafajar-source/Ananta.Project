from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from .config import settings

_ph = PasswordHasher()


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, raw)
    except VerifyMismatchError:
        return False


def _make_token(sub: str, *, minutes: int | None = None,
                days: int | None = None, kind: str = "access") -> str:
    now = datetime.now(timezone.utc)
    delta = timedelta(minutes=minutes) if minutes else timedelta(days=days or 0)
    payload = {"sub": sub, "type": kind, "iat": now, "exp": now + delta}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(sub: str) -> str:
    return _make_token(sub, minutes=settings.ACCESS_TOKEN_MINUTES, kind="access")


def create_refresh_token(sub: str) -> str:
    return _make_token(sub, days=settings.REFRESH_TOKEN_DAYS, kind="refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
