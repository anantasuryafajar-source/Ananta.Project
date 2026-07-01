from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Company, User, Role, UserRole
from ..deps import current_user

router = APIRouter(prefix="/settings", tags=["settings"])


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


@router.get("/users")
async def list_users(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    users = (await db.execute(
        select(User).where(User.company_id == user.company_id).order_by(User.full_name)
    )).scalars().all()
    # peran per user
    role_rows = (await db.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
    )).all()
    roles_by_user: dict[str, list[str]] = {}
    for uid, rname in role_rows:
        roles_by_user.setdefault(uid, []).append(rname)
    return [
        {"id": u.id, "full_name": u.full_name, "email": u.email,
         "is_active": u.is_active, "roles": roles_by_user.get(u.id, [])}
        for u in users
    ]


@router.get("/roles")
async def list_roles(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars().all()
    return [{"id": r.id, "name": r.name, "label": r.label} for r in roles]
