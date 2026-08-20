from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class BillLineIn(BaseModel):
    """Satu baris tagihan. `quantity` & `unit_cost` mengikuti `unit` yang dipilih
    (unit="dus" -> jumlah dus & modal per dus). Supplier ASF biasanya per dus."""
    product_id: str | None = None
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(default="dus", pattern="^(dus|botol)$")
    unit_cost: Decimal = Field(ge=0)
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    # Keterangan khusus baris ini (mis. "2 botol pecah"). Berbeda dari
    # `notes` dokumen yang berlaku untuk seluruh nota.
    note: str | None = Field(default=None, max_length=255)


class BillIn(BaseModel):
    contact_id: str
    date: date
    warehouse_id: str | None = None
    notes: str | None = None
    lines: list[BillLineIn] = Field(min_length=1)


class BillLineOut(ORMModel):
    id: str
    description: str
    quantity: Decimal        # dalam botol (satuan dasar)
    qty_input: Decimal       # seperti diketik user
    unit: str                # "dus" | "botol"
    unit_factor: int         # botol per satuan, snapshot saat transaksi
    unit_cost: Decimal       # per `unit`
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal
    note: str | None = None


class BillOut(ORMModel):
    id: str
    number: str
    contact_id: str
    date: date
    due_date: date | None
    status: str
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    paid_total: Decimal
    journal_id: str | None
    lines: list[BillLineOut]


class PaymentIn(BaseModel):
    """Untuk penerimaan (invoice_id) atau pembayaran (bill_id)."""
    invoice_id: str | None = None
    bill_id: str | None = None
    date: date
    amount: Decimal = Field(gt=0)
    cash_account_id: str | None = None


class PaymentOut(ORMModel):
    id: str
    number: str
    date: date
    amount: Decimal
    journal_id: str | None
