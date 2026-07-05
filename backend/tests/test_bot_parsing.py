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
