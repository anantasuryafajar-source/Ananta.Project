"""Penyesuaian stok: hasil hitung fisik gudang jadi stok + jurnal.

Satu-satunya jalan mengubah stok tanpa membuat utang ke supplier. Sebelum ini
stok hanya bisa masuk lewat Pembelian, sehingga memasukkan hasil opname berarti
menciptakan utang palsu ke supplier yang tidak pernah menagih.

MODEL: HITUNGAN FISIK, BUKAN SELISIH
User memasukkan JUMLAH FISIK yang ada di gudang; sistem menghitung sendiri
selisihnya terhadap saldo tercatat. Meminta user menghitung selisih memindahkan
aritmetika ke manusia dan hasilnya bergantung pada saldo yang dia kira benar.

DUA MODE - perbedaannya menentukan benar-tidaknya laba rugi:

    opening (stok awal)   Dr Persediaan / Cr Saldo Awal Persediaan (EKUITAS)
    opname  (selisih)     Dr/Cr Persediaan lawan Selisih Persediaan (BEBAN)

Mencatat stok awal sebagai selisih opname membuat laba periode pertama melonjak
atau anjlok sebesar seluruh nilai persediaan pembuka - padahal tidak ada
untung/rugi apa pun yang terjadi. Karena itu modenya wajib dipilih, bukan
ditebak sistem.

PRODUK YANG TIDAK TERCANTUM tidak disentuh, kecuali `hitungan_lengkap=True`
yang secara eksplisit menganggapnya habis. Bawaan ini disengaja: daftar hitung
client biasanya hanya memuat barang yang ADA, dan menolkan sisanya diam-diam
akan menghapus stok beserta jurnalnya tanpa siapa pun sadar.

NILAI SELISIH selalu memakai biaya per BOTOL:
  - stok BERTAMBAH  -> modal yang diketik user, atau avg_cost yang sudah ada,
                       atau modal acuan dari master sebagai upaya terakhir
  - stok BERKURANG  -> avg_cost yang berlaku (barang yang hilang bernilai
                       sebesar yang tercatat, bukan sebesar harga baru)

Biaya nol TIDAK ditolak: ada barang yang memang didapat gratis (lihat Absolut
Vodka di seed_asf). Tapi setiap baris bernilai nol dilaporkan sebagai
peringatan, karena barang bermodal nol akan terjual dengan HPP nol dan
labanya terlihat 100%.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Product, StockAdjustment, StockAdjustmentLine, StockLevel, StockMovement,
)
from .accounts_map import code_to_id, ensure_account
from .journal import Line, post_journal
from .numbering import next_number
from .units import clean_pack_size, format_qty, resolve_warehouse

CENT = Decimal("0.01")
QTYQ = Decimal("0.0001")
COSTQ = Decimal("0.0001")
Z = Decimal("0")


class PenyesuaianError(ValueError):
    """Input penyesuaian stok tidak sah."""


def _q(v) -> Decimal:
    """Nilai UANG (masuk jurnal) - 2 desimal."""
    return Decimal(str(v)).quantize(CENT)


def _qc(v) -> Decimal:
    """Biaya PER BOTOL - 4 desimal (lihat UnitCost di models/base.py)."""
    return Decimal(str(v)).quantize(COSTQ)


def _qn(v) -> Decimal:
    """Kuantitas - 4 desimal."""
    return Decimal(str(v)).quantize(QTYQ)


def _dec(v, nama: str) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except ArithmeticError:
        raise PenyesuaianError(f"{nama} bukan angka yang sah.") from None


async def hitung_penyesuaian(
    db: AsyncSession, *, company_id: str, warehouse_id: str,
    lines_in: list[dict], hitungan_lengkap: bool = False,
) -> dict:
    """Hitung selisih tanpa menyimpan apa pun.

    Dipakai oleh endpoint pratinjau MAUPUN oleh proses simpan, supaya angka
    yang dilihat user sebelum menyetujui persis angka yang nanti diposting.
    """
    if not lines_in and not hitungan_lengkap:
        raise PenyesuaianError("Belum ada produk yang dihitung.")

    terlihat: set[str] = set()
    hasil: list[dict] = []

    for raw in lines_in:
        pid = raw.get("product_id")
        if not pid:
            raise PenyesuaianError("Ada baris tanpa produk.")
        if pid in terlihat:
            raise PenyesuaianError(
                "Satu produk hanya boleh muncul sekali. Gabungkan jumlahnya "
                "dalam satu baris - kolom dus dan botol bisa diisi bersamaan."
            )
        terlihat.add(pid)

        product = (await db.execute(
            select(Product).where(Product.id == pid,
                                  Product.company_id == company_id)
        )).scalar_one_or_none()
        if product is None:
            raise PenyesuaianError("Produk tidak ditemukan.")
        if product.kind != "good":
            raise PenyesuaianError(
                f"{product.name} bukan barang berstok, jadi tidak bisa dihitung."
            )

        qty_dus = _dec(raw.get("qty_dus"), "Jumlah dus")
        qty_botol = _dec(raw.get("qty_botol"), "Jumlah botol")
        if qty_dus < 0 or qty_botol < 0:
            raise PenyesuaianError(
                f"Hitungan fisik {product.name} tidak boleh negatif - "
                "barang yang tidak ada ditulis 0."
            )

        pack = clean_pack_size(product.pack_size)
        hasil.append(await _baris(
            db, product=product, pack=pack, warehouse_id=warehouse_id,
            qty_dus=qty_dus, qty_botol=qty_botol,
            modal_per_dus=raw.get("modal_per_dus"),
            note=(raw.get("note") or "").strip() or None,
            tercantum=True,
        ))

    if hitungan_lengkap:
        hasil.extend(await _yang_tidak_tercantum(
            db, company_id=company_id, warehouse_id=warehouse_id,
            sudah=terlihat,
        ))

    total_nilai = _q(sum((b["line_value"] for b in hasil), Z))
    peringatan = [
        f"{b['product_name']}: stok bertambah {b['diff_display']} tetapi "
        f"modalnya Rp 0 - bila terjual, HPP-nya nol dan labanya terlihat 100%."
        for b in hasil if b["qty_diff"] > 0 and b["unit_cost"] == 0
    ]
    return {
        "lines": hasil,
        "total_value": total_nilai,
        "jumlah_berubah": sum(1 for b in hasil if b["qty_diff"] != 0),
        "warnings": peringatan,
    }


async def _baris(
    db: AsyncSession, *, product: Product, pack: int, warehouse_id: str,
    qty_dus: Decimal, qty_botol: Decimal, modal_per_dus, note: str | None,
    tercantum: bool,
) -> dict:
    """Hitung satu baris: fisik vs sistem, selisih, dan nilainya."""
    qty_counted = _qn(qty_dus * Decimal(pack) + qty_botol)

    level = (await db.execute(
        select(StockLevel).where(StockLevel.product_id == product.id,
                                 StockLevel.warehouse_id == warehouse_id)
    )).scalar_one_or_none()
    qty_before = _qn(level.quantity if level else 0)
    avg = _qc(level.avg_cost if level else 0)
    diff = _qn(qty_counted - qty_before)

    if diff > 0:
        # Barang MASUK: pakai modal yang diketik; kalau kosong, avg_cost yang
        # sudah ada; kalau itu pun nol, modal acuan dari master produk.
        if modal_per_dus not in (None, ""):
            unit_cost = _qc(_dec(modal_per_dus, "Modal per dus") / Decimal(pack))
        elif avg > 0:
            unit_cost = avg
        else:
            unit_cost = _qc(product.purchase_price or 0)
    else:
        # Barang KELUAR/tetap: bernilai sebesar yang tercatat.
        unit_cost = avg

    return {
        "product_id": product.id,
        "product_name": product.name,
        "pack_size": pack,
        "qty_dus": qty_dus,
        "qty_botol": qty_botol,
        "qty_counted": qty_counted,
        "qty_before": qty_before,
        "qty_diff": diff,
        "unit_cost": unit_cost,
        "line_value": _q(diff * unit_cost),
        "note": note,
        "tercantum": tercantum,
        "counted_display": format_qty(qty_counted, pack),
        "before_display": format_qty(qty_before, pack),
        "diff_display": ("+" if diff > 0 else "") + format_qty(diff, pack),
    }


async def _yang_tidak_tercantum(
    db: AsyncSession, *, company_id: str, warehouse_id: str, sudah: set[str],
) -> list[dict]:
    """Produk bersaldo yang tidak ada di daftar hitung - dianggap habis.

    Hanya dipanggil bila user memilih `hitungan_lengkap`. Yang saldonya sudah
    nol dilewati: menuliskannya cuma menambah baris tanpa efek apa pun.
    """
    rows = (await db.execute(
        select(Product, StockLevel)
        .join(StockLevel, StockLevel.product_id == Product.id)
        .where(Product.company_id == company_id,
               StockLevel.warehouse_id == warehouse_id,
               StockLevel.quantity != 0)
        .order_by(Product.name)
    )).all()

    keluar = []
    for product, _level in rows:
        if product.id in sudah:
            continue
        keluar.append(await _baris(
            db, product=product, pack=clean_pack_size(product.pack_size),
            warehouse_id=warehouse_id, qty_dus=Z, qty_botol=Z,
            modal_per_dus=None, note="Tidak tercantum dalam hitungan fisik.",
            tercantum=False,
        ))
    return keluar


async def create_and_post_adjustment(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    on_date: date, warehouse_id: str | None, mode: str,
    lines_in: list[dict], hitungan_lengkap: bool = False,
    notes: str | None = None,
) -> StockAdjustment:
    """Simpan penyesuaian: dokumen + jurnal + mutasi stok. Atomik.

    Caller (router) yang commit/rollback - sama seperti invoice & purchase.
    """
    if mode not in ("opening", "opname"):
        raise PenyesuaianError("Mode harus 'opening' (stok awal) atau 'opname'.")

    warehouse_id = await resolve_warehouse(db, company_id, warehouse_id)
    hitung = await hitung_penyesuaian(
        db, company_id=company_id, warehouse_id=warehouse_id,
        lines_in=lines_in, hitungan_lengkap=hitungan_lengkap,
    )
    if hitung["jumlah_berubah"] == 0:
        raise PenyesuaianError(
            "Tidak ada selisih: seluruh hitungan fisik sama dengan catatan "
            "sistem, jadi tidak ada yang perlu disimpan."
        )

    number = await next_number(
        db, company_id=company_id, doc_type="stock_adjustment",
        on_date=on_date, prefix="ADJ", reset="monthly",
    )

    adj = StockAdjustment(
        company_id=company_id, number=number, date=on_date,
        warehouse_id=warehouse_id, mode=mode,
        hitungan_lengkap=hitungan_lengkap, status="posted",
        total_value=hitung["total_value"], notes=notes, created_by=user_id,
        lines=[
            StockAdjustmentLine(
                product_id=b["product_id"], description=b["product_name"],
                qty_dus=b["qty_dus"], qty_botol=b["qty_botol"],
                pack_size_snapshot=b["pack_size"],
                qty_counted=b["qty_counted"], qty_before=b["qty_before"],
                qty_diff=b["qty_diff"], unit_cost=b["unit_cost"],
                line_value=b["line_value"], note=b["note"],
            )
            for b in hitung["lines"]
        ],
    )
    db.add(adj)
    await db.flush()

    await _posting_jurnal(
        db, adj=adj, company_id=company_id, user_id=user_id,
        on_date=on_date, mode=mode, total=hitung["total_value"],
    )
    await _terapkan_stok(
        db, adj=adj, company_id=company_id, warehouse_id=warehouse_id,
        baris=hitung["lines"],
    )

    await db.flush()
    return adj


async def _posting_jurnal(
    db: AsyncSession, *, adj: StockAdjustment, company_id: str,
    user_id: str | None, on_date: date, mode: str, total: Decimal,
) -> None:
    """Jurnal penyesuaian. Nilai bersih nol -> tidak ada jurnal.

    Nilai nol terjadi wajar: menambah barang bermodal nol menaikkan kuantitas
    tanpa mengubah nilai persediaan sepeser pun, jadi tidak ada yang perlu
    dicatat di buku besar. Valuasi stok tetap cocok dengan saldo Persediaan
    karena kedua sisinya sama-sama tidak berubah.
    """
    if total == 0:
        return

    acc = await code_to_id(db, company_id)
    lawan = await ensure_account(
        db, company_id,
        "inventory_opening" if mode == "opening" else "inventory_variance",
    )
    label = "Stok awal" if mode == "opening" else "Selisih opname"
    nilai = abs(total)

    if total > 0:
        lines = [
            Line(acc["inventory"], debit=nilai,
                 description=f"{label} - stok bertambah"),
            Line(lawan, credit=nilai, description=label),
        ]
    else:
        lines = [
            Line(lawan, debit=nilai, description=label),
            Line(acc["inventory"], credit=nilai,
                 description=f"{label} - stok berkurang"),
        ]

    journal = await post_journal(
        db, company_id=company_id, number=adj.number.replace("ADJ", "JV"),
        on_date=on_date, lines=lines,
        memo=f"Penyesuaian stok {adj.number}",
        source_type="stock_adjustment", source_id=adj.id, created_by=user_id,
    )
    adj.journal_id = journal.id


async def _terapkan_stok(
    db: AsyncSession, *, adj: StockAdjustment, company_id: str,
    warehouse_id: str, baris: list[dict],
) -> None:
    """Setel saldo stok ke hasil hitung fisik + catat mutasinya."""
    for b in baris:
        diff = b["qty_diff"]
        if diff == 0:
            continue

        level = (await db.execute(
            select(StockLevel).where(StockLevel.product_id == b["product_id"],
                                     StockLevel.warehouse_id == warehouse_id)
        )).scalar_one_or_none()
        if level is None:
            level = StockLevel(product_id=b["product_id"],
                               warehouse_id=warehouse_id,
                               quantity=Z, avg_cost=b["unit_cost"])
            db.add(level)
            await db.flush()

        if diff > 0:
            # Rata-rata tertimbang, sama persis dengan pembelian.
            old_qty = _qn(level.quantity)
            old_avg = _qc(level.avg_cost)
            new_qty = b["qty_counted"]
            if new_qty > 0:
                level.avg_cost = _qc(
                    (old_qty * old_avg + diff * b["unit_cost"]) / new_qty
                )
        # Barang berkurang tidak mengubah avg_cost: yang hilang dinilai sebesar
        # yang tercatat, dan sisanya tetap bernilai sama per botolnya.

        # Disetel ke hasil hitung fisik, bukan saldo lama + selisih. Hasilnya
        # sama secara aritmetika, tapi ini membuat opname benar-benar jadi kata
        # akhir atas saldo - tidak ada ruang untuk selisih menumpuk diam-diam.
        level.quantity = b["qty_counted"]

        db.add(StockMovement(
            company_id=company_id, product_id=b["product_id"],
            warehouse_id=warehouse_id, direction="adjustment",
            quantity=diff,                      # BERTANDA: minus = berkurang
            unit_cost=b["unit_cost"],
            ref_type="stock_adjustment", ref_id=adj.id,
        ))
