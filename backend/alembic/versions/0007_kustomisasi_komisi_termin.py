"""Skema komisi, uang muka pelanggan (DP), dan jadwal termin faktur.

Tiga tambahan yang saling bebas (lihat RANCANGAN-KUSTOMISASI.md):

1. `commission_schemes` + kolom snapshot di `sales_commissions` — menampung
   komisi flat, per botol, persen, dan `manual` untuk kasus khusus.
2. `customer_advances` + `advance_allocations` — DP diterima sebelum barang
   keluar. Ini yang membuat neraca tetap benar: DP adalah kewajiban di
   2-1500, bukan pendapatan dan bukan piutang negatif.
3. `invoice_terms` — jadwal "kapan berapa" menggantikan due_date tunggal,
   supaya "DP 30% lalu tempo 30 hari" bisa dicatat apa adanya.
4. `payable_account_id` + `settlement_journal_id` di `sales_commissions` —
   komisi pindah ke basis AKRUAL: beban diakui saat nilainya disepakati
   (Cr 2-1600 Utang Komisi), pembayaran hanya menutup utang itu.

Komisi LAMA yang terlanjur dicatat tanpa jurnal pengakuan TIDAK ditambal di
sini. Menambalnya berarti menambah beban ke laporan periode yang mungkin sudah
dilaporkan ke orang lain — itu harus dilihat manusia dulu. Jalankan
`python -m app.backfill_komisi_akrual` (dry run) lalu `--terapkan`.

Akun 2-1500 Uang Muka Pelanggan TIDAK dibuat di sini: akun dibuat per
perusahaan, bukan per database. `accounts_map.ensure_account("customer_advance")`
membuatnya saat pertama dibutuhkan - satu jalur yang sama untuk database lama
maupun baru.

Dijaga (idempoten) seperti 0002-0006. Tidak ada kolom lama yang berubah tipe
dan tidak ada backfill, jadi tidak ada angka historis yang bisa bergeser:
faktur lama tanpa `invoice_terms` tetap dihitung dengan `due_date`-nya sendiri
oleh `reports.ar_aging`.

Revision ID: 0007_kustomisasi_komisi_termin
Revises: 0006_komisi_penjualan
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_kustomisasi_komisi_termin"
down_revision = "0006_komisi_penjualan"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tabel = set(insp.get_table_names())

    # ---------------------------------------------------------- SKEMA KOMISI
    if "commission_schemes" not in tabel:
        op.create_table(
            "commission_schemes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36),
                      sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            # nominal | per_botol | persen_margin | persen_omzet | manual
            sa.Column("type", sa.String(20), nullable=False, index=True),
            sa.Column("value", MONEY, nullable=False, server_default="0"),
            sa.Column("default_for_contact_id", sa.String(36),
                      sa.ForeignKey("contacts.id"), nullable=True, index=True),
            sa.Column("default_for_product_id", sa.String(36),
                      sa.ForeignKey("products.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean, nullable=False,
                      server_default=sa.true(), index=True),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )

    if "sales_commissions" in tabel:
        kolom = {c["name"] for c in insp.get_columns("sales_commissions")}
        with op.batch_alter_table("sales_commissions") as batch:
            if "scheme_id" not in kolom:
                batch.add_column(sa.Column("scheme_id", sa.String(36),
                                           nullable=True))
            if "scheme_type" not in kolom:
                batch.add_column(sa.Column("scheme_type", sa.String(20),
                                           nullable=True))
            if "scheme_value" not in kolom:
                batch.add_column(sa.Column("scheme_value", MONEY, nullable=True))
            # --- Pindah ke basis akrual ---
            # `journal_id` yang sudah ada kini berarti jurnal PENGAKUAN beban;
            # pelunasan kas dipisah ke `settlement_journal_id` supaya dua
            # kejadian itu bisa ditelusuri sendiri-sendiri.
            if "payable_account_id" not in kolom:
                batch.add_column(sa.Column("payable_account_id", sa.String(36),
                                           nullable=True))
            if "settlement_journal_id" not in kolom:
                batch.add_column(sa.Column("settlement_journal_id", sa.String(36),
                                           nullable=True))

    # ---------------------------------------------------------- UANG MUKA
    if "customer_advances" not in tabel:
        op.create_table(
            "customer_advances",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36),
                      sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("number", sa.String(40), nullable=False, index=True),
            sa.Column("contact_id", sa.String(36),
                      sa.ForeignKey("contacts.id"), nullable=False, index=True),
            sa.Column("date", sa.Date, nullable=False, index=True),
            sa.Column("amount", MONEY, nullable=False, server_default="0"),
            sa.Column("allocated_total", MONEY, nullable=False,
                      server_default="0"),
            sa.Column("status", sa.String(12), nullable=False,
                      server_default="open", index=True),
            sa.Column("cash_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=False),
            sa.Column("advance_account_id", sa.String(36),
                      sa.ForeignKey("accounts.id"), nullable=False),
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

    if "advance_allocations" not in tabel:
        op.create_table(
            "advance_allocations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36),
                      sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("advance_id", sa.String(36),
                      sa.ForeignKey("customer_advances.id"), nullable=False,
                      index=True),
            sa.Column("invoice_id", sa.String(36),
                      sa.ForeignKey("invoices.id"), nullable=False, index=True),
            sa.Column("date", sa.Date, nullable=False, index=True),
            sa.Column("amount", MONEY, nullable=False, server_default="0"),
            sa.Column("journal_id", sa.String(36),
                      sa.ForeignKey("journals.id"), nullable=True),
            sa.Column("created_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )

    # ---------------------------------------------------------- JADWAL TERMIN
    if "invoice_terms" not in tabel:
        op.create_table(
            "invoice_terms",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("invoice_id", sa.String(36),
                      sa.ForeignKey("invoices.id"), nullable=False, index=True),
            sa.Column("sequence", sa.Integer, nullable=False,
                      server_default="1"),
            # tunai | dp | tempo | po_berikutnya | custom
            sa.Column("kind", sa.String(16), nullable=False,
                      server_default="tempo", index=True),
            # NULL = belum ada tanggal (mis. "tagih di PO berikutnya").
            # Bukan berarti jatuh tempo hari faktur - lihat reports.ar_aging.
            sa.Column("due_date", sa.Date, nullable=True, index=True),
            sa.Column("amount", MONEY, nullable=False, server_default="0"),
            sa.Column("settled_amount", MONEY, nullable=False,
                      server_default="0"),
            sa.Column("note", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tabel = set(insp.get_table_names())

    if "invoice_terms" in tabel:
        op.drop_table("invoice_terms")
    # Anak dulu: punya foreign key ke customer_advances.
    if "advance_allocations" in tabel:
        op.drop_table("advance_allocations")
    if "customer_advances" in tabel:
        op.drop_table("customer_advances")

    if "sales_commissions" in tabel:
        kolom = {c["name"] for c in insp.get_columns("sales_commissions")}
        with op.batch_alter_table("sales_commissions") as batch:
            for k in ("settlement_journal_id", "payable_account_id",
                      "scheme_value", "scheme_type", "scheme_id"):
                if k in kolom:
                    batch.drop_column(k)

    if "commission_schemes" in tabel:
        op.drop_table("commission_schemes")
