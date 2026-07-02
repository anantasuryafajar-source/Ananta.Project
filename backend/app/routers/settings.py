from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..core.security import hash_password
from ..models import Company, User, Role, UserRole
from ..deps import current_user, require_roles

router = APIRouter(prefix="/settings", tags=["settings"])

VALID_ROLES = {"owner", "finance", "sales", "warehouse", "viewer"}


# ============================= COMPANY =============================
class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    npwp: str | None = None
    address: str | None = None


@router.get("/company")
async def get_company(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    c = (await db.execute(
        select(Company).where(Company.id == user.company_id)
    )).scalar_one()
    return {
        "id": c.id, "name": c.name, "npwp": c.npwp, "address": c.address,
        "currency": c.currency, "costing_method": c.costing_method,
    }


@router.patch("/company")
async def update_company(
    body: CompanyPatch,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(
        select(Company).where(Company.id == user.company_id)
    )).scalar_one()
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    await db.commit()
    return {"ok": True}


# ============================= USERS =============================
class UserIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["viewer"])


class UserPatch(BaseModel):
    is_active: bool | None = None
    roles: list[str] | None = None


async def _roles_by_user(db) -> dict[str, list[str]]:
    rows = (await db.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
    )).all()
    out: dict[str, list[str]] = {}
    for uid, rname in rows:
        out.setdefault(uid, []).append(rname)
    return out


@router.get("/users")
async def list_users(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    users = (await db.execute(
        select(User).where(User.company_id == user.company_id)
        .order_by(User.full_name)
    )).scalars().all()
    roles_map = await _roles_by_user(db)
    return [
        {"id": u.id, "full_name": u.full_name, "email": u.email,
         "is_active": u.is_active, "roles": roles_map.get(u.id, [])}
        for u in users
    ]


@router.get("/roles")
async def list_roles(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars().all()
    return [{"id": r.id, "name": r.name, "label": r.label} for r in roles]


@router.post("/users", status_code=201)
async def create_user(
    body: UserIn,
    user: User = Depends(require_roles()),  # hanya owner (require_roles tanpa arg = owner-only)
    db: AsyncSession = Depends(get_db),
):
    bad = set(body.roles) - VALID_ROLES
    if bad:
        raise HTTPException(status_code=422, detail=f"Peran tidak dikenal: {', '.join(bad)}")
    exists = (await db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=422, detail="Email sudah terdaftar.")

    new_user = User(
        company_id=user.company_id, email=body.email,
        full_name=body.full_name, password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    roles = (await db.execute(
        select(Role).where(Role.name.in_(body.roles))
    )).scalars().all()
    for r in roles:
        db.add(UserRole(user_id=new_user.id, role_id=r.id))
    await db.commit()
    return {"id": new_user.id, "email": new_user.email}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str, body: UserPatch,
    user: User = Depends(require_roles()),  # owner-only
    db: AsyncSession = Depends(get_db),
):
    target = (await db.execute(
        select(User).where(User.id == user_id,
                           User.company_id == user.company_id)
    )).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    if target.id == user.id and body.is_active is False:
        raise HTTPException(status_code=422, detail="Tidak bisa menonaktifkan akun sendiri.")

    if body.is_active is not None:
        target.is_active = body.is_active

    if body.roles is not None:
        bad = set(body.roles) - VALID_ROLES
        if bad:
            raise HTTPException(status_code=422, detail=f"Peran tidak dikenal: {', '.join(bad)}")
        old = (await db.execute(
            select(UserRole).where(UserRole.user_id == target.id)
        )).scalars().all()
        for ur in old:
            await db.delete(ur)
        roles = (await db.execute(
            select(Role).where(Role.name.in_(body.roles))
        )).scalars().all()
        for r in roles:
            db.add(UserRole(user_id=target.id, role_id=r.id))

    await db.commit()
    return {"ok": True}
