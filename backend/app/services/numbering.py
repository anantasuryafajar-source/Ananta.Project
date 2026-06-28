"""Penomoran dokumen otomatis, aman terhadap balapan (row lock)."""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import DocumentSequence


def _period_key(reset: str, on_date: date) -> str:
    if reset == "monthly":
        return on_date.strftime("%Y%m")
    if reset == "yearly":
        return on_date.strftime("%Y")
    return ""


async def next_number(
    db: AsyncSession, *, company_id: str, doc_type: str, on_date: date,
    prefix: str = "", reset: str = "monthly", padding: int = 4,
) -> str:
    pkey = _period_key(reset, on_date)
    stmt = (
        select(DocumentSequence)
        .where(
            DocumentSequence.company_id == company_id,
            DocumentSequence.doc_type == doc_type,
            DocumentSequence.period_key == pkey,
        )
        .with_for_update()
    )
    seq = (await db.execute(stmt)).scalar_one_or_none()
    if seq is None:
        seq = DocumentSequence(
            company_id=company_id, doc_type=doc_type, period_key=pkey,
            prefix=prefix, padding=padding, next_number=1,
        )
        db.add(seq)
        await db.flush()

    n = seq.next_number
    seq.next_number = n + 1
    await db.flush()

    pad = str(n).zfill(seq.padding)
    parts = [p for p in (seq.prefix or prefix, pkey, pad) if p]
    return "/".join(parts) if len(parts) > 1 else pad
