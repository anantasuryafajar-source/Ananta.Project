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


# ============================= EDIT & HAPUS =============================
from fastapi import HTTPException
from ..models import Invoice, Bill


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str, body: ContactIn,
    user: User = Depends(require_roles("sales", "finance")),
    db: AsyncSession = Depends(get_db),
):
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id,
                              Contact.company_id == user.company_id)
    )).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Kontak tidak ditemukan.")
    for k, v in body.model_dump().items():
        setattr(contact, k, v)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: str,
    user: User = Depends(require_roles()),  # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    contact = (await db.execute(
        select(Contact).where(Contact.id == contact_id,
                              Contact.company_id == user.company_id)
    )).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Kontak tidak ditemukan.")

    used_inv = (await db.execute(
        select(Invoice.id).where(Invoice.contact_id == contact_id).limit(1)
    )).scalar_one_or_none()
    used_bill = (await db.execute(
        select(Bill.id).where(Bill.contact_id == contact_id).limit(1)
    )).scalar_one_or_none()
    if used_inv or used_bill:
        raise HTTPException(
            status_code=422,
            detail="Kontak punya riwayat faktur/tagihan — tidak bisa dihapus "
                   "(jejak transaksi harus utuh).")
    await db.delete(contact)
    await db.commit()
    return {"ok": True}
