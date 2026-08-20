from decimal import Decimal

from app.bot.parsing import (
    DEFAULT_EXPENSE_CODE,
    DEFAULT_PAID_CODE,
    parse_amount,
    parse_expense_block,
    resolve_expense_account,
    resolve_payment_account,
)


def test_parse_amount():
    assert parse_amount("150000") == Decimal("150000")
    assert parse_amount("150.000") == Decimal("150000")  # titik ribuan
    assert parse_amount("1.500,00") == Decimal("150000")
    assert parse_amount("0") is None  # harus > 0
    assert parse_amount("abc") is None
    assert parse_amount("-5") is None


def test_resolve_expense_account():
    assert resolve_expense_account("bensin") == "6-2400"
    assert resolve_expense_account("Beli BENSIN pertamax") == "6-2400"
    assert resolve_expense_account("6-3000") == "6-3000"  # kode langsung
    assert resolve_expense_account("entah apa") is None  # -> caller pakai default


def test_resolve_payment_account():
    assert resolve_payment_account("kas") == "1-1000"
    assert resolve_payment_account("BCA") == "1-1110"
    assert resolve_payment_account("ocbc") == "1-1120"
    assert resolve_payment_account("1-1000") == "1-1000"


def test_parse_expense_block_full():
    block = """Jumlah: 150.000
Untuk: Bensin operasional
Beban: bensin
Bayar: kas"""
    f = parse_expense_block(block)
    assert parse_amount(f["amount_raw"]) == Decimal("150000")
    assert f["description"] == "Bensin operasional"
    assert resolve_expense_account(f["expense_raw"]) == "6-2400"
    assert resolve_payment_account(f["paid_raw"]) == "1-1000"


def test_parse_expense_block_defaults():
    # tanpa Beban & Bayar -> caller pakai default
    block = "Jumlah: 50000\nUntuk: Parkir"
    f = parse_expense_block(block)
    assert parse_amount(f["amount_raw"]) == Decimal("50000")
    assert f["description"] == "Parkir"
    assert (resolve_expense_account(f.get("expense_raw", "")) or DEFAULT_EXPENSE_CODE) == "6-2900"
    assert (resolve_payment_account(f.get("paid_raw", "")) or DEFAULT_PAID_CODE) == "1-1000"


def test_resolve_contact_type():
    from app.bot.parsing import resolve_contact_type
    assert resolve_contact_type("supplier") == "supplier"
    assert resolve_contact_type("Pemasok utama") == "supplier"
    assert resolve_contact_type("customer") == "customer"
    assert resolve_contact_type("pelanggan") == "customer"
    assert resolve_contact_type("keduanya") == "both"
    assert resolve_contact_type("entah") is None


def test_parse_contact_block():
    from app.bot.parsing import parse_contact_block, resolve_contact_type
    block = """Tipe: supplier
Nama: PT Sumber Minuman
HP: 081234567890"""
    f = parse_contact_block(block)
    assert f["name"] == "PT Sumber Minuman"
    assert resolve_contact_type(f["type_raw"]) == "supplier"
    assert f["phone"] == "081234567890"


def test_parse_loan_block():
    from app.bot.parsing import parse_loan_block, parse_amount, resolve_payment_account, DEFAULT_PAID_CODE
    block = """Nama: Budi
Jumlah: 500.000
Bayar: bca"""
    f = parse_loan_block(block)
    assert f["name"] == "Budi"
    assert parse_amount(f["amount_raw"]) == Decimal("500000")
    assert resolve_payment_account(f["paid_raw"]) == "1-1110"
    # tanpa bayar -> default kas
    f2 = parse_loan_block("Nama: Ani\nJumlah: 100000")
    assert (resolve_payment_account(f2.get("paid_raw", "")) or DEFAULT_PAID_CODE) == "1-1000"


def test_parse_payment_block():
    from app.bot.parsing import parse_payment_block, parse_amount
    f = parse_payment_block("Faktur: BILL/2026/0001\nJumlah: 500.000")
    assert f["ref"] == "BILL/2026/0001"
    assert parse_amount(f["amount_raw"]) == Decimal("500000")
    f2 = parse_payment_block("Nota: INV/2026/0009\nBayar: 250000")
    assert f2["ref"] == "INV/2026/0009"
    assert parse_amount(f2["amount_raw"]) == Decimal("250000")


def test_parse_item_line():
    """Satuan WAJIB ada di baris item; bot tidak boleh menebak."""
    import pytest
    from app.bot.parsing import ItemUnitMissing, parse_item_line

    assert parse_item_line("MNS-WHK x 10 dus @ 250000") == (
        "MNS-WHK", Decimal("10"), "dus", Decimal("250000"), None)
    assert parse_item_line("CLA-AZL x 5 botol @ 800.000") == (
        "CLA-AZL", Decimal("5"), "botol", Decimal("800000"), None)
    # alias satuan & huruf besar tetap dikenali
    assert parse_item_line("MNS-WHK x 2 DUS @ 100") == (
        "MNS-WHK", Decimal("2"), "dus", Decimal("100"), None)
    assert parse_item_line("MNS-WHK x 2 btl @ 100") == (
        "MNS-WHK", Decimal("2"), "botol", Decimal("100"), None)
    # 'X' di dalam SKU tetap aman
    assert parse_item_line("BOXES x 3 botol @ 0") == (
        "BOXES", Decimal("3"), "botol", Decimal("0"), None)

    assert parse_item_line("ngawur") is None
    assert parse_item_line("SKU x 0 dus @ 100") is None      # qty harus > 0
    assert parse_item_line("SKU x 2 lusin @ 100") is None    # satuan tak dikenal

    # Format lama tanpa satuan DITOLAK dengan galat khusus, bukan ditebak.
    with pytest.raises(ItemUnitMissing):
        parse_item_line("MNS-WHK x 10 @ 250000")
    with pytest.raises(ItemUnitMissing):
        parse_item_line("MNS-WHK x 10 @ 250000 # ada catatan")


def test_parse_item_line_keterangan_opsional():
    """'# keterangan' setara kotak "Keterangan item" di web — opsional."""
    from app.bot.parsing import parse_item_line

    assert parse_item_line("CHIVAS x 10 dus @ 1800000 # 2 botol pecah") == (
        "CHIVAS", Decimal("10"), "dus", Decimal("1800000"), "2 botol pecah")
    # spasi bebas & keterangan boleh memuat tanda baca
    assert parse_item_line("CHIVAS x 1 dus @ 1800000   #beda batch, cek expired") == (
        "CHIVAS", Decimal("1"), "dus", Decimal("1800000"), "beda batch, cek expired")
    # '#' kosong dianggap tidak ada keterangan
    assert parse_item_line("CHIVAS x 1 dus @ 1800000 #") == (
        "CHIVAS", Decimal("1"), "dus", Decimal("1800000"), None)


def test_parse_blok_mengenali_catatan_nota():
    """`Catatan:` mengisi catatan tingkat dokumen, bukan per baris."""
    from app.bot.parsing import parse_pengadaan_block, parse_penjualan_block

    beli = parse_pengadaan_block(
        "Supplier: EXA\n"
        "Catatan: kiriman susulan\n"
        "Item: CHIVAS x 1 dus @ 1800000"
    )
    assert beli["supplier"] == "EXA"
    assert beli["notes"] == "kiriman susulan"
    assert beli["items"] == ["CHIVAS x 1 dus @ 1800000"]

    jual = parse_penjualan_block(
        "Customer: Toko Berkah\nItem: CHIVAS x 1 botol @ 110000")
    assert jual["notes"] is None   # tanpa Catatan: -> None, bukan string kosong


def test_parse_product_block_membaca_modal_per_dus():
    """Bug lama: nilai 'Harga' tersimpan sebagai harga JUAL sehingga modal produk
    selalu kosong di web. Sekarang dibaca sebagai modal per DUS."""
    from app.bot.parsing import parse_product_block

    got = parse_product_block(
        "Nama: Chivas 200ml\nIsi per dus: 24\nModal per dus: 1800000"
    )
    assert got["name"] == "Chivas 200ml"
    assert got["pack_raw"] == "24"
    assert got["price_raw"] == "1800000"
    # SKU tidak wajib lagi (dibuat otomatis dari nama)
    assert "sku" not in got

    # Sinonim yang wajar tetap dikenali
    alias = parse_product_block("Nama: Mansion Vodka\nIsi: 12\nHarga: 1100000")
    assert alias["pack_raw"] == "12"
    assert alias["price_raw"] == "1100000"


def test_parse_pengadaan_block():
    from app.bot.parsing import parse_pengadaan_block
    blk = """Supplier: PT Sumber Minuman
Gudang: Gudang Utama
Item: MNS-WHK x 10 @ 250000
Item: CLA-AZL x 5 @ 800000"""
    b = parse_pengadaan_block(blk)
    assert b["supplier"] == "PT Sumber Minuman"
    assert b["warehouse"] == "Gudang Utama"
    assert len(b["items"]) == 2


def test_parse_penjualan_block():
    from app.bot.parsing import parse_penjualan_block
    blk = """Customer: Toko Berkah
Item: MNS-WHK x 2 @ 300000
Item: CLA-AZL x 1 @ 950000"""
    b = parse_penjualan_block(blk)
    assert b["customer"] == "Toko Berkah"
    assert len(b["items"]) == 2


def test_draft_to_lines_in_membawa_satuan_dan_keterangan():
    """REGRESI: satuan pernah HILANG di jalur konfirmasi bot.

    Baris draft menyimpan "10 dus", tetapi pemetaan ke service dulu hanya
    mengirim product_id/quantity/harga. Service lalu memakai default "botol",
    sehingga 10 dus tercatat 10 botol — salah 12-48x dan langsung masuk jurnal.
    """
    import pytest
    from app.bot.parsing import DraftUnitMissing, draft_to_lines_in

    draft = [
        {"product_id": "p1", "quantity": "10", "unit": "dus",
         "unit_cost": "1800000", "note": "2 botol pecah"},
        {"product_id": "p2", "quantity": "5", "unit": "botol",
         "unit_cost": "80000", "note": None},
    ]
    got = draft_to_lines_in(draft, price_field="unit_cost")
    assert got[0] == {
        "product_id": "p1", "quantity": Decimal("10"), "unit": "dus",
        "unit_cost": Decimal("1800000"), "note": "2 botol pecah",
    }
    assert got[1]["unit"] == "botol" and got[1]["note"] is None

    # penjualan memakai nama field harga yang berbeda
    jual = draft_to_lines_in(
        [{"product_id": "p1", "quantity": "1", "unit": "dus",
          "unit_price": "2400000"}],
        price_field="unit_price")
    assert jual[0]["unit"] == "dus"
    assert jual[0]["unit_price"] == Decimal("2400000")

    # Sesi lama tanpa satuan DITOLAK — tidak boleh diam-diam dianggap botol.
    for rusak in ({"product_id": "p1", "quantity": "10", "unit_cost": "1"},
                  {"product_id": "p1", "quantity": "10", "unit": "",
                   "unit_cost": "1"}):
        with pytest.raises(DraftUnitMissing):
            draft_to_lines_in([rusak], price_field="unit_cost")


def test_handlers_sintaksis_valid():
    """`app/bot/handlers.py` tidak bisa diimpor di tes karena butuh paket
    `telegram`, sehingga kesalahan sintaks di sana lolos dari pytest. Tes ini
    setidaknya memastikan filenya masih bisa di-parse."""
    import ast
    import pathlib

    berkas = pathlib.Path(__file__).resolve().parents[1] / "app" / "bot" / "handlers.py"
    ast.parse(berkas.read_text(encoding="utf-8"), filename=str(berkas))
