from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="good", pattern="^(good|service)$")
    unit: str = "pcs"
    sale_price: Decimal = Decimal("0")
    purchase_price: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")


class ProductOut(ORMModel):
    id: str
    sku: str
    name: str
    kind: str
    unit: str
    sale_price: Decimal
    purchase_price: Decimal
    min_stock: Decimal
    is_active: bool
