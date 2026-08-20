"""Tabel komisi penjualan (kesepakatan internal, di luar faktur).

Fitur baru: mencatat komisi yang hanya berlaku di kasus tertentu dan nilainya
beda-beda, tanpa menyentuh harga di faktur. Sebelum ini komisi cuma ada
sebagai laporan simulasi (`reports_ext.commission`, rate rata untuk semua SKU)
yang tidak pernah berjurnal — akibatnya akun 6-1100 Beban Komisi selalu nol
dan Laba Rugi kelebihan laba sebesar total komisi yang sebenarnya dibayar.

Dijaga (idempoten) seperti 0002-0005: revisi 0001 membuat skema dengan
`create_all()` dari model saat ini, jadi database BARU sudah punya tabel ini
dan langkahnya dilewati - bukan gagal karena tabel sudah ada.

Akun 6-1100 TIDAK dibuat di sini: akun dibuat per perusahaan, bukan per
database, dan sudah ada di `seed_asf.py`. Kalau CoA sebuah perusahaan belum
punya kode itu, `commission_service` menolak dengan pesan jelas alih-alih
diam-diam membuat akun baru.

Revision ID: 0006_komisi_penjualan
Revises: 0005_penyesuaian_stok
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_komisi_penjualan"
down_revision = "0005_penyesuaian_stok"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)
QTY = sa.Numeric(18, 4)


def upgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())

    if "sales_commissions" not in tabel:
        op.create_table(
            "sales_commissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36),
                      sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("number", sa.String(40), nullable=False, index=True),
            sa.Column("date", sa.Date, nullable=False, index=True),
            sa.Column("invoice_id", sa.String(36),
                      sa.ForeignKey("invoices.id"), nullable=False, index=True),
            sa.Column("payee_name", sa.String(120), nullable=False, index=True),
            # nominal | persen_margin | persen_omzet - catatan cara hitung saja.
            sa.Column("basis", sa.String(16), nullable=False,
                      server_default="nominal"),
            sa.Column("rate", QTY, nullable=True),
            sa.Column("amount", MONEY, nullable=False, server_default="0"),
            # terutang -> belum berjurnal; dibayar -> sudah masuk Laba Rugi.
            sa.Column("status", sa.String(12), nullable=False,
                      server_default="terutang", index=True),
            sa.Column("paid_date", sa.Date, nullable=True, index=True),
            sa.Column("expense_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=False),
            sa.Column("paid_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=True),
            sa.Column("journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("created_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())
    if "sales_commissions" in tabel:
        op.drop_table("sales_commissions")
