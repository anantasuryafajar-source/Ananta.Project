"""Tambah satuan dus/botol ke database yang SUDAH TERISI — tanpa reset.

Kenapa revisi ini ada: revisi 0001 membuat skema dengan `create_all()` dari model
saat ini, jadi database BARU langsung punya semua kolom satuan. Tetapi database
yang sudah hidup sebelum Alembic dipakai (skemanya dulu dibuat create_all di dalam
seed) hanya punya kolom lama — `create_all(checkfirst=True)` tidak menambah kolom
ke tabel yang sudah ada. Revisi inilah yang mengejar ketertinggalan itu, sehingga
akun pengguna, role, tautan Telegram, dan riwayat transaksi TIDAK perlu dibuang.

Karena itu semua operasi di sini **dijaga (idempoten)**: pada database baru yang
0001-nya sudah membuat kolomnya, langkah-langkahnya dilewati, bukan gagal.

Yang dikerjakan:
1. products      : + pack_unit, pack_size, pack_purchase_price
2. baris transaksi (invoice_lines, bill_lines, purchase_order_lines,
                   sales_order_lines): + qty_input, unit, unit_factor
3. stock_levels.avg_cost & stock_movements.unit_cost: Numeric(18,2) -> (18,4)
4. Pengisian nilai awal kolom baru dari data yang sudah ada.

Asumsi pengisian yang perlu diketahui:
- `products.purchase_price` LAMA bernilai modal per DUS (seed lama memakai angka
  per dus, mis. JW Black 3.700.000), jadi nilai itu dipindah ke
  `pack_purchase_price` dan `purchase_price` dihitung ulang menjadi per botol.
- Baris transaksi LAMA dianggap satuan BOTOL dengan faktor 1 (`qty_input` =
  `quantity`). Ini menjaga agar angka stok & HPP historis tidak bergeser sama
  sekali; riwayatnya hanya akan tampil sebagai "n botol".
- Isi per dus diisi 12, kecuali Robinson Vodka (48). Chivas 200ml (24) belum ada
  di data lama — produk itu ditambahkan oleh `python -m app.master_asf`.

Revision ID: 0002_satuan_dus_botol
Revises: 0001_baseline
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_satuan_dus_botol"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

# Tabel baris transaksi yang mendapat kolom satuan.
LINE_TABLES = (
    "invoice_lines",
    "bill_lines",
    "purchase_order_lines",
    "sales_order_lines",
)


def _kolom(insp, tabel: str) -> dict:
    """Peta nama kolom -> info kolom. Kosong bila tabelnya tidak ada."""
    try:
        return {c["name"]: c for c in insp.get_columns(tabel)}
    except Exception:  # tabel belum ada
        return {}


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tabel_ada = set(insp.get_table_names())

    # ---------------------------------------------------------------- products
    if "products" in tabel_ada:
        kol = _kolom(insp, "products")

        if "pack_unit" not in kol:
            op.add_column("products", sa.Column(
                "pack_unit", sa.String(20), nullable=False,
                server_default="dus"))

        if "pack_size" not in kol:
            op.add_column("products", sa.Column(
                "pack_size", sa.Integer(), nullable=True))
            # Robinson Vodka 48 botol/dus; produk lain default 12.
            conn.execute(sa.text(
                "UPDATE products SET pack_size = CASE "
                "  WHEN lower(name) LIKE '%robinson%' THEN 48 ELSE 12 END "
                "WHERE pack_size IS NULL"))
            op.alter_column("products", "pack_size", nullable=False,
                            server_default="12")

        if "pack_purchase_price" not in kol:
            op.add_column("products", sa.Column(
                "pack_purchase_price", sa.Numeric(18, 2), nullable=True))
            # Modal lama tercatat per DUS -> pindahkan, lalu turunkan per botol.
            conn.execute(sa.text(
                "UPDATE products SET pack_purchase_price = "
                "COALESCE(purchase_price, 0) WHERE pack_purchase_price IS NULL"))
            conn.execute(sa.text(
                "UPDATE products SET purchase_price = ROUND("
                "  COALESCE(pack_purchase_price, 0) / "
                "  CAST(GREATEST(COALESCE(pack_size, 12), 1) AS numeric), 2)"))
            op.alter_column("products", "pack_purchase_price", nullable=False,
                            server_default="0")

        # Satuan dasar barang: 'pcs' warisan lama -> 'botol'.
        conn.execute(sa.text(
            "UPDATE products SET unit = 'botol' "
            "WHERE unit IS NULL OR lower(unit) IN ('pcs', 'pc', '')"))

    # ------------------------------------------------- baris transaksi (4 tabel)
    for tabel in LINE_TABLES:
        if tabel not in tabel_ada:
            continue
        kol = _kolom(insp, tabel)

        if "qty_input" not in kol:
            op.add_column(tabel, sa.Column(
                "qty_input", sa.Numeric(18, 4), nullable=True))
            # Baris lama dianggap sudah dalam satuan dasar -> qty_input = quantity
            # supaya stok & HPP historis tidak bergeser.
            conn.execute(sa.text(
                f"UPDATE {tabel} SET qty_input = quantity "
                f"WHERE qty_input IS NULL"))
            op.alter_column(tabel, "qty_input", nullable=False,
                            server_default="1")

        if "unit" not in kol:
            op.add_column(tabel, sa.Column(
                "unit", sa.String(20), nullable=False, server_default="botol"))

        if "unit_factor" not in kol:
            op.add_column(tabel, sa.Column(
                "unit_factor", sa.Integer(), nullable=False, server_default="1"))

    # ------------------------------- presisi biaya per satuan: 2 -> 4 desimal
    # (lihat UnitCost di models/base.py — 2 desimal membuat valuasi stok
    #  melenceng dari saldo akun Persediaan di jurnal)
    for tabel, kolom in (("stock_levels", "avg_cost"),
                         ("stock_movements", "unit_cost")):
        if tabel not in tabel_ada:
            continue
        info = _kolom(insp, tabel).get(kolom)
        if info is None:
            continue
        tipe = info["type"]
        if getattr(tipe, "scale", None) == 4:
            continue  # sudah 4 desimal (database baru dari 0001)
        op.alter_column(tabel, kolom,
                        existing_type=sa.Numeric(18, 2),
                        type_=sa.Numeric(18, 4),
                        existing_nullable=False)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tabel_ada = set(insp.get_table_names())

    for tabel, kolom in (("stock_levels", "avg_cost"),
                         ("stock_movements", "unit_cost")):
        if tabel in tabel_ada:
            op.alter_column(tabel, kolom,
                            existing_type=sa.Numeric(18, 4),
                            type_=sa.Numeric(18, 2),
                            existing_nullable=False)

    for tabel in LINE_TABLES:
        if tabel not in tabel_ada:
            continue
        kol = _kolom(insp, tabel)
        for kolom in ("unit_factor", "unit", "qty_input"):
            if kolom in kol:
                op.drop_column(tabel, kolom)

    if "products" in tabel_ada:
        kol = _kolom(insp, "products")
        for kolom in ("pack_purchase_price", "pack_size", "pack_unit"):
            if kolom in kol:
                op.drop_column("products", kolom)
