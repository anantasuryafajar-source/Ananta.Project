from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import CourierExpense, Invoice, User
from ..deps import current_user, require_roles
from ..schemas.distribusi import CourierIn, CourierOut
from ..services.courier_service import create_courier_expense
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/courier-expenses", tags=["courier"])


@router.get("", response_model=list[CourierOut])
async def list_courier(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (select(CourierExpense)
            .where(CourierExpense.company_id == user.company_id)
            .order_by(CourierExpense.date.desc(), CourierExpense.number.desc())
            .limit(200))
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=CourierOut, status_code=201)
async def create_courier(
    body: CourierIn,
    user: User = Depends(require_roles("finance", "warehouse")),
    db: AsyncSession = Depends(get_db),
):
    try:
        exp = await create_courier_expense(
            db, company_id=user.company_id, user_id=user.id,
            on_date=body.date, courier_name=body.courier_name, amount=body.amount,
            invoice_id=body.invoice_id, supplier_id=body.supplier_id,
            supplier_share=body.supplier_share,
            paid_account_code=body.paid_account_code, note=body.note,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(exp)
    return exp


@router.get("/report")
async def courier_report(
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Rekap pengeluaran kurir per periode + rincian per faktur (permintaan #1 & #9)."""
    stmt = (
        select(CourierExpense, Invoice.number)
        .join(Invoice, Invoice.id == CourierExpense.invoice_id, isouter=True)
        .where(CourierExpense.company_id == user.company_id,
               CourierExpense.date >= start, CourierExpense.date <= end)
        .order_by(CourierExpense.date)
    )
    rows = (await db.execute(stmt)).all()
    total = sum((e.amount for e, _ in rows), 0)
    total_asf = sum((e.company_share for e, _ in rows), 0)
    total_sup = sum((e.supplier_share for e, _ in rows), 0)
    return {
        "start": str(start), "end": str(end),
        "total": str(total), "company_share": str(total_asf),
        "supplier_share": str(total_sup),
        "items": [{
            "number": e.number, "date": str(e.date), "courier": e.courier_name,
            "invoice_number": inv, "amount": str(e.amount),
            "company_share": str(e.company_share), "supplier_share": str(e.supplier_share),
        } for e, inv in rows],
    }


# ============================= IMPORT CSV =============================
from pydantic import BaseModel
from decimal import Decimal, InvalidOperation


class CourierCsvRow(BaseModel):
    date: str                       # YYYY-MM-DD
    courier_name: str
    amount: str                     # angka (boleh dengan pemisah ribuan)
    invoice_number: str | None = None
    supplier_share: str | None = None
    note: str | None = None


class CourierImportIn(BaseModel):
    rows: list[CourierCsvRow]


def _clean_num(v: str | None) -> Decimal:
    if not v:
        return Decimal("0")
    s = str(v).replace("Rp", "").replace(".", "").replace(",", ".").strip()
    # kalau format sudah 1234.56 (titik desimal), pembersihan di atas bisa salah;
    # coba parse langsung dulu.
    try:
        return Decimal(str(v).replace(",", "").strip())
    except InvalidOperation:
        try:
            return Decimal(s)
        except InvalidOperation:
            raise ValueError(f"Nominal tidak valid: {v}")


@router.post("/import")
async def import_courier_csv(
    body: CourierImportIn,
    user: User = Depends(require_roles("finance", "warehouse")),
    db: AsyncSession = Depends(get_db),
):
    """Import massal pengeluaran kurir (hasil parse CSV di frontend).
    Tiap baris dibuat sebagai courier expense + jurnal. Baris gagal dilaporkan,
    baris lain tetap diproses."""
    created = 0
    failed: list[dict] = []
    for i, row in enumerate(body.rows, start=1):
        try:
            inv_id = None
            if row.invoice_number:
                inv_id = (await db.execute(
                    select(Invoice.id).where(
                        Invoice.company_id == user.company_id,
                        Invoice.number == row.invoice_number.strip())
                )).scalar_one_or_none()
                if inv_id is None:
                    raise ValueError(f"Faktur {row.invoice_number} tidak ditemukan.")
            amount = _clean_num(row.amount)
            share = _clean_num(row.supplier_share)
            await create_courier_expense(
                db, company_id=user.company_id, user_id=user.id,
                on_date=date.fromisoformat(row.date.strip()),
                courier_name=row.courier_name.strip() or "(tanpa nama)",
                amount=amount, invoice_id=inv_id, supplier_id=None,
                supplier_share=share, paid_account_code="1-1000",
                note=row.note,
            )
            await db.commit()
            created += 1
        except Exception as e:
            await db.rollback()
            failed.append({"row": i, "reason": str(e)})
    return {"created": created, "failed": failed}
