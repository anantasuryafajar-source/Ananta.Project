from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


# ============================= WAREHOUSE =============================
class WarehouseIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    is_default: bool = False


class WarehouseOut(ORMModel):
    id: str
    code: str
    name: str
    is_default: bool


class StockRow(ORMModel):
    product_id: str
    sku: str
    name: str
    warehouse_id: str
    quantity: Decimal
    avg_cost: Decimal


# ============================= TRANSFER =============================
class TransferLineIn(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)


class TransferIn(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    date: date
    notes: str | None = None
    lines: list[TransferLineIn] = Field(min_length=1)


class TransferOut(BaseModel):
    moved: int
    from_warehouse_id: str
    to_warehouse_id: str


# ============================= COURIER =============================
class CourierIn(BaseModel):
    date: date
    courier_name: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0)
    invoice_id: str | None = None
    supplier_id: str | None = None
    # porsi supplier (0..amount). Sisanya jadi beban ASF.
    supplier_share: Decimal = Decimal("0")
    paid_account_code: str = "1-1000"  # default Kas
    note: str | None = None


class CourierOut(ORMModel):
    id: str
    number: str
    date: date
    courier_name: str
    invoice_id: str | None
    amount: Decimal
    supplier_share: Decimal
    company_share: Decimal
    journal_id: str | None


# ============================= ORDERS (PO/SO) =============================
class OrderLineIn(BaseModel):
    product_id: str | None = None
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)  # unit_cost utk PO, unit_price utk SO
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")


class PurchaseOrderIn(BaseModel):
    contact_id: str
    date: date
    expected_date: date | None = None
    warehouse_id: str | None = None
    freight_total: Decimal = Decimal("0")
    freight_supplier_share: Decimal = Decimal("0")
    notes: str | None = None
    lines: list[OrderLineIn] = Field(min_length=1)


class SalesOrderIn(BaseModel):
    contact_id: str
    date: date
    warehouse_id: str | None = None
    courier_name: str | None = None
    notes: str | None = None
    lines: list[OrderLineIn] = Field(min_length=1)


class OrderLineOut(ORMModel):
    id: str
    description: str
    quantity: Decimal
    line_total: Decimal


class PurchaseOrderOut(ORMModel):
    id: str
    number: str
    contact_id: str
    date: date
    status: str
    total: Decimal
    freight_total: Decimal
    bill_id: str | None
    lines: list[OrderLineOut]


class SalesOrderOut(ORMModel):
    id: str
    number: str
    contact_id: str
    date: date
    status: str
    delivery_status: str
    total: Decimal
    invoice_id: str | None
    lines: list[OrderLineOut]
