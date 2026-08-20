from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class CommissionIn(BaseModel):
    """Catat kesepakatan komisi atas satu faktur.

    `amount` adalah nilai yang disepakati dan diketik manual — sengaja tidak
    diturunkan dari rate global, karena komisi hanya berlaku di kasus tertentu
    dan besarannya beda-beda.
    """
    date: date
    invoice_id: str
    payee_name: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0)
    # Catatan cara menghitung waktu itu; tidak dipakai menghitung ulang.
    basis: str = Field(default="nominal",
                       pattern="^(nominal|persen_margin|persen_omzet)$")
    rate: Decimal | None = None
    # Skema yang dipakai (opsional). Isinya di-snapshot ke baris komisi.
    scheme_id: str | None = None
    note: str | None = None


class CommissionPayIn(BaseModel):
    date: date
    paid_account_code: str = "1-1000"  # default Kas


class CommissionVoidIn(BaseModel):
    date: date
    reason: str | None = None


class CommissionOut(ORMModel):
    id: str
    number: str
    date: date
    invoice_id: str
    payee_name: str
    basis: str
    rate: Decimal | None
    amount: Decimal
    status: str
    scheme_id: str | None
    scheme_type: str | None
    paid_date: date | None
    journal_id: str | None
    note: str | None
