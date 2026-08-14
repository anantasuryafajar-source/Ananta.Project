"""Keterangan kondisi barang pada master produk.

Keterangan yang diketik per baris saat PEMBELIAN (mis. "2 botol pecah") kini
ikut menempel ke produknya, supaya terlihat di daftar Produk & Stok tanpa harus
membuka dokumen pembelian. Terbaru menimpa yang lama; bisa diubah/dikosongkan
dari form produk tanpa mengubah dokumen aslinya.

Dijaga (idempoten) seperti 0002 & 0003: revisi 0001 membuat skema dari model
saat ini, jadi database BARU sudah punya kolom ini dan langkahnya dilewati.

Revision ID: 0004_keterangan_produk
Revises: 0003_keterangan_per_baris
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_keterangan_produk"
down_revision = "0003_keterangan_per_baris"
branch_labels = None
depends_on = None


def _kolom(insp, tabel: str) -> set[str]:
    try:
        return {c["name"] for c in insp.get_columns(tabel)}
    except Exception:
        return set()


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "products" in set(insp.get_table_names()) and "note" not in _kolom(insp, "products"):
        op.add_column("products", sa.Column("note", sa.String(255), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "products" in set(insp.get_table_names()) and "note" in _kolom(insp, "products"):
        op.drop_column("products", "note")
