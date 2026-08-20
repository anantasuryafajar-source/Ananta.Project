"""Keterangan per BARIS pada faktur, tagihan, PO, dan SO.

Sebelumnya keterangan hanya ada di tingkat dokumen (`invoices.notes`,
`bills.notes`), padahal client butuh catatan yang menempel pada satu item —
mis. "2 botol pecah" atau "beda batch" — yang tidak berlaku untuk item lain
di nota yang sama.

Kolom `description` yang sudah ada TIDAK bisa dipakai untuk ini: ia terisi
otomatis dengan nama produk dan di UI hanya bisa diketik saat baris TIDAK
memakai produk dari master.

Dijaga (idempoten) dengan pola yang sama seperti 0002: revisi 0001 membuat skema
dari model saat ini, jadi database BARU sudah punya kolom ini dan langkahnya harus
dilewati, bukan gagal. Selama baseline masih berupa create_all, setiap revisi
berikutnya perlu penjagaan serupa.

Revision ID: 0003_keterangan_per_baris
Revises: 0002_satuan_dus_botol
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_keterangan_per_baris"
down_revision = "0002_satuan_dus_botol"
branch_labels = None
depends_on = None

TABEL = (
    "invoice_lines",
    "bill_lines",
    "purchase_order_lines",
    "sales_order_lines",
)


def _kolom(insp, tabel: str) -> set[str]:
    try:
        return {c["name"] for c in insp.get_columns(tabel)}
    except Exception:  # tabel belum ada
        return set()


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    ada = set(insp.get_table_names())
    for tabel in TABEL:
        if tabel in ada and "note" not in _kolom(insp, tabel):
            op.add_column(tabel, sa.Column("note", sa.String(255), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    ada = set(insp.get_table_names())
    for tabel in TABEL:
        if tabel in ada and "note" in _kolom(insp, tabel):
            op.drop_column(tabel, "note")
