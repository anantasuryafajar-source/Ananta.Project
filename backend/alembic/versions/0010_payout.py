"""Hak internal terakrual: insentif penjualan & bagi hasil omzet.

Tabel `payouts` menampung dua jenis hak yang TIDAK melekat pada satu faktur:

    insentif  -> 4,3% / 5,3% (+ booster 1%) atas UANG MASUK BERSIH,
                 diakui per cicilan       -> 6-1400 / 2-1800
    omzet     -> 18% Nyokap Sam + 14% Delvina atas OMZET BULANAN,
                 diakui saat tutup buku   -> 6-1500 / 2-1900

Komisi pihak ketiga & hak mitra TIDAK di sini: keduanya melekat pada faktur
dan sudah diakui penuh saat lembar hitung disetujui (`profit_sheets`).
Mengakrualnya ulang per cicilan akan membuat komisi yang sama terjurnal dua
kali. Prorata untuk komisi hanya menentukan berapa yang boleh DITRANSFER.

Akun 6-1400/2-1800/6-1500/2-1900 tidak dibuat di sini - akun dibuat per
perusahaan lewat `accounts_map.ensure_account`, dan `seed_asf` memasukkannya
untuk perusahaan baru.

Revision ID: 0010_payout
Revises: 0009_lembar_hitung
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_payout"
down_revision = "0009_lembar_hitung"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)


def upgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())
    if "payouts" in tabel:
        return
    op.create_table(
        "payouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"),
                  nullable=False, index=True),
        sa.Column("number", sa.String(40), nullable=False, index=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        # insentif | omzet
        sa.Column("jenis", sa.String(12), nullable=False, index=True),
        sa.Column("payee_name", sa.String(120), nullable=False, index=True),
        # Periode dasar - dipakai juga untuk mencegah dobel akrual saat tutup
        # buku dijalankan ulang.
        sa.Column("periode_tahun", sa.Integer, nullable=False, index=True),
        sa.Column("periode_bulan", sa.Integer, nullable=False, index=True),
        sa.Column("term", sa.Integer, nullable=False, server_default="0"),
        sa.Column("dasar", MONEY, nullable=False, server_default="0"),
        sa.Column("persen", MONEY, nullable=True),
        sa.Column("amount", MONEY, nullable=False, server_default="0"),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"),
                  nullable=True, index=True),
        # terutang | dibayar | batal
        sa.Column("status", sa.String(12), nullable=False,
                  server_default="terutang", index=True),
        sa.Column("paid_date", sa.Date, nullable=True),
        sa.Column("expense_account_id", sa.String(36),
                  sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("payable_account_id", sa.String(36),
                  sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("paid_account_id", sa.String(36),
                  sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("journal_id", sa.String(36), sa.ForeignKey("journals.id"),
                  nullable=True),
        sa.Column("settlement_journal_id", sa.String(36),
                  sa.ForeignKey("journals.id"), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())
    if "payouts" in tabel:
        op.drop_table("payouts")
