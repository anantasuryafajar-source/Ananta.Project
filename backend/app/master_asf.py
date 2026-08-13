"""Selaraskan master produk PT ASF dengan daftar resmi client — tanpa reset.

Dipakai pada database yang SUDAH TERISI (akun, transaksi, stok tetap utuh).
Aman dijalankan berulang kali:

    python -m app.master_asf                        # rencana saja (dry-run)
    python -m app.master_asf --terapkan             # simpan
    python -m app.master_asf --bersihkan            # + rencana hapus produk lama
    python -m app.master_asf --bersihkan --terapkan # + hapus produk lama

Yang dikerjakan:
1. Mengganti nama produk yang berubah (mis. "Captain Morgan Spiced Rum" ->
   "Captain Morgan Spiced Gold") sesuai peta RENAMES, supaya tidak jadi duplikat.
2. Memperbarui isi per dus & modal per dus ke angka yang dikonfirmasi client,
   lalu menghitung ulang modal per botol.
3. Menambahkan produk yang belum ada (Chivas 200ml, Azul/Codigo Reposado,
   Mansion Vodka & Whisky) dengan SKU otomatis.
4. Dengan `--bersihkan`: MENGHAPUS produk di luar daftar resmi client, sehingga
   master produk berisi tepat 23 produk. Hanya produk yang BELUM PERNAH dipakai
   transaksi yang dihapus — produk berjejak faktur/tagihan/PO/SO/mutasi stok
   selalu dilewati dan dilaporkan, supaya riwayat akuntansi tidak pernah bolong.
   Biasanya dipakai sesudah `python -m app.reset_transactions`.

Yang TIDAK dikerjakan — disengaja:
- Tidak mengubah SKU produk yang sudah ada. SKU lama yang pendek (mis. "B",
  "RBV") lebih enak diketik di bot Telegram, dan menggantinya hanya menambah
  risiko tanpa manfaat — user tidak pernah melihat SKU di web.
- Tidak menyentuh stok, avg_cost, jurnal, akun pengguna, maupun tautan bot.
"""
import asyncio
import sys
from decimal import Decimal

from sqlalchemy import delete, func, select

from .core.database import SessionLocal
from .models import (
    BillLine, Company, InvoiceLine, POLine, Product, SOLine, StockLevel,
    StockMovement,
)
from .seed_asf import COMPANY_NAME, PRODUCTS
from .services.product_service import generate_sku
from .services.units import base_price_from_pack

# Nama lama (di seed/database lama) -> nama baru sesuai daftar client.
RENAMES = {
    "Captain Morgan Spiced Rum": "Captain Morgan Spiced Gold",
    "JW Black Label 750ml": "JW Black Label",
    "JW Red Label 750ml": "JW Red Label",
    "Chivas Regal 12 YO 750ml": "Chivas Regal 12 YO",
    "Jameson 750ml": "Jameson",
    "Hennessy VSOP EU": "Hennessy VSOP",
    "Jose Cuervo Tequila": "Jose Cuervo",
}


async def _pemakaian(db, product_id: str) -> dict[str, int]:
    """Berapa kali produk dipakai di tiap jenis dokumen. Semua nol = aman dihapus."""
    jumlah = {}
    for label, model in (("faktur", InvoiceLine), ("tagihan", BillLine),
                         ("PO", POLine), ("SO", SOLine),
                         ("mutasi stok", StockMovement)):
        jumlah[label] = (await db.execute(
            select(func.count()).select_from(model)
            .where(model.product_id == product_id)
        )).scalar_one()
    return {k: v for k, v in jumlah.items() if v}


async def run(terapkan: bool = False, bersihkan: bool = False) -> None:
    async with SessionLocal() as db:
        company = (await db.execute(
            select(Company).where(Company.name == COMPANY_NAME)
        )).scalar_one_or_none()
        if company is None:
            print(f"Company '{COMPANY_NAME}' tidak ada. Jalankan seed dulu.")
            return

        rows = (await db.execute(
            select(Product).where(Product.company_id == company.id)
        )).scalars().all()
        by_name = {(p.name or "").strip().lower(): p for p in rows}

        rencana: list[str] = []

        # --- 1) Ganti nama produk yang berubah ---
        for lama, baru in RENAMES.items():
            p = by_name.get(lama.lower())
            if p is None or baru.lower() in by_name:
                continue
            rencana.append(f"RENAME  {p.name!r} -> {baru!r}")
            if terapkan:
                p.name = baru
            by_name.pop(lama.lower(), None)
            by_name[baru.lower()] = p

        # --- 2) Perbarui / 3) tambahkan sesuai daftar client ---
        for name, modal_per_dus, pack_size in PRODUCTS:
            pack_modal = Decimal(modal_per_dus)
            per_botol = base_price_from_pack(pack_modal, pack_size)
            p = by_name.get(name.lower())

            if p is None:
                rencana.append(
                    f"BARU    {name!r}  isi/dus={pack_size}  "
                    f"modal/dus={pack_modal:,}")
                if terapkan:
                    db.add(Product(
                        company_id=company.id,
                        sku=await generate_sku(db, company.id, name),
                        name=name, kind="good",
                        unit="botol", pack_unit="dus", pack_size=pack_size,
                        pack_purchase_price=pack_modal,
                        purchase_price=per_botol,
                        sale_price=Decimal("0"),
                    ))
                continue

            ubah = []
            if int(p.pack_size or 0) != pack_size:
                ubah.append(f"isi/dus {p.pack_size}->{pack_size}")
            if Decimal(str(p.pack_purchase_price or 0)) != pack_modal:
                ubah.append(
                    f"modal/dus {Decimal(str(p.pack_purchase_price or 0)):,}"
                    f"->{pack_modal:,}")
            if not ubah:
                continue
            rencana.append(f"UBAH    {p.name!r}  " + ", ".join(ubah))
            if terapkan:
                p.pack_unit = "dus"
                p.pack_size = pack_size
                p.pack_purchase_price = pack_modal
                p.purchase_price = per_botol
                p.unit = "botol"

        # --- 4) Buang produk di luar daftar resmi (opsional) ---
        dilewati: list[str] = []
        if bersihkan:
            resmi = {name.lower() for name, _, _ in PRODUCTS}
            for p in rows:
                nama_kini = (p.name or "").strip()
                if nama_kini.lower() in resmi:
                    continue
                dipakai = await _pemakaian(db, p.id)
                if dipakai:
                    jejak = ", ".join(f"{v} {k}" for k, v in dipakai.items())
                    dilewati.append(f"{nama_kini!r} — masih dipakai: {jejak}")
                    continue
                rencana.append(f"HAPUS   {nama_kini!r} (di luar daftar, tanpa transaksi)")
                if terapkan:
                    # Baris saldo stok nol ikut dibuang, kalau tidak FK menolak hapus.
                    await db.execute(
                        delete(StockLevel).where(StockLevel.product_id == p.id))
                    await db.delete(p)

        # --- Laporan ---
        if not rencana and not dilewati:
            print("Master produk sudah sesuai daftar client. Tidak ada perubahan.")
            return

        if rencana:
            print(f"{len(rencana)} perubahan:")
            for baris in rencana:
                print("  " + baris)

        if dilewati:
            print(f"\n{len(dilewati)} produk TIDAK dihapus karena masih berjejak "
                  f"transaksi (riwayat harus tetap utuh):")
            for baris in dilewati:
                print("  - " + baris)
            print("  Buang dulu transaksinya (python -m app.reset_transactions,")
            print("  atau hapus permanen dokumennya dari web), lalu ulangi.")

        if terapkan:
            await db.commit()
            total = (await db.execute(
                select(func.count()).select_from(Product)
                .where(Product.company_id == company.id)
            )).scalar_one()
            print(f"\nDiterapkan. Total produk sekarang: {total}.")
        elif rencana:
            print("\n(dry-run — belum ada yang disimpan)")
            print("Jalankan ulang dengan --terapkan untuk menyimpan.")


if __name__ == "__main__":
    asyncio.run(run(
        terapkan="--terapkan" in sys.argv,
        bersihkan="--bersihkan" in sys.argv,
    ))
