from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field
from .common import ORMModel


class InvoiceLineIn(BaseModel):
    """Satu baris faktur.

    `quantity` & `unit_price` mengikuti `unit` yang dipilih: kalau unit="dus",
    berarti jumlah dus dan harga per dus. Pesanan campur ("1 dus + 5 botol")
    dikirim sebagai DUA baris produk yang sama dengan unit berbeda.
    """
    product_id: str | None = None
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(default="botol", pattern="^(dus|botol)$")
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    # Keterangan khusus baris ini (mis. "2 botol pecah"). Berbeda dari
    # `notes` dokumen yang berlaku untuk seluruh nota.
    note: str | None = Field(default=None, max_length=255)


class InvoiceTermIn(BaseModel):
    """Satu baris jadwal pembayaran.

    `custom` adalah pintu darurat untuk kesepakatan yang tidak terduga: ia
    menyimpan tanggal & nominal apa adanya, tanpa aturan yang dieksekusi.
    `po_berikutnya` sengaja tidak punya tanggal.
    """
    kind: str = Field(default="tempo",
                      pattern="^(tunai|dp|tempo|po_berikutnya|custom)$")
    due_date: date | None = None
    amount: Decimal = Field(gt=0)
    note: str | None = None


class InvoiceIn(BaseModel):
    contact_id: str
    date: date
    warehouse_id: str | None = None
    notes: str | None = None
    lines: list[InvoiceLineIn] = Field(min_length=1)
    # Kosong -> dibuatkan satu termin dari payment_term_days customer.
    # Total termin wajib sama persis dengan total faktur.
    terms: list[InvoiceTermIn] | None = None


class InvoiceLineOut(ORMModel):
    id: str
    description: str
    quantity: Decimal        # dalam botol (satuan dasar)
    qty_input: Decimal       # seperti diketik user
    unit: str                # "dus" | "botol"
    unit_factor: int         # botol per satuan, snapshot saat transaksi
    unit_price: Decimal      # per `unit`
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal
    note: str | None = None


class StockWarning(BaseModel):
    """Peringatan stok kurang saat faktur diterbitkan (nilai sudah diformat
    'dus + botol' oleh services/units.py)."""
    product: str
    diminta: str
    tersedia: str
    kurang: str


class InvoiceCreatedOut(BaseModel):
    """Respons POST /invoices.

    Bukan `InvoiceOut`: endpoint ini juga mengembalikan `stock_warnings`, dan
    memakai InvoiceOut membuat FastAPI menolak respons (ResponseValidationError)
    SETELAH faktur ter-commit — klien melihat 500 padahal fakturnya tersimpan,
    lalu mengulang dan membuat faktur ganda.
    """
    id: str
    number: str
    status: str
    stock_warnings: list[StockWarning] = []


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
