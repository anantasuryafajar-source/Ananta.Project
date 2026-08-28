"""Endpoint Lembar Hitung.

DIREKONSTRUKSI — berkas asli tidak pernah ikut ter-commit, padahal `main.py`
sudah mendaftarkannya dan halaman Disbursement sudah memanggil
`POST /profit-sheets/lines/{line_id}/transfer`.

Empat perintah, masing-masing satu titik dalam siklus hidup lembar:

    GET  /profit-sheets/dasar                pilihan dasar hitung + artinya
    POST /profit-sheets/pratinjau            hitung, TIDAK menyimpan apa pun
    POST /profit-sheets                      buat (draft, belum ada jurnal)
    POST /profit-sheets/{id}/approve         akui beban + utang
    POST /profit-sheets/lines/{id}/transfer  bayarkan satu hak (butuh faktur lunas)
    POST /profit-sheets/{id}/void            batalkan + balik jurnalnya

Seluruh kesalahan aturan bisnis dari service berupa `ValueError` dan
diterjemahkan jadi 422 dengan pesan aslinya — pesan itu ditulis untuk dibaca
orang keuangan, bukan programmer, jadi jangan diganti jadi teks generik.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..deps import current_user, require_roles
from ..models import ProfitSheet, User
from ..schemas.profit_sheet import (
    DaftarDasarOut,
    LineOut,
    PratinjauIn,
    PratinjauOut,
    SheetDetailOut,
    SheetIn,
    SheetOut,
    TanggalIn,
    TransferIn,
    VoidIn,
)
from ..services import profit_sheet_service as ps
from ..services.audit_service import write_audit
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/profit-sheets", tags=["profit-sheets"])


@router.get("", response_model=list[SheetOut])
async def list_sheets(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ProfitSheet)
        .where(ProfitSheet.company_id == user.company_id)
        .order_by(ProfitSheet.date.desc(), ProfitSheet.number.desc())
        .limit(100)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=SheetDetailOut, status_code=201)
async def create_sheet(
    body: SheetIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Buat lembar. Masih draft — belum ada satu pun jurnal yang terposting."""
    try:
        sheet = await ps.create_sheet(
            db, company_id=user.company_id, user_id=user.id,
            invoice_id=body.invoice_id, on_date=body.date,
            baris=[l.model_dump() for l in body.lines],
            modal_perjanjian=body.modal_perjanjian,
            hpp_dasar_komisi=body.hpp_dasar_komisi,
            pengurang_per_dus=body.pengurang_per_dus,
            notes=body.notes,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(sheet)
    return sheet


@router.get("/dasar", response_model=DaftarDasarOut)
async def daftar_dasar(user: User = Depends(current_user)):
    """Pilihan dasar hitung & jenis baris beserta artinya.

    Dikirim dari server, bukan ditulis ulang di frontend: daftarnya TERTUTUP
    dan artinya menentukan uang siapa. Dua salinan pasti bergeser cepat atau
    lambat, dan yang bergeser diam-diam adalah penjelasannya — bukan angkanya.
    """
    return ps.daftar_dasar()


@router.post("/pratinjau", response_model=PratinjauOut)
async def pratinjau(
    body: PratinjauIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Hitung tanpa menyimpan, supaya angkanya bisa dilihat sebelum disetujui.

    Rollback di akhir bukan sekadar kehati-hatian: perhitungan membaca lewat
    sesi yang sama, dan tanpa rollback objek yang sempat termuat bisa ikut
    ter-flush oleh permintaan berikutnya.
    """
    try:
        hasil = await ps.pratinjau(
            db, company_id=user.company_id, invoice_id=body.invoice_id,
            baris=[l.model_dump() for l in body.lines],
            modal_perjanjian=body.modal_perjanjian,
            hpp_dasar_komisi=body.hpp_dasar_komisi,
            pengurang_per_dus=body.pengurang_per_dus,
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.rollback()
    return hasil


@router.post("/lines/{line_id}/transfer", response_model=LineOut)
async def transfer_line(
    line_id: str, body: TransferIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Bayarkan satu hak. Ditolak bila fakturnya belum lunas."""
    try:
        baris = await ps.transfer_line(
            db, company_id=user.company_id, user_id=user.id,
            line_id=line_id, on_date=body.date,
            paid_account_code=body.paid_account_code,
        )
        await write_audit(
            db, company_id=user.company_id, user_id=user.id,
            action="transfer_profit_sheet_line", entity="profit_sheet_line",
            entity_id=line_id,
        )
        await db.commit()
    except (ValueError, JournalNotBalanced) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(baris)
    return baris


@router.get("/{sheet_id}", response_model=SheetDetailOut)
async def get_sheet(
    sheet_id: str,
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    sheet = (await db.execute(
        select(ProfitSheet).where(ProfitSheet.id == sheet_id,
                                  ProfitSheet.company_id == user.company_id)
    )).scalar_one_or_none()
    if sheet is None:
        raise HTTPException(status_code=404, detail="Lembar hitung tidak ditemukan.")
    return sheet


@router.post("/{sheet_id}/approve", response_model=SheetDetailOut)
async def approve_sheet(
    sheet_id: str, body: TanggalIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    """Akui beban komisi & hak mitra. Titik pengakuan, bukan pembayaran."""
    try:
        sheet = await ps.approve_sheet(
            db, company_id=user.company_id, user_id=user.id,
            sheet_id=sheet_id, on_date=body.date,
        )
        await write_audit(
            db, company_id=user.company_id, user_id=user.id,
            action="approve_profit_sheet", entity="profit_sheet",
            entity_id=sheet_id,
        )
        await db.commit()
    except (ValueError, JournalNotBalanced) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(sheet)
    return sheet


@router.post("/{sheet_id}/void", response_model=SheetDetailOut)
async def void_sheet(
    sheet_id: str, body: VoidIn,
    user: User = Depends(require_roles()),   # absolut: hanya owner
    db: AsyncSession = Depends(get_db),
):
    """Batalkan lembar & balik jurnalnya, untuk faktur yang tak akan lunas."""
    try:
        sheet = await ps.void_sheet(
            db, company_id=user.company_id, user_id=user.id,
            sheet_id=sheet_id, on_date=body.date, reason=body.reason,
        )
        await write_audit(
            db, company_id=user.company_id, user_id=user.id,
            action="void_profit_sheet", entity="profit_sheet",
            entity_id=sheet_id,
        )
        await db.commit()
    except (ValueError, JournalNotBalanced) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(sheet)
    return sheet
