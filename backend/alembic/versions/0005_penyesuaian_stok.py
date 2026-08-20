"""Tabel penyesuaian stok (opname & stok awal).

Fitur baru: memasukkan hasil hitung fisik gudang tanpa membuat dokumen
pembelian. Sebelum ini stok hanya bisa masuk lewat Pembelian, sehingga opname
berarti menciptakan utang palsu ke supplier yang tidak pernah menagih.

Dijaga (idempoten) seperti 0002-0004: revisi 0001 membuat skema dengan
`create_all()` dari model saat ini, jadi database BARU sudah punya kedua tabel
ini dan langkahnya dilewati - bukan gagal karena tabel sudah ada.

Akun lawan jurnalnya (3-4000 Saldo Awal Persediaan & 5-2000 Selisih Persediaan)
TIDAK dibuat di sini. Akun dibuat per perusahaan, bukan per database, dan
`accounts_map.ensure_account()` membuatnya saat pertama dibutuhkan - satu jalur
yang sama untuk database lama maupun baru.

Revision ID: 0005_penyesuaian_stok
Revises: 0004_keterangan_produk
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_penyesuaian_stok"
down_revision = "0004_keterangan_produk"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)
QTY = sa.Numeric(18, 4)
UNIT_COST = sa.Numeric(18, 4)


def upgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())

    if "stock_adjustments" not in tabel:
        op.create_table(
            "stock_adjustments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36),
                      sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("number", sa.String(40), nullable=False, index=True),
            sa.Column("date", sa.Date, nullable=False, index=True),
            sa.Column("warehouse_id", sa.String(36),
                      sa.ForeignKey("warehouses.id"), nullable=False, index=True),
            sa.Column("mode", sa.String(10), nullable=False,
                      server_default="opname", index=True),
            sa.Column("hitungan_lengkap", sa.Boolean, nullable=False,
                      server_default=sa.false()),
            sa.Column("status", sa.String(12), nullable=False,
                      server_default="posted", index=True),
            sa.Column("total_value", MONEY, nullable=False, server_default="0"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("created_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )

    if "stock_adjustment_lines" not in tabel:
        op.create_table(
            "stock_adjustment_lines",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("adjustment_id", sa.String(36),
                      sa.ForeignKey("stock_adjustments.id"), nullable=False,
                      index=True),
            sa.Column("product_id", sa.String(36),
                      sa.ForeignKey("products.id"), nullable=False, index=True),
            sa.Column("description", sa.String(255), nullable=False),
            # Seperti diketik user: "15 dus 11 botol" masuk sebagai dua kolom.
            sa.Column("qty_dus", QTY, nullable=False, server_default="0"),
            sa.Column("qty_botol", QTY, nullable=False, server_default="0"),
            sa.Column("pack_size_snapshot", sa.Integer, nullable=False,
                      server_default="12"),
            # Dalam BOTOL.
            sa.Column("qty_counted", QTY, nullable=False, server_default="0"),
            sa.Column("qty_before", QTY, nullable=False, server_default="0"),
            sa.Column("qty_diff", QTY, nullable=False, server_default="0"),
            sa.Column("unit_cost", UNIT_COST, nullable=False, server_default="0"),
            sa.Column("line_value", MONEY, nullable=False, server_default="0"),
            sa.Column("note", sa.Text, nullable=True),
        )


def downgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())
    # Baris dulu: ada foreign key ke tabel induknya.
    if "stock_adjustment_lines" in tabel:
        op.drop_table("stock_adjustment_lines")
    if "stock_adjustments" in tabel:
        op.drop_table("stock_adjustments")
