from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Account, User
from ..deps import current_user
from ..schemas.account import AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Account)
        .where(Account.company_id == user.company_id)
        .order_by(Account.code)
    )
    return (await db.execute(stmt)).scalars().all()
