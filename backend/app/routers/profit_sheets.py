"""Lembar Hitung - kalkulator kesepakatan yang menempel pada satu faktur.

Perhatikan pembagian peran yang disengaja: seluruh perhitungan & jurnal ada di
`services/profit_sheet_service.py`, router ini hanya menerjemahkan HTTP dan
mengurus commit/rollback. Menaruh rumus di sini berarti bot Telegram dan
skrip apa pun yang memakai service langsung akan menghitung berbeda.
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..deps import current_user, require_roles
from ..models import User
from ..schemas.common import ORMModel
from ..services import profit_sheet_service as svc
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/profit-sheets", tags=["profit-sheets"])


class BarisIn(BaseModel):
    payee_name: str = Field(min_length=1, max_length=120)
    # komisi | bagi_hasil
    jenis: str
    # Daftar TERTUTUP, lihat profit_sheet_service.DASAR.
    dasar: str
    persen: Decimal | None = None
    # Hanya dipakai kalau dasar == "nominal".
    nominal: Decimal | None = None
    note: str | None = None


class LembarIn(BaseModel):
    invoice_id: str
    date: date
    baris: list[BarisIn] = Field(min_length=1)
    modal_perjanjian: Decimal | None = None
    hpp_dasar_komisi: Decimal | None = None
    pengurang_per_dus: Decimal | None = None
    note: str | None = None


class PratinjauIn(BaseModel):
    invoice_id: str
    baris: list[BarisIn] = Field(min_length=1)
    modal_perjanjian: Decimal | None = None
    hpp_dasar_komisi: Decimal | None = None
    pengurang_per_dus: Decimal | None = None


class TanggalIn(BaseModel):
    date: date


class TransferIn(BaseModel):
    date: date
    paid_account_code: str = "1-1000"


class VoidIn(BaseModel):
    date: date
    reason: str | None = None


class BarisOut(ORMModel):
    id: str
    sequence: int
    payee_name: str
    jenis: str
    dasar: str
    persen: Decimal | None
    nominal: Decimal | None
    amount: Decimal
    paid_date: date | None
    settlement_journal_id: str | None
    note: str | None


class LembarOut(ORMModel):
    id: str
    number: str
    date: date
    invoice_id: str
    status: str
    penjualan: Decimal
    hpp_riil: Decimal
    hpp_dasar_komisi: Decimal
    modal_perjanjian: Decimal | None
    pengurang_per_dus: Decimal | None
    jumlah_dus: Decimal
    profit_bersama: Decimal
    bagian_asf: Decimal
    hidden_margin: Decimal
    note: str | None
    lines: list[BarisOut]


def _baris(items: list[BarisIn]) -> list[dict]:
    return [b.model_dump() for b in items]


@router.get("/dasar")
async def daftar_dasar(user: User = Depends(current_user)):
    """Pilihan dasar perhitungan yang tersedia, untuk mengisi dropdown UI.

    Diambil dari service supaya UI tidak pernah punya daftarnya sendiri -
    daftar yang bercabang dua adalah cara paling gampang memunculkan dasar
    yang tidak bisa dihitung backend.
    """
    return {
        "dasar": [{"kode": k, "keterangan": v} for k, v in svc.DASAR.items()],
        "jenis": [
            {"kode": "komisi", "keterangan": "Komisi pihak ketiga (6-1100)"},
            {"kode": "bagi_hasil", "keterangan": "Hak mitra / bagi hasil (6-1300)"},
        ],
    }


@router.get("", response_model=list[LembarOut])
async def list_sheets(
    status: str | None = Query(None, description="draft | disetujui | ditransfer | batal"),
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    return await svc.list_sheets(db, user.company_id, status=status)


@router.get("/by-invoice/{invoice_id}", response_model=LembarOut | None)
async def by_invoice(
    invoice_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Lembar aktif faktur ini, atau null kalau belum ada."""
    return await svc.sheet_by_invoice(db, user.company_id, invoice_id)


@router.get("/{sheet_id}", response_model=LembarOut)
async def detail(
    sheet_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.get_sheet(db, user.company_id, sheet_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/pratinjau")
async def pratinjau(
    body: PratinjauIn,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    """Angka lembar tanpa menyimpan apa pun. Tidak menyentuh jurnal."""
    try:
        return await svc.pratinjau(
            db, company_id=user.company_id, invoice_id=body.invoice_id,
            baris=_baris(body.baris), modal_perjanjian=body.modal_perjanjian,
            hpp_dasar_komisi=body.hpp_dasar_komisi,
            pengurang_per_dus=body.pengurang_per_dus)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("", response_model=LembarOut, status_code=201)
async def create_sheet(
    body: LembarIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Simpan lembar sebagai draft. Belum ada jurnal sampai disetujui."""
    try:
        s = await svc.create_sheet(
            db, company_id=user.company_id, user_id=user.id,
            invoice_id=body.invoice_id, on_date=body.date,
            baris=_baris(body.baris), modal_perjanjian=body.modal_perjanjian,
            hpp_dasar_komisi=body.hpp_dasar_komisi,
            pengurang_per_dus=body.pengurang_per_dus, note=body.note)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return await svc.get_sheet(db, user.company_id, s.id)


@router.post("/{sheet_id}/approve", response_model=LembarOut)
async def approve(
    sheet_id: str, body: TanggalIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Akui beban & utang. Ini titik pengakuannya, bukan saat transfer."""
    try:
        s = await svc.approve_sheet(db, company_id=user.company_id,
                                    user_id=user.id, sheet_id=sheet_id,
                                    on_date=body.date)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return await svc.get_sheet(db, user.company_id, s.id)


@router.post("/lines/{line_id}/transfer", response_model=BarisOut)
async def transfer(
    line_id: str, body: TransferIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Bayar satu hak. Hanya dibuka untuk faktur yang sudah lunas."""
    try:
        b = await svc.transfer_line(
            db, company_id=user.company_id, user_id=user.id, line_id=line_id,
            on_date=body.date, paid_account_code=body.paid_account_code)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(b)
    return b


@router.post("/{sheet_id}/void", response_model=LembarOut)
async def void(
    sheet_id: str, body: VoidIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Balik pengakuan hak yang belum cair - untuk faktur yang tak akan lunas."""
    try:
        s = await svc.void_sheet(db, company_id=user.company_id,
                                 user_id=user.id, sheet_id=sheet_id,
                                 on_date=body.date, reason=body.reason)
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    return await svc.get_sheet(db, user.company_id, s.id)
