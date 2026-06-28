from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class ContactIn(BaseModel):
    type: str = Field(pattern="^(customer|supplier|both)$")
    name: str = Field(min_length=1, max_length=160)
    npwp: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    payment_term_days: int = 0
    credit_limit: Decimal = Decimal("0")


class ContactOut(ORMModel):
    id: str
    type: str
    name: str
    npwp: str | None
    email: str | None
    phone: str | None
    payment_term_days: int
    credit_limit: Decimal
    is_active: bool
