from datetime import date
from decimal import Decimal
import pytest
from app.models import Company, Account
from app.services.journal import post_journal, Line, JournalNotBalanced


async def _setup(db):
    c = Company(name="T", currency="IDR")
    db.add(c); await db.flush()
    a1 = Account(company_id=c.id, code="1-1000", name="Kas", type="asset", normal_balance="debit")
    a2 = Account(company_id=c.id, code="4-1000", name="Pendapatan", type="income", normal_balance="credit")
    db.add_all([a1, a2]); await db.flush()
    return c, a1, a2


async def test_balanced_journal_ok(db):
    c, a1, a2 = await _setup(db)
    j = await post_journal(
        db, company_id=c.id, number="JV/1", on_date=date.today(),
        lines=[Line(a1.id, debit=Decimal("100")), Line(a2.id, credit=Decimal("100"))],
    )
    assert len(j.entries) == 2


async def test_unbalanced_rejected(db):
    c, a1, a2 = await _setup(db)
    with pytest.raises(JournalNotBalanced):
        await post_journal(
            db, company_id=c.id, number="JV/2", on_date=date.today(),
            lines=[Line(a1.id, debit=Decimal("100")), Line(a2.id, credit=Decimal("90"))],
        )


async def test_debit_and_credit_same_line_rejected(db):
    c, a1, a2 = await _setup(db)
    with pytest.raises(JournalNotBalanced):
        await post_journal(
            db, company_id=c.id, number="JV/3", on_date=date.today(),
            lines=[Line(a1.id, debit=Decimal("50"), credit=Decimal("50")),
                   Line(a2.id, credit=Decimal("0"))],
        )
