"""Tabel Lembar Hitung — kesepakatan bagi hasil & komisi per faktur.

DIREKONSTRUKSI. Revisi ini tidak pernah ikut ter-commit, padahal
`0010_payout` menunjuk ke sini sebagai `down_revision` — akibatnya SELURUH
perintah alembic gagal dengan "Can't locate revision identified by
'0009_lembar_hitung'", bahkan `alembic heads`. Isinya disusun ulang dari
`app/models/profit_sheet.py`.

Dijaga (idempoten) seperti 0002-0008: revisi 0001 membuat skema dengan
`create_all()` dari model saat ini, jadi database BARU sudah punya kedua tabel
ini dan langkahnya dilewati - bukan gagal karena tabel sudah ada.

Catatan nama: kolom `pengurang_per_dus` di sini sempat bernama
`ongkir_per_dus`, dan itu keliru. Angka ini murni variabel pengurang komisi
(mis. Rp50.000/dus pada skema Rusdi) - tidak ada hubungannya dengan
`courier_expenses` dan tidak pernah masuk jurnal. Yang di
`commission_schemes.ongkir_per_dus` (revisi 0008) adalah hal berbeda dan tetap
bernama begitu.

Revision ID: 0009_lembar_hitung
Revises: 0008_ongkir_per_dus
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_lembar_hitung"
down_revision = "0008_ongkir_per_dus"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)
QTY = sa.Numeric(18, 4)


def upgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())

    if "profit_sheets" not in tabel:
        op.create_table(
            "profit_sheets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36),
                      sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("number", sa.String(40), nullable=False, index=True),
            sa.Column("date", sa.Date, nullable=False, index=True),
            sa.Column("invoice_id", sa.String(36),
                      sa.ForeignKey("invoices.id"), nullable=False, index=True),
            # draft | disetujui | ditransfer | batal
            sa.Column("status", sa.String(12), nullable=False,
                      server_default="draft", index=True),
            # Snapshot angka faktur saat lembar dibuat - jangan dibaca ulang.
            sa.Column("penjualan", MONEY, nullable=False, server_default="0"),
            sa.Column("hpp_riil", MONEY, nullable=False, server_default="0"),
            sa.Column("jumlah_dus", QTY, nullable=False, server_default="0"),
            # Variabel kesepakatan yang diketik user.
            sa.Column("modal_perjanjian", MONEY, nullable=True),
            sa.Column("hpp_dasar_komisi", MONEY, nullable=True),
            sa.Column("pengurang_per_dus", MONEY, nullable=False,
                      server_default="0"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("void_journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("void_reason", sa.String(255), nullable=True),
            sa.Column("created_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )

    if "profit_sheet_lines" not in tabel:
        op.create_table(
            "profit_sheet_lines",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("sheet_id", sa.String(36),
                      sa.ForeignKey("profit_sheets.id"), nullable=False,
                      index=True),
            sa.Column("urutan", sa.Integer, nullable=False, server_default="0"),
            sa.Column("payee_name", sa.String(120), nullable=False),
            # komisi | bagi_hasil - menentukan pasangan akun jurnalnya.
            sa.Column("jenis", sa.String(16), nullable=False, index=True),
            # Daftar TERTUTUP, lihat models/profit_sheet.py::DASAR.
            sa.Column("dasar", sa.String(24), nullable=False),
            sa.Column("persen", MONEY, nullable=False, server_default="0"),
            sa.Column("nominal", MONEY, nullable=False, server_default="0"),
            # Hasil hitung yang DIBEKUKAN - inilah angka yang dijurnal.
            sa.Column("amount", MONEY, nullable=False, server_default="0"),
            sa.Column("basis_amount", MONEY, nullable=False, server_default="0"),
            sa.Column("note", sa.String(255), nullable=True),
            # NULL = masih utang; terisi saat haknya benar-benar ditransfer.
            sa.Column("settlement_journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
        )


def downgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())
    # Baris dulu: ada foreign key ke tabel induknya.
    if "profit_sheet_lines" in tabel:
        op.drop_table("profit_sheet_lines")
    if "profit_sheets" in tabel:
        op.drop_table("profit_sheets")
