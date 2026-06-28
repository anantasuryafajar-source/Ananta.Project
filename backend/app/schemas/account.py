from pydantic import BaseModel
from .common import ORMModel


class AccountOut(ORMModel):
    id: str
    code: str
    name: str
    type: str
    normal_balance: str
    is_active: bool
