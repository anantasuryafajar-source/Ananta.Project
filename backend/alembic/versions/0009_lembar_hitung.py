"""Lembar Hitung: bagi hasil & komisi bertingkat per faktur.

Dua tabel baru:

    profit_sheets       satu lembar per faktur - angka dasar kesepakatan
    profit_sheet_lines  siapa dapat apa, dan berapa

Kenapa tabel sendiri dan bukan kolom di `invoices`: faktur adalah dokumen yang
DILIHAT CUSTOMER dan harganya harus harga sebenarnya. Memisahkan kesepakatan
internal ke sini menutup dua jalur kebocoran yang sudah pernah terjadi -
markup diam-diam di `unit_price`, dan komisi dititipkan ke `discount`.

Catatan nama: variabel pengurang komisi di sini bernama `pengurang_per_dus`,
BUKAN `ongkir_per_dus` seperti kolom yang ditambahkan 0008 ke
`commission_schemes`. Nama itu keliru untuk konteks lembar hitung: angkanya
murni variabel pengurang komisi, tidak ada hubungannya dengan
`courier_expenses`, dan tidak pernah masuk jurnal.

Akun 6-1100/2-1600/6-1300/2-1700 tidak dibuat di sini - akun dibuat per
perusahaan lewat `accounts_map.ensure_account`, dan `seed_asf` memasukkannya
untuk perusahaan baru.

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
    # Dijaga inspector, sama seperti 0002 & 0010: revisi ini harus jalan di
    # database BARU (yang tabelnya sudah dibuat 0001 dari model) maupun di
    # database lama, jadi keberadaan tabel bikin ia no-op alih-alih gagal.
    tabel = set(sa.inspect(op.get_bind()).get_table_names())

    if "profit_sheets" not in tabel:
        op.create_table(
            "profit_sheets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"),
                      nullable=False, index=True),
            sa.Column("number", sa.String(40), nullable=False, index=True),
            sa.Column("date", sa.Date, nullable=False, index=True),
            sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"),
                      nullable=False, index=True),
            # draft | disetujui | ditransfer | batal
            sa.Column("status", sa.String(12), nullable=False,
                      server_default="draft", index=True),
            # ---- dasar perhitungan, semua di-snapshot saat lembar dibuat ----
            sa.Column("penjualan", MONEY, nullable=False, server_default="0"),
            # Dibaca dari journal_entries, bukan dihitung ulang dari stok:
            # avg_cost sudah bergerak sejak faktur diposting.
            sa.Column("hpp_riil", MONEY, nullable=False, server_default="0"),
            sa.Column("hpp_dasar_komisi", MONEY, nullable=False,
                      server_default="0"),
            sa.Column("modal_perjanjian", MONEY, nullable=True),
            sa.Column("pengurang_per_dus", MONEY, nullable=True),
            # Pecahan: 18 botol dari dus isi 12 = 1,5 dus. Bukan dibulatkan.
            sa.Column("jumlah_dus", QTY, nullable=False, server_default="0"),
            # ---- hasil antara, disimpan supaya angkanya bisa ditelusuri ----
            sa.Column("profit_bersama", MONEY, nullable=False,
                      server_default="0"),
            sa.Column("bagian_asf", MONEY, nullable=False, server_default="0"),
            # Turunan & TIDAK pernah dijurnal - disimpan sebagai angka tampilan.
            sa.Column("hidden_margin", MONEY, nullable=False,
                      server_default="0"),
            sa.Column("journal_id", sa.String(36), sa.ForeignKey("journals.id"),
                      nullable=True),
            sa.Column("void_journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"),
                      nullable=True),
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
            sa.Column("sequence", sa.Integer, nullable=False,
                      server_default="0"),
            sa.Column("payee_name", sa.String(120), nullable=False, index=True),
            # komisi -> 6-1100 / 2-1600 ; bagi_hasil -> 6-1300 / 2-1700
            sa.Column("jenis", sa.String(12), nullable=False, index=True),
            # Daftar TERTUTUP, lihat profit_sheet_service.DASAR.
            sa.Column("dasar", sa.String(24), nullable=False),
            sa.Column("persen", MONEY, nullable=True),
            sa.Column("nominal", MONEY, nullable=True),
            # Sumber kebenaran nilai hak - tidak dihitung ulang setelah
            # disetujui, sama seperti SalesCommission.amount.
            sa.Column("amount", MONEY, nullable=False, server_default="0"),
            sa.Column("expense_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=True),
            sa.Column("payable_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=True),
            sa.Column("paid_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=True),
            sa.Column("paid_date", sa.Date, nullable=True),
            sa.Column("settlement_journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("note", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    tabel = set(sa.inspect(op.get_bind()).get_table_names())
    # Anak dulu, baru induk - FK-nya menunjuk profit_sheets.
    if "profit_sheet_lines" in tabel:
        op.drop_table("profit_sheet_lines")
    if "profit_sheets" in tabel:
        op.drop_table("profit_sheets")
