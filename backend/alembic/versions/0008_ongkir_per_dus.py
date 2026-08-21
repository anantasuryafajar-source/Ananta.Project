"""Tarif ongkir per dus di skema komisi (komisi bertingkat).

Kasus client 2026-08-21: margin dikurangi dulu tarif ongkir per dus, sisanya
baru dipersenkan — mis. (360.000 - 2 dus x 50.000) x 4% = 10.400.

Menambah satu kolom, bukan mesin rumus: tipe `persen_margin_min_ongkir` masuk
ke daftar TERTUTUP di CommissionScheme.type. `ongkir_per_dus` hanya dipakai
tipe itu dan NULL untuk tipe lain.

Tarif ini sengaja TIDAK diambil dari `courier_expenses`. Itu ongkir AKTUAL yang
dibayar ke ekspedisi; yang ini angka KESEPAKATAN dengan sales. Keduanya sering
berbeda, dan memakai yang salah berarti orang dibayar keliru.

Revision ID: 0008_ongkir_per_dus
Revises: 0007_kustomisasi_komisi_termin
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_ongkir_per_dus"
down_revision = "0007_kustomisasi_komisi_termin"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "commission_schemes" not in set(insp.get_table_names()):
        return  # dibuat 0007 dengan kolom ini sudah ada (database baru)
    kolom = {c["name"] for c in insp.get_columns("commission_schemes")}
    if "ongkir_per_dus" not in kolom:
        with op.batch_alter_table("commission_schemes") as batch:
            batch.add_column(sa.Column("ongkir_per_dus", MONEY, nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "commission_schemes" not in set(insp.get_table_names()):
        return
    kolom = {c["name"] for c in insp.get_columns("commission_schemes")}
    if "ongkir_per_dus" in kolom:
        with op.batch_alter_table("commission_schemes") as batch:
            batch.drop_column("ongkir_per_dus")
