from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class ProductIn(BaseModel):
    """Input master produk.

    - `sku` OPSIONAL: dibuat otomatis dari nama bila kosong (user tidak mengetiknya).
    - `pack_purchase_price` adalah **modal per DUS** — begitu cara client berpikir.
      Modal per botol dihitung sistem, tidak dikirim frontend.
    - **Tidak ada harga jual di sini.** Harga jual berbeda per customer dan
      ditentukan saat pembuatan faktur.
    """
    name: str = Field(min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=40)
    kind: str = Field(default="good", pattern="^(good|service)$")
    unit: str = "botol"
    pack_unit: str = "dus"
    pack_size: int = Field(default=12, ge=1, le=10_000)
    pack_purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    min_stock: Decimal = Field(default=Decimal("0"), ge=0)


class ProductOut(ORMModel):
    id: str
    sku: str
    name: str
    kind: str
    unit: str
    pack_unit: str
    pack_size: int
    pack_purchase_price: Decimal   # modal per dus
    purchase_price: Decimal        # modal per botol (turunan)
    sale_price: Decimal            # harga acuan lama; 0 bila tidak dipakai
    min_stock: Decimal
    is_active: bool
