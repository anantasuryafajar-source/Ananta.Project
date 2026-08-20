from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import CustomerAdvance, InvoiceTerm, User
from ..deps import current_user, require_roles
from ..schemas.common import ORMModel
from ..services import advance_service, terms_service
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/receivables", tags=["receivables"])


# ============================= UANG MUKA (DP) =============================
class AdvanceIn(BaseModel):
    contact_id: str
    date: date
    amount: Decimal = Field(gt=0)
    cash_account_code: str = "1-1000"
    note: str | None = None


class AdvanceAllocIn(BaseModel):
    invoice_id: str
    date: date
    amount: Decimal = Field(gt=0)


class AdvanceOut(ORMModel):
    id: str
    number: str
    date: date
    contact_id: str
    amount: Decimal
    allocated_total: Decimal
    status: str
    journal_id: str | None


@router.get("/advances", response_model=list[AdvanceOut])
async def list_advances(
    contact_id: str | None = Query(None),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (select(CustomerAdvance)
            .where(CustomerAdvance.company_id == user.company_id)
            .order_by(CustomerAdvance.date.desc(), CustomerAdvance.number.desc())
            .limit(200))
    if contact_id:
        stmt = stmt.where(CustomerAdvance.contact_id == contact_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/advances/balance")
async def advance_balance(
    contact_id: str = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Sisa uang muka customer yang belum terpakai."""
    saldo = await advance_service.advance_balance(db, user.company_id, contact_id)
    return {"contact_id": contact_id, "balance": str(saldo)}


@router.post("/advances", response_model=AdvanceOut, status_code=201)
async def create_advance(
    body: AdvanceIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Terima DP sebelum barang keluar — masuk sebagai kewajiban, bukan pendapatan."""
    try:
        adv = await advance_service.receive_advance(
            db, company_id=user.company_id, user_id=user.id,
            contact_id=body.contact_id, on_date=body.date, amount=body.amount,
            cash_account_code=body.cash_account_code, note=body.note,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(adv)
    return adv


@router.post("/advances/{advance_id}/allocate", response_model=AdvanceOut)
async def allocate_advance(
    advance_id: str, body: AdvanceAllocIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await advance_service.allocate_to_invoice(
            db, company_id=user.company_id, user_id=user.id,
            advance_id=advance_id, invoice_id=body.invoice_id,
            on_date=body.date, amount=body.amount,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    adv = (await db.execute(
        select(CustomerAdvance).where(CustomerAdvance.id == advance_id)
    )).scalar_one()
    return adv


# ============================= JADWAL TERMIN =============================
class TermIn(BaseModel):
    kind: str = Field(pattern="^(tunai|dp|tempo|po_berikutnya|custom)$")
    due_date: date | None = None
    amount: Decimal = Field(gt=0)
    note: str | None = None


class TermsIn(BaseModel):
    terms: list[TermIn] = Field(min_length=1)


class TermOut(ORMModel):
    id: str
    sequence: int
    kind: str
    due_date: date | None
    amount: Decimal
    settled_amount: Decimal
    note: str | None


@router.get("/invoices/{invoice_id}/terms", response_model=list[TermOut])
async def get_terms(
    invoice_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return (await db.execute(
        select(InvoiceTerm).where(InvoiceTerm.invoice_id == invoice_id)
        .order_by(InvoiceTerm.sequence)
    )).scalars().all()


@router.put("/invoices/{invoice_id}/terms", response_model=list[TermOut])
async def put_terms(
    invoice_id: str, body: TermsIn,
    user: User = Depends(require_roles("finance", "sales")),
    db: AsyncSession = Depends(get_db),
):
    """Pasang jadwal termin. Total termin wajib sama persis dengan total faktur."""
    try:
        rows = await terms_service.set_terms(
            db, invoice_id=invoice_id,
            terms=[t.model_dump() for t in body.terms],
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return rows
