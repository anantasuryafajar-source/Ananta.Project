from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Contact, User
from ..deps import current_user, require_roles
from ..schemas.contact import ContactIn, ContactOut

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    q: str | None = Query(None), type: str | None = None,
    limit: int = Query(50, le=200),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Contact).where(Contact.company_id == user.company_id)
    if type:
        stmt = stmt.where(Contact.type == type)
    if q:
        stmt = stmt.where(Contact.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Contact.name).limit(limit)
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=ContactOut, status_code=201)
async def create_contact(
    body: ContactIn,
    user: User = Depends(require_roles("sales", "finance")),
    db: AsyncSession = Depends(get_db),
):
    contact = Contact(company_id=user.company_id, **body.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact
