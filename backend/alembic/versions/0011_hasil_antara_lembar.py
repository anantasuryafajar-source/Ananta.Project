"""Simpan hasil antara Lembar Hitung: profit bersama, bagian ASF, hidden margin.

Ketiganya turunan dan bisa dihitung ulang dari variabel kesepakatan, tetapi
dokumen keuangan harus bisa dibaca ulang TANPA menjalankan kembali rumusnya:
"bagian ASF 150" perlu tetap terbaca 150 bertahun-tahun kemudian, walau
variabel kesepakatannya sudah tidak lagi dipahami siapa pun.

`hidden_margin` (= modal_perjanjian - hpp_riil) disimpan murni sebagai angka
TAMPILAN dan tidak pernah dijurnal. Menjurnalnya sebagai pendapatan terpisah
membuat laba dobel dan persediaan melenceng.

Kolom terpisah dari 0009 karena 0009 sudah terlanjur diterapkan di database
yang berjalan; menambahkannya ke sana berarti database itu tidak akan pernah
mendapat kolomnya.

Dijaga inspector seperti revisi lain: database BARU sudah punya kolom ini dari
`create_all()` di 0001, jadi langkahnya dilewati - bukan gagal.

Revision ID: 0011_hasil_antara_lembar
Revises: 0010_payout
"""
import sqlalchemy as sa
from alembic import op

revision = "0011_hasil_antara_lembar"
down_revision = "0010_payout"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)
KOLOM = ("profit_bersama", "bagian_asf", "hidden_margin")


def _kolom(insp, tabel: str) -> set[str]:
    try:
        return {c["name"] for c in insp.get_columns(tabel)}
    except Exception:
        return set()


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "profit_sheets" not in set(insp.get_table_names()):
        return
    ada = _kolom(insp, "profit_sheets")
    for nama in KOLOM:
        if nama not in ada:
            op.add_column(
                "profit_sheets",
                sa.Column(nama, MONEY, nullable=False, server_default="0"),
            )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "profit_sheets" not in set(insp.get_table_names()):
        return
    ada = _kolom(insp, "profit_sheets")
    for nama in KOLOM:
        if nama in ada:
            op.drop_column("profit_sheets", nama)
