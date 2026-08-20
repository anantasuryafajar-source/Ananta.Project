"""Penjaga tiga aturan komisi yang disepakati client (2026-08-20).

Kalau file ini gagal, salah satu dari tiga hal ini sedang bocor:
  1. komisi jadi berlaku rata, bukan per kasus;
  2. komisi merembes ke nilai faktur yang dilihat customer;
  3. komisi tidak sampai ke Laba Rugi (atau sampai terlalu cepat).
"""
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models import (
    Company, Warehouse, Contact, Product, StockLevel, Account,
    Journal, JournalEntry, SalesCommission,
)
from app.services.invoice_service import create_and_post_invoice
from app.services.accounts_map import DEFAULT_CODES
from app.services import commission_service, reports


async def _setup(db):
    c = Company(name="T", currency="IDR", costing_method="average")
    db.add(c)
    await db.flush()
    for key, code in DEFAULT_CODES.items():
        db.add(Account(company_id=c.id, code=code, name=key, type="asset",
                       normal_balance="debit"))
    # Akun beban komisi — yang selama ini ada di CoA tapi tak pernah terpakai.
    db.add(Account(company_id=c.id, code="6-1100", name="Beban Komisi",
                   type="expense", normal_balance="debit"))
    # 2-1600 sengaja TIDAK dibuat di sini: accounts_map.ensure_account harus
    # bisa membuatnya sendiri, seperti di database lama yang CoA-nya di-seed
    # sebelum fitur ini ada.
    wh = Warehouse(company_id=c.id, code="GD1", name="Utama", is_default=True)
    ct = Contact(company_id=c.id, type="customer", name="Pelanggan A",
                 payment_term_days=14)
    p = Product(company_id=c.id, sku="A1", name="Barang A", kind="good",
                purchase_price=Decimal("6000"), sale_price=Decimal("10000"))
    db.add_all([wh, ct, p])
    await db.flush()
    db.add(StockLevel(product_id=p.id, warehouse_id=wh.id,
                      quantity=Decimal("100"), avg_cost=Decimal("6000")))
    await db.flush()
    return c, wh, ct, p


async def _faktur(db, c, wh, ct, p):
    return await create_and_post_invoice(
        db, company_id=c.id, user_id=None, contact_id=ct.id,
        on_date=date(2026, 1, 10), warehouse_id=wh.id,
        lines_in=[{"product_id": p.id, "quantity": "10", "unit_price": "10000"}],
    )


async def _utang_komisi(db, company_id) -> Decimal:
    """Saldo akun 2-1600 di neraca."""
    neraca = await reports.balance_sheet(db, company_id, date(2026, 12, 31))
    for baris in neraca["liabilities"]:
        if baris["code"] == "2-1600":
            return Decimal(baris["amount"])
    return Decimal("0")


async def _beban_komisi_di_pnl(db, company_id, start, end) -> Decimal:
    pl = await reports.profit_loss(db, company_id, start, end)
    for baris in pl["expense"]:
        if baris["code"] == "6-1100":
            return Decimal(baris["amount"])
    return Decimal("0")


async def test_komisi_tidak_mengubah_nilai_faktur(db):
    """Aturan 2: faktur = harga real. Mencatat komisi tidak boleh menggesernya."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    total_sebelum, sub_sebelum = inv.total, inv.subtotal

    await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("25000"),
    )
    await db.refresh(inv)
    assert inv.total == total_sebelum
    assert inv.subtotal == sub_sebelum
    # Tidak ada diskon siluman di baris mana pun.
    assert all(Decimal(str(l.discount)) == 0 for l in inv.lines)


async def test_komisi_diakui_saat_disepakati(db):
    """Aturan 3: beban diakui di titik nilainya disepakati (basis akrual)."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    kom = await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("25000"),
    )
    assert kom.status == "terutang"
    assert kom.journal_id is not None          # jurnal pengakuan
    assert kom.settlement_journal_id is None   # belum dibayar
    assert await _beban_komisi_di_pnl(
        db, c.id, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("25000.00")
    # Kewajibannya kelihatan di neraca — inti dari pindah ke akrual.
    assert await _utang_komisi(db, c.id) == Decimal("25000.00")


async def test_pembayaran_menutup_utang_tanpa_menambah_beban(db):
    """Membayar hanya menyentuh neraca — beban tidak boleh terhitung dua kali."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    kom = await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("25000"),
    )
    kom = await commission_service.pay_commission(
        db, company_id=c.id, user_id=None, commission_id=kom.id,
        on_date=date(2026, 1, 20), paid_account_code="1-1000",
    )
    assert kom.status == "dibayar"
    assert kom.settlement_journal_id is not None

    entries = (await db.execute(
        select(JournalEntry).join(Journal)
        .where(Journal.id == kom.settlement_journal_id)
    )).scalars().all()
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)

    # Beban tetap 25.000 (bukan 50.000), utang komisi kembali nol.
    assert await _beban_komisi_di_pnl(
        db, c.id, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("25000.00")
    assert await _utang_komisi(db, c.id) == Decimal("0.00")


async def test_beban_jatuh_di_bulan_kesepakatan_bukan_bulan_pembayaran(db):
    """Basis akrual: pembayaran yang telat tidak menggeser beban ke bulan lain.

    Komisi disepakati Januari, dibayar Maret -> bebannya tetap di Laba Rugi
    JANUARI. Tes ini menjaga agar tidak diam-diam kembali ke basis kas.
    """
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    kom = await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("25000"),
    )
    await commission_service.pay_commission(
        db, company_id=c.id, user_id=None, commission_id=kom.id,
        on_date=date(2026, 3, 5), paid_account_code="1-1000",
    )
    jan = await _beban_komisi_di_pnl(db, c.id, date(2026, 1, 1), date(2026, 1, 31))
    mar = await _beban_komisi_di_pnl(db, c.id, date(2026, 3, 1), date(2026, 3, 31))
    assert jan == Decimal("25000.00")
    assert mar == Decimal("0")


async def test_komisi_ditolak_bila_faktur_belum_terposting(db):
    """Aturan client: komisi dibayarkan SETELAH barang keluar."""
    from app.models import Invoice
    c, wh, ct, p = await _setup(db)
    draft = Invoice(company_id=c.id, number="INV/DRAFT", contact_id=ct.id,
                    date=date(2026, 1, 10), status="draft", total=Decimal("100000"))
    db.add(draft)
    await db.flush()

    with pytest.raises(ValueError, match="diposting"):
        await commission_service.create_commission(
            db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
            invoice_id=draft.id, payee_name="Budi", amount=Decimal("25000"),
        )


async def test_komisi_melebihi_nilai_faktur_ditolak(db):
    """Jaring pengaman salah ketik nol — nilainya custom, jadi tak ada rate
    yang membatasi secara alami."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    with pytest.raises(ValueError, match="melebihi nilai faktur"):
        await commission_service.create_commission(
            db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
            invoice_id=inv.id, payee_name="Budi",
            amount=Decimal(str(inv.total)) + Decimal("1"),
        )


async def test_void_komisi_terbayar_membalik_beban(db):
    """Transaksi terposting tidak dihapus — dibalik, jejak audit utuh."""
    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    kom = await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("25000"),
    )
    await commission_service.pay_commission(
        db, company_id=c.id, user_id=None, commission_id=kom.id,
        on_date=date(2026, 1, 20), paid_account_code="1-1000",
    )
    await commission_service.void_commission(
        db, company_id=c.id, user_id=None, commission_id=kom.id,
        on_date=date(2026, 1, 25), reason="salah orang",
    )
    kom = (await db.execute(
        select(SalesCommission).where(SalesCommission.id == kom.id)
    )).scalar_one()
    assert kom.status == "void"
    assert await _beban_komisi_di_pnl(
        db, c.id, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("0")
    # Tidak boleh ada utang komisi menggantung setelah pembatalan.
    assert await _utang_komisi(db, c.id) == Decimal("0.00")


async def test_backfill_menambal_komisi_lama_tanpa_jurnal(db):
    """Komisi era basis kas (tanpa jurnal pengakuan) bisa ditambal, sekali saja.

    Meniru kondisi database produksi saat pindah ke akrual: baris komisi ada,
    `journal_id` kosong. Menjalankan penambalan dua kali tidak boleh
    menggandakan beban.
    """
    from app.services.accounts_map import ensure_account
    from app.services.journal import Line, post_journal

    c, wh, ct, p = await _setup(db)
    inv = await _faktur(db, c, wh, ct, p)
    kom = await commission_service.create_commission(
        db, company_id=c.id, user_id=None, on_date=date(2026, 1, 10),
        invoice_id=inv.id, payee_name="Budi", amount=Decimal("25000"),
    )
    # Paksa kembali ke kondisi lama: buang jurnal pengakuannya.
    jr = (await db.execute(
        select(Journal).where(Journal.id == kom.journal_id)
    )).scalar_one()
    await db.delete(jr)          # entries ikut terhapus lewat cascade
    kom.journal_id = None
    await db.flush()
    assert await _beban_komisi_di_pnl(
        db, c.id, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("0")

    # --- inti backfill (logika sama dengan app/backfill_komisi_akrual.py) ---
    async def tambal():
        payable_id = await ensure_account(db, c.id, "commission_payable")
        rows = (await db.execute(
            select(SalesCommission).where(
                SalesCommission.company_id == c.id,
                SalesCommission.status != "void",
                SalesCommission.journal_id.is_(None))
        )).scalars().all()
        for k in rows:
            amount = Decimal(str(k.amount))
            j = await post_journal(
                db, company_id=c.id, number=k.number.replace("KOM", "JVA"),
                on_date=k.date,
                lines=[Line(k.expense_account_id, debit=amount),
                       Line(payable_id, credit=amount)],
                memo=f"Backfill {k.number}", source_type="commission",
                source_id=k.id,
            )
            k.journal_id = j.id
        await db.flush()
        return len(rows)

    assert await tambal() == 1
    assert await _beban_komisi_di_pnl(
        db, c.id, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("25000.00")

    # Idempoten: jalan kedua tidak menemukan apa pun, beban tidak berubah.
    assert await tambal() == 0
    assert await _beban_komisi_di_pnl(
        db, c.id, date(2026, 1, 1), date(2026, 1, 31)) == Decimal("25000.00")
