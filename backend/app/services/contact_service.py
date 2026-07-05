"""Service pembuatan kontak (customer/supplier). Master-data, tanpa jurnal."""
from ..models import Contact


async def create_contact(
    db,
    *,
    company_id: str,
    type: str,
    name: str,
    phone: str | None = None,
) -> Contact:
    contact = Contact(
        company_id=company_id,
        type=type,
        name=name,
        phone=phone,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact
