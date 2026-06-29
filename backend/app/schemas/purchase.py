from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class BillLineIn(BaseModel):
    product_id: str | None = None
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")


class BillIn(BaseModel):
    contact_id: str
    date: date
    warehouse_id: str | None = None
    notes: str | None = None
    lines: list[BillLineIn] = Field(min_length=1)


class BillLineOut(ORMModel):
    id: str
    description: str
    quantity: Decimal
    unit_cost: Decimal
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal


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
