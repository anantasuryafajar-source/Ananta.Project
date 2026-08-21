from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import SalesCommission, CommissionScheme, Invoice, Contact, User
from ..deps import current_user, require_roles
from ..schemas.commission import (
    CommissionIn, CommissionOut, CommissionPayIn, CommissionVoidIn,
)
from ..services import commission_service
from ..services.journal import JournalNotBalanced
from pydantic import BaseModel, Field
from ..schemas.common import ORMModel

router = APIRouter(prefix="/commissions", tags=["commissions"])


@router.get("", response_model=list[CommissionOut])
async def list_commissions(
    status: str | None = Query(None, description="terutang | dibayar | void"),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (select(SalesCommission)
            .where(SalesCommission.company_id == user.company_id)
            .order_by(SalesCommission.date.desc(), SalesCommission.number.desc())
            .limit(200))
    if status:
        stmt = stmt.where(SalesCommission.status == status)
    return (await db.execute(stmt)).scalars().all()


@router.get("/saran")
async def saran_komisi(
    invoice_id: str = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Omzet & margin faktur sebagai bahan pertimbangan sebelum mengetik nilai.

    Tidak mengikat: nilai akhir tetap diketik user.
    """
    try:
        return await commission_service.hitung_saran(db, user.company_id, invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("", response_model=CommissionOut, status_code=201)
async def create_commission(
    body: CommissionIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        kom = await commission_service.create_commission(
            db, company_id=user.company_id, user_id=user.id,
            on_date=body.date, invoice_id=body.invoice_id,
            payee_name=body.payee_name, amount=body.amount,
            basis=body.basis, rate=body.rate, scheme_id=body.scheme_id,
            note=body.note,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(kom)
    return kom


@router.post("/{commission_id}/pay", response_model=CommissionOut)
async def pay_commission(
    commission_id: str, body: CommissionPayIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Bayar komisi — di sinilah bebannya masuk jurnal & Laba Rugi."""
    try:
        kom = await commission_service.pay_commission(
            db, company_id=user.company_id, user_id=user.id,
            commission_id=commission_id, on_date=body.date,
            paid_account_code=body.paid_account_code,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(kom)
    return kom


@router.post("/{commission_id}/void", response_model=CommissionOut)
async def void_commission(
    commission_id: str, body: CommissionVoidIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        kom = await commission_service.void_commission(
            db, company_id=user.company_id, user_id=user.id,
            commission_id=commission_id, on_date=body.date, reason=body.reason,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(kom)
    return kom


@router.get("/report")
async def commission_report(
    start: date = Query(...), end: date = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Rekap komisi NYATA (yang dicatat), bukan simulasi rate.

    Dipisah jadi dua angka yang sengaja tidak dijumlah:
      - `total_dibayar`  : sudah berjurnal, ADA di Laba Rugi periode ini.
      - `total_terutang` : disepakati tapi belum dibayar, BELUM di Laba Rugi.
    Menjumlahkan keduanya lalu membandingkannya dengan Laba Rugi akan selalu
    tampak selisih — itu bukan bug, itu memang beda basis.

    Catatan periode: baris "dibayar" disaring pakai `paid_date` (tanggal beban
    diakui), sedangkan "terutang" pakai `date` kesepakatan — supaya kolom
    total_dibayar bisa dicocokkan langsung dengan akun 6-1100 di Laba Rugi.
    """
    rows = (await db.execute(
        select(SalesCommission, Invoice.number, Contact.name)
        .join(Invoice, Invoice.id == SalesCommission.invoice_id, isouter=True)
        .join(Contact, Contact.id == Invoice.contact_id, isouter=True)
        .where(SalesCommission.company_id == user.company_id,
               SalesCommission.status != "void")
        .order_by(SalesCommission.date)
    )).all()

    items, dibayar, terutang = [], Decimal("0"), Decimal("0")
    for k, inv_no, cust in rows:
        if k.status == "dibayar":
            if not (k.paid_date and start <= k.paid_date <= end):
                continue
            dibayar += Decimal(str(k.amount or 0))
        else:
            if not (start <= k.date <= end):
                continue
            terutang += Decimal(str(k.amount or 0))
        items.append({
            "number": k.number, "date": str(k.date),
            "invoice_number": inv_no, "customer": cust,
            "payee": k.payee_name, "basis": k.basis,
            "amount": str(k.amount), "status": k.status,
            "paid_date": str(k.paid_date) if k.paid_date else None,
        })

    return {
        "start": str(start), "end": str(end),
        "total_dibayar": str(dibayar),
        "total_terutang": str(terutang),
        "items": items,
    }


# ============================= SKEMA KOMISI =============================
class SchemeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # `manual` = pintu darurat kasus khusus: tidak menghitung apa pun,
    # angkanya diketik manusia.
    type: str = Field(
        pattern="^(nominal|per_botol|persen_margin|persen_omzet"
                "|persen_margin_min_ongkir|manual)$")
    value: Decimal = Decimal("0")
    # Hanya untuk persen_margin_min_ongkir: tarif ongkir kesepakatan per dus.
    ongkir_per_dus: Decimal | None = None
    default_for_contact_id: str | None = None
    default_for_product_id: str | None = None
    note: str | None = None


class SchemeOut(ORMModel):
    id: str
    name: str
    type: str
    value: Decimal
    ongkir_per_dus: Decimal | None
    default_for_contact_id: str | None
    default_for_product_id: str | None
    is_active: bool
    note: str | None


@router.get("/schemes", response_model=list[SchemeOut])
async def list_schemes(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return (await db.execute(
        select(CommissionScheme)
        .where(CommissionScheme.company_id == user.company_id,
               CommissionScheme.is_active.is_(True))
        .order_by(CommissionScheme.name)
    )).scalars().all()


@router.post("/schemes", response_model=SchemeOut, status_code=201)
async def create_scheme(
    body: SchemeIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    sk = CommissionScheme(
        company_id=user.company_id, name=body.name, type=body.type,
        value=body.value, ongkir_per_dus=body.ongkir_per_dus, note=body.note,
        default_for_contact_id=body.default_for_contact_id,
        default_for_product_id=body.default_for_product_id,
    )
    db.add(sk)
    await db.commit()
    await db.refresh(sk)
    return sk


@router.delete("/schemes/{scheme_id}", response_model=SchemeOut)
async def deactivate_scheme(
    scheme_id: str,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Nonaktifkan skema — TIDAK dihapus, karena komisi lama menunjuk ke sini."""
    sk = (await db.execute(
        select(CommissionScheme).where(
            CommissionScheme.company_id == user.company_id,
            CommissionScheme.id == scheme_id)
    )).scalar_one_or_none()
    if sk is None:
        raise HTTPException(status_code=404, detail="Skema tidak ditemukan.")
    sk.is_active = False
    await db.commit()
    await db.refresh(sk)
    return sk


@router.get("/schemes/{scheme_id}/hitung")
async def hitung_skema(
    scheme_id: str, invoice_id: str = Query(...),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Berapa komisi menurut skema ini untuk faktur tsb. Saran, tidak mengikat."""
    sk = (await db.execute(
        select(CommissionScheme).where(
            CommissionScheme.company_id == user.company_id,
            CommissionScheme.id == scheme_id)
    )).scalar_one_or_none()
    if sk is None:
        raise HTTPException(status_code=404, detail="Skema tidak ditemukan.")
    try:
        r = await commission_service.rincian_skema(
            db, user.company_id, sk, invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # `langkah` dikirim supaya orang bisa MEMERIKSA angkanya, bukan cuma
    # menerima hasil akhir yang tidak bisa dicek di kepala.
    return {"scheme_id": sk.id, "type": sk.type, "amount": str(r["amount"]),
            "langkah": r["langkah"], "manual": sk.type == "manual"}
