from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Payout, User
from ..deps import current_user, require_roles
from ..schemas.common import ORMModel
from ..services import payout_service as svc
from ..services.incentive_engine import MonthData, PaymentRecord
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/payouts", tags=["payouts"])


class InsentifIn(BaseModel):
    date: date
    payee_name: str = Field(min_length=1, max_length=120)
    net_basis: Decimal = Field(gt=0)
    invoice_id: str | None = None
    persen: Decimal | None = None
    note: str | None = None


class BayarIn(BaseModel):
    date: date
    paid_account_code: str = "1-1000"


class VoidIn(BaseModel):
    date: date
    reason: str | None = None


class BayarMasukIn(BaseModel):
    tanggal: date
    net_basis: Decimal
    commission_released: Decimal = Decimal("0")
    invoice_lunas: bool = False


class TutupBukuIn(BaseModel):
    tahun: int
    bulan: int
    payee_sales: str = "Sales"
    # False = pratinjau (tidak menjurnal apa pun). Sengaja jadi bawaan:
    # tutup buku memindahkan ratusan juta, harus dilihat orang dulu.
    terapkan: bool = False


class PayoutOut(ORMModel):
    id: str
    number: str
    date: date
    jenis: str
    payee_name: str
    periode_tahun: int
    periode_bulan: int
    term: int
    dasar: Decimal
    persen: Decimal | None
    amount: Decimal
    status: str
    paid_date: date | None
    note: str | None


@router.get("", response_model=list[PayoutOut])
async def list_payouts(
    jenis: str | None = Query(None, description="insentif | omzet"),
    status: str | None = Query(None),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (select(Payout).where(Payout.company_id == user.company_id)
            .order_by(Payout.date.desc(), Payout.number.desc()).limit(300))
    if jenis:
        stmt = stmt.where(Payout.jenis == jenis)
    if status:
        stmt = stmt.where(Payout.status == status)
    return (await db.execute(stmt)).scalars().all()


@router.post("/insentif", response_model=PayoutOut, status_code=201)
async def accrue_insentif(
    body: InsentifIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Akui hak insentif atas satu cicilan masuk."""
    try:
        p = await svc.accrue_insentif(
            db, company_id=user.company_id, user_id=user.id, on_date=body.date,
            payee_name=body.payee_name, net_basis=body.net_basis,
            invoice_id=body.invoice_id, persen=body.persen, note=body.note)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(p)
    return p


@router.post("/tutup-buku")
async def tutup_buku(
    body: TutupBukuIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Evaluasi gerbang target, lalu (opsional) jurnalkan hak yang lolos.

    Aman diulang: hak yang sudah diakrual untuk periode & penerima yang sama
    dilewati, bukan ditumpuk.
    """
    try:
        # Angka disusun dari transaksi nyata di server, bukan dikirim UI:
        # kalau UI yang menjumlahkan, dua tempat bisa berbeda dan tidak ada
        # yang tahu mana yang benar.
        data = await svc.build_month_data(db, user.company_id,
                                          body.tahun, body.bulan)
        r = await svc.close_month(
            db, company_id=user.company_id, user_id=user.id, data=data,
            on_date=date(body.tahun + (body.bulan // 12),
                         (body.bulan % 12) + 1, 1),
            payee_sales=body.payee_sales, terapkan=body.terapkan)
        if body.terapkan:
            await db.commit()
        else:
            await db.rollback()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return r


@router.get("/disbursement")
async def disbursement(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Yang siap ditransfer sekarang, dipisah dari yang masih tertahan."""
    return await svc.daftar_disbursement(db, user.company_id)


@router.get("/tutup-buku/pratinjau")
async def pratinjau_tutup_buku(
    tahun: int = Query(...), bulan: int = Query(..., ge=1, le=12),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Laporan tutup buku tanpa menyentuh jurnal sama sekali."""
    data = await svc.build_month_data(db, user.company_id, tahun, bulan)
    from ..services.incentive_engine import generate_monthly_closing_report
    r = generate_monthly_closing_report(data)
    r["mode"] = "pratinjau"
    r["dijurnalkan"] = []
    return r


@router.post("/{payout_id}/pay", response_model=PayoutOut)
async def pay(
    payout_id: str, body: BayarIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        p = await svc.pay_payout(db, company_id=user.company_id,
                                 user_id=user.id, payout_id=payout_id,
                                 on_date=body.date,
                                 paid_account_code=body.paid_account_code)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(p)
    return p


@router.post("/{payout_id}/void", response_model=PayoutOut)
async def void(
    payout_id: str, body: VoidIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        p = await svc.void_payout(db, company_id=user.company_id,
                                  user_id=user.id, payout_id=payout_id,
                                  on_date=body.date, reason=body.reason)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(p)
    return p
