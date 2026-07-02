"""Beban operasional & kasbon karyawan, dengan jurnal otomatis.

Beban        :  Dr <akun beban>, Cr <kas/bank>
Kasbon keluar:  Dr 1-1600 Piutang Karyawan, Cr <kas/bank>
Cicilan masuk:  Dr <kas/bank>, Cr 1-1600 Piutang Karyawan
Akun 1-1600 dibuat otomatis oleh seed_extras bila belum ada.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Expense, EmployeeLoan, Account
from .journal import Line, post_journal
from .numbering import next_number

CENT = Decimal("0.01")
LOAN_CODE = "1-1600"   # Piutang Karyawan


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


async def _acc_id(db, company_id, code) -> str:
    aid = (await db.execute(
        select(Account.id).where(Account.company_id == company_id,
                                 Account.code == code)
    )).scalar_one_or_none()
    if not aid:
        raise ValueError(f"Akun {code} tidak ada di CoA. "
                         f"(Untuk kasbon, jalankan seed_extras dulu.)")
    return aid


async def create_expense(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    on_date: date, category: str, description: str, amount: Decimal,
    expense_account_code: str, paid_account_code: str, note: str | None,
) -> Expense:
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nominal harus lebih dari 0.")
    exp_id = await _acc_id(db, company_id, expense_account_code)
    paid_id = await _acc_id(db, company_id, paid_account_code)
    number = await next_number(db, company_id=company_id, doc_type="expense",
                               on_date=on_date, prefix="EXP", reset="monthly")
    exp = Expense(
        company_id=company_id, number=number, date=on_date, category=category,
        description=description, amount=amount, expense_account_id=exp_id,
        paid_account_id=paid_id, note=note, created_by=user_id,
    )
    db.add(exp)
    await db.flush()
    journal = await post_journal(
        db, company_id=company_id, number=number.replace("EXP", "JV"),
        on_date=on_date,
        lines=[
            Line(exp_id, debit=amount, description=description),
            Line(paid_id, credit=amount, description=f"Bayar {description}"),
        ],
        memo=f"Beban {category}: {description} ({number})",
        source_type="expense", source_id=exp.id, created_by=user_id,
    )
    exp.journal_id = journal.id
    await db.flush()
    return exp


async def create_loan(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    employee_name: str, on_date: date, amount: Decimal,
    paid_account_code: str, note: str | None,
) -> EmployeeLoan:
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nominal harus lebih dari 0.")
    loan_acc = await _acc_id(db, company_id, LOAN_CODE)
    cash_id = await _acc_id(db, company_id, paid_account_code)
    number = await next_number(db, company_id=company_id, doc_type="loan",
                               on_date=on_date, prefix="LN", reset="monthly")
    loan = EmployeeLoan(
        company_id=company_id, number=number, employee_name=employee_name,
        date=on_date, amount=amount, note=note, created_by=user_id,
    )
    db.add(loan)
    await db.flush()
    journal = await post_journal(
        db, company_id=company_id, number=number.replace("LN", "JV"),
        on_date=on_date,
        lines=[
            Line(loan_acc, debit=amount, description=f"Kasbon {employee_name}"),
            Line(cash_id, credit=amount, description=f"Kas keluar kasbon {employee_name}"),
        ],
        memo=f"Kasbon {employee_name} ({number})",
        source_type="loan", source_id=loan.id, created_by=user_id,
    )
    loan.journal_id = journal.id
    await db.flush()
    return loan


async def repay_loan(
    db: AsyncSession, *, company_id: str, user_id: str | None,
    loan_id: str, on_date: date, amount: Decimal, cash_account_code: str,
) -> EmployeeLoan:
    amount = _q(amount)
    if amount <= 0:
        raise ValueError("Nominal harus lebih dari 0.")
    loan = (await db.execute(
        select(EmployeeLoan).where(EmployeeLoan.id == loan_id,
                                   EmployeeLoan.company_id == company_id)
    )).scalar_one()
    sisa = _q(Decimal(str(loan.amount)) - Decimal(str(loan.repaid_total)))
    if amount > sisa:
        raise ValueError(f"Cicilan melebihi sisa kasbon ({sisa}).")

    loan_acc = await _acc_id(db, company_id, LOAN_CODE)
    cash_id = await _acc_id(db, company_id, cash_account_code)
    number = await next_number(db, company_id=company_id, doc_type="loanpay",
                               on_date=on_date, prefix="LP", reset="monthly")
    await post_journal(
        db, company_id=company_id, number=number, on_date=on_date,
        lines=[
            Line(cash_id, debit=amount, description=f"Cicilan kasbon {loan.employee_name}"),
            Line(loan_acc, credit=amount, description=f"Pengurangan piutang {loan.employee_name}"),
        ],
        memo=f"Cicilan kasbon {loan.employee_name} ({loan.number})",
        source_type="loan_payment", source_id=loan.id, created_by=user_id,
    )
    loan.repaid_total = _q(Decimal(str(loan.repaid_total)) + amount)
    if Decimal(str(loan.repaid_total)) >= Decimal(str(loan.amount)):
        loan.status = "paid"
    await db.flush()
    return loan
