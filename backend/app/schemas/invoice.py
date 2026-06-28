from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class InvoiceLineIn(BaseModel):
    product_id: str | None = None
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")


class InvoiceIn(BaseModel):
    contact_id: str
    date: date
    warehouse_id: str | None = None
    notes: str | None = None
    lines: list[InvoiceLineIn] = Field(min_length=1)


class InvoiceLineOut(ORMModel):
    id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal


class InvoiceOut(ORMModel):
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
    lines: list[InvoiceLineOut]
